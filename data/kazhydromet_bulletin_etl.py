"""
ETL for real Kazhydromet monthly environmental bulletins (surface water chemistry).

Kazhydromet's oblast branches publish a monthly "Информационный бюллетень о
состоянии окружающей среды" (PDF) per region, which includes a hydrochemical
table for surface water objects: pollutant name, unit (mg/dm3 or mg/l), and
the measured concentration for that month. This module downloads those PDFs,
extracts the hydrochemical tables — attributing each reading to the specific
river/lake it was measured in wherever the table layout allows — and produces
db/kazhydromet_real_pollution_<year>.csv: real measured values, replacing the
previous statistically-reconstructed demo dataset.

Requires the `pdftotext` binary (poppler-utils): `brew install poppler` /
`apt-get install poppler-utils`.

Two source table layouts appear across bulletins/months, recorded as
`table_type` and handled differently:

  1. "worst_parameter" — "Кесте"/class-exceedance tables: one row (or a short
     multi-row block) per water body, listing only whichever parameter(s)
     exceeded that month, e.g. "Жайық өз.  3 сынып  ОБТ5  мг/дм3  2.639".
     The water body name is read off the nearest name line within a bounded
     window (before OR after — Kazhydromet lays these out with the name
     sometimes visually centered on row 2 of a multi-row block, or even
     after the value line entirely when a new object's block starts before
     its own name line is reached), including names split across 2-3 lines
     by column wrapping (e.g. "Глубочанка" on one line, "өзені" appearing
     only after the value line for the *next* object). Only the single
     worst-parameter value per water body is present, so this layout cannot
     support a "typical concentration" statistic — see analytics/water_body.py
     and README L2/L8 for how the two table types are kept apart downstream.
  2. "full_panel" — "Ингредиенттер(дің) атауы" numbered tables: one row per
     parameter, one COLUMN per water body (e.g. Alakol / Bolshoe Almatinskoe
     / Balkhash lakes side by side), reporting every tracked substance for
     each water body whether or not it happens to be the worst one that
     month. Water body names live in 1-3 wrapped header lines; pdftotext
     -layout preserves horizontal character position, so a value is
     attributed to the header whose column-start position is nearest to its
     own. A minority of bulletins repeat the "Көл"/"өз" classifier as a
     prefix for every column instead of a suffix per name ("Көл Копа  Көл
     Зеренді  Көл Бурабай ..."); that layout cannot be reliably separated by
     this method and is intentionally left unattributed rather than risk
     merging two water bodies' values.

Pipeline:
    1. download_bulletins()  — fetch PDFs listed in a manifest JSON
       (ollama/kazhydromet_bulletin_manifest_<year>.json: "{Basin}_{Y-M}" -> URL)
    2. extract_pollution_records() — pdftotext + regex extraction of the 6
       pollutants with an MPC in config.settings.POLLUTANTS
    3. main() — run both steps and write the CSV consumed by data/build_dataset.py

Run: python3 -m data.kazhydromet_bulletin_etl --year 2025
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import re
import subprocess
from pathlib import Path

from config.logging_config import get_logger
from config.settings import OLLAMA_DIR, POLLUTANTS

logger = get_logger(__name__)

BULLETIN_BASE_URL = "https://www.kazhydromet.kz"

BASIN_REGION = {
    "Ertis": "VKO",
    "Esil": "Akmoal",
    "Nura-Sarysu": "Karaganda",
    "Shu-Talas": "Zhambyl",
    "Aralo-Syrdarya": "Kyzylorda",
    "Tobyl-Torgay": "Kostanay",
    "Zhaiyk-Kaspian": "Atyrau",
    "Balkash-Alakol": "Almaty",
}

# Canonical Kazakh/Russian ingredient names (as printed in the bulletins) ->
# (pollutant key in config.settings.POLLUTANTS, conversion factor to that unit)
#
# "нитратты азот" (nitrate-nitrogen, NO3-N) is reported instead of nitrate-ion
# (NO3-) in a number of bulletins — the units are chemically different
# quantities. Converted here to NO3- equivalents so every Nitrates row is
# comparable to the same MPC (config.settings.POLLUTANTS["Nitrates"].mpc,
# which is defined as NO3-, see that file). Factor = molar mass NO3- / molar
# mass N, using IUPAC standard atomic weights (N=14.007, O=15.999):
#   (14.007 + 3*15.999) / 14.007 = 4.4266
NITRATE_N_TO_ION = 4.4266

TERMS: dict[str, tuple[str, float]] = {
    "нитраттар": ("Nitrates", 1.0),
    "нитрат-ионы": ("Nitrates", 1.0),
    "нитраты": ("Nitrates", 1.0),
    "нитратты азот": ("Nitrates", NITRATE_N_TO_ION),
    "азот нитратный": ("Nitrates", NITRATE_N_TO_ION),
    "мыс": ("Copper", 1.0),
    "еріген мыс": ("Copper", 1.0),
    "медь": ("Copper", 1.0),
    "растворенная медь": ("Copper", 1.0),
    "сульфаттар": ("Sulfates", 1.0),
    "сульфаты": ("Sulfates", 1.0),
    "мырыш": ("Zinc", 1.0),
    "цинк": ("Zinc", 1.0),
    "фенолдар": ("Phenols", 1.0),
    "фенолы": ("Phenols", 1.0),
    "ұшпа фенолдар": ("Phenols", 1.0),
    "ұшқыш фенол": ("Phenols", 1.0),
    "летучие фенолы": ("Phenols", 1.0),
    "мұнай өнімдері": ("Oil Products", 1.0),
    "нефтепродукты": ("Oil Products", 1.0),
}
TERM_KEYS = sorted(TERMS.keys(), key=len, reverse=True)

# Generous plausibility ceilings (mg/dm3), covering documented extreme cases
# (Nura-Sarysu mining pollution, Tengiz/Aral hypersalinity, and severe
# recurring Cu/Zn contamination in specific Ertis-basin rivers — Kishi
# Karakozha alone has been seen at 22.7, 9.04, and 32.9 mg/dm3 Copper across
# different months). A value over this ceiling is flagged via
# exceeds_plausible=True rather than dropped: manual review of every case
# found in this dataset (n=1: Ertis_2024-09, Copper 32.9 mg/dm3, Kishi
# Karakozha) confirmed it as a real reading, not a column-misalignment
# artifact — dropping would have discarded genuine data.
PLAUSIBLE_MAX = {
    "Nitrates": 60.0,
    "Copper": 25.0,
    "Sulfates": 10000.0,
    "Zinc": 200.0,
    "Phenols": 0.02,
    "Oil Products": 2.0,
}

# Bulletins with a confirmed internal inconsistency in the extracted table
# (simultaneously implausible pH/temperature/transparency in the same column,
# indicating a text-layer row-shift for that specific PDF).
EXCLUDED_BULLETINS = {
    "Aralo-Syrdarya_2025-10",  # Aral Sea column: pH 10.3, temp 40.6 C, transparency 0 cm
}

LINE_RE = re.compile(r"^\s*(?:\d+\s+)?(?P<prefix>[^\d\n]+?)\s+мг/(?:дм3|л)(?P<rest>[-\d\s.,]*)\s*$")
NUM_TOKEN_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

MONTH_LAST_DAY = {
    "01": "31", "02": "28", "03": "31", "04": "30", "05": "31", "06": "30",
    "07": "31", "08": "31", "09": "30", "10": "31", "11": "30", "12": "31",
}

# Kazakh month names, as printed in a table's "<Month> <year>" banner row —
# sometimes with the year wrapped onto a different line, leaving the month
# name alone with no digit of its own to filter out per-word.
KAZAKH_MONTHS = {
    "қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде",
    "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан",
}

# Water-body name detection for "worst_parameter" style rows: 1-3 leading
# words ending in a recognized Kazakh hydronym suffix.
SUFFIXES = r"(?:өз\.|өзені|көл\.|көлі|тарм\.|тармағы|су қоймасы|шығанағы|теңізі|бассейні|арнасы|каналы)"
LEADING_WB_RE = re.compile(
    r"^\s*([A-ZӘІҢҒҮҰҚӨҺA-Za-zА-Яа-яәіңғүұқөһ0-9\-]+"
    r"(?:\s+[A-ZӘІҢҒҮҰҚӨҺA-Za-zА-Яа-яәіңғүұқөһ0-9\-]+){0,2}"
    rf"\s+{SUFFIXES})(?=\s{{2,}}|\s*$)"
)
LAKE_SUFFIXES = ("көл.", "көлі", "су қоймасы", "шығанағы", "теңізі", "бассейні")

STANDALONE_CLASSIFIERS = {
    "көл", "көлі", "көл.", "өз", "өзені", "өз.", "тарм", "тарм.", "тармағы",
    "теңізі", "қоймасы", "бассейні",
}

# A water-body name split across lines by column wrapping, where the
# trailing classifier suffix lands on its own line — sometimes only AFTER
# the value line for the object (e.g. Ertis_2025-11.pdf: "Глубочанка" / value
# row / "өзені"; Ertis_2025-07.pdf: "Бұқтырма су" / value row / "қоймасы").
# First word must start uppercase (proper noun); a second word, if present,
# may be lowercase ("су" in "Бұқтырма су қоймасы").
ORPHAN_NAME_RE = re.compile(
    r"^\s*([А-ЯӘІҢҒҮҰҚӨҺ][а-яәіңғүұқөһ]+(?:\s+[А-Яа-яӘәІіҢңҒғҮүҰұҚқӨөҺһ]+)?)\s*$"
)
ORPHAN_SUFFIX_ONLY_RE = re.compile(
    r"^\s*(өзені|өз\.|көлі|көл\.|тармағы|тарм\.|қоймасы|теңізі|бассейні|каналы|шығанағы)\s*$",
    re.IGNORECASE,
)
ORPHAN_LOOKAHEAD = 3  # lines to search forward for the trailing suffix fragment
BLOCK_NAME_LOOKAHEAD = 8  # lines to search forward from a class-label for its water body's name

# "Кесте"/class-exceedance table rows always carry a class assessment next to
# each water body ("5 – сынып", "3 – класс", "4– класс"): a bare number,
# optional dash, then "сынып"/"класс" in the NOMINATIVE case. This is the
# true block-boundary marker — more reliable than proximity to the water
# body's name text, which pdftotext can print 0-2 lines away from where the
# block it belongs to actually starts (see _scan_class_label_blocks). The
# narrative summary sentences that follow every table use the DATIVE case
# instead ("сыныпқа", "класқа" — "belongs to class N"), which \b correctly
# excludes since Cyrillic case suffixes are glued on with no space.
CLASS_LABEL_RE = re.compile(r"(?<!\S)\d+\s*[-–—]?\s*(?:сынып|класс)\b")

# A tracked pollutant's own "Кесте"-row can end at "мг/дм3" with the actual
# number appearing alone at the end of the next 1-2 lines instead (e.g.
# Balkash-Alakol_2025-01.pdf: "Түрген өзені - 3 класс   Мыс   мг/дм3" / next
# line ends "...  0,0011" with no other digits on the term's own line).
NEXT_VALUE_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*$")

# Bare-word lines seen stacked beside a single value in "worst_parameter"
# blocks when several parameters share one measurement column visually but
# pdftotext linearizes them into one row with only ONE actually adjacent to
# the value (e.g. Ertis_2025-11.pdf p.15, Бұқтырма өзені: марганец / ОБТ5 /
# [value] / жалпы темір / мыс stacked around a single "0,016"). Which listed
# parameter the number belongs to cannot be recovered from the flattened
# text, so any value with 2+ of these immediately around it is dropped
# rather than guessed.
BARE_PARAM_WORDS = {
    "марганец", "жалпы темір", "темір", "магний", "кермектік", "кермектігі",
    "минералдану", "минерализация", "хлоридтер", "фосфаттар", "жалпы фосфор",
    "қалқыма заттар", "өлшенген заттар", "аммоний-иондар", "аммоний ионы",
    "тұз аммонийі", "никель", "кадмий", "қорғасын", "обт5", "охт", "натрий",
    "кальций", "калий", "гидрокарбонаттар", "нитритті азот", "құрғақ қалдық",
    "хром", "мышьяк", "күшән", "сынап",
} | set(TERM_KEYS)
AMBIGUOUS_CELL_WINDOW = 2

# Known cosmetic artifacts from column-wrap merging (a name letter or two
# landing on its own wrapped line) or leading/trailing connective words
# ("бірлігі" = "unit", "айына" = "for the month of", "бойынша" = "regarding")
# that a strict proximity-based column merge, or the greedy leading-word
# match, cannot distinguish from a genuine extra word in the name.
JUNK_WORDS = {"бірлігі", "айына", "бойынша", "атауы"}

NAME_FIXUPS = {
    "Шола қ көлі": "Шолақ көлі",
    "Сұлта нк елді көлі": "Сұлтанкелді көлі",
}

# Spelling/abbreviation variants that refer to the same water body, found by
# inspecting the full set of extracted names — unify to one canonical form
# so the same river isn't split into two rows in any per-water-body stat.
CANONICAL_NAMES = {
    "Балкаш көлі": "Балқаш көлі",  # Cyrillic к vs Kazakh қ
    "Еміл өз.": "Еміл өзені",
    "Ембі өз.": "Ембі өзені",
    "Тобыл өз.": "Тобыл өзені",
    "Торғай өз.": "Торғай өзені",
    "Тоғызақ өз.": "Тоғызақ өзені",
    "Обаған өз.": "Обаған өзені",
    "Әйет өз.": "Әйет өзені",
    "Жайық өз.": "Жайық өзені",
    "Қиғаш өз.": "Қиғаш өзені",
    "Арасан өз.": "Арасан өзені",
    "Маховка өз.": "Маховка өзені",
    "Секисовка өз.": "Секисовка өзені",
    "Үй өз.": "Үй өзені",
    "Кіші Қарақожа өз.": "Кіші Қарақожа өзені",
    "Зеренды көлі": "Зеренді көлі",
}

# Sea names that appear as bare proper nouns in ingredient-table column
# headers (e.g. "Солтүстік Каспий" = "Northern Caspian") without a generic
# "теңізі" suffix attached — classified as lake/still-water like any sea.
SEA_NAMES = ("каспий", "арал")

# Repeated-prefix ingredient tables ("Көл Копа  Көл Зеренді  Көл Бурабай
# ...") print the classifier once per column as a PREFIX rather than once
# per name as a suffix. Recovered by anchoring column x-positions on this
# row's classifier tokens (nearest-distance assignment, not proximity
# clustering — see _repeated_prefix_columns), then normalized back to the
# dataset's usual suffix form ("Бурабай көлі") so the same lake reads the
# same way regardless of which table layout it came from.
PREFIX_CLASSIFIER_TOKENS = {"көл", "өз"}
PREFIX_CLASSIFIER_TO_SUFFIX = {"көл": "көлі", "өз": "өзені"}

# A recovered repeated-prefix table is trusted only if every column passes
# a physical-plausibility check — this is the same layout where a genuine
# row-shift was found once before (Esil_2024-06.pdf: a missing pH row
# pushed every later label up by one, see EXCLUDED_BULLETINS-era history).
# pH ("Сутектік көрсеткіш") is nominally 6-9 in clean water; widened to 4-10
# to allow real acidification/alkalinization without also accepting a
# shifted row showing e.g. a hardness- or BOD-scale value (tens to hundreds).
PH_LABEL_RE = re.compile(r"сутект", re.IGNORECASE)
MINERALIZATION_LABEL_RE = re.compile(r"минерализаци", re.IGNORECASE)
HARDNESS_LABEL_RE = re.compile(r"кермект", re.IGNORECASE)
COPPER_LABEL_RE = re.compile(r"(?<!\S)мыс(?!\S)", re.IGNORECASE)
PH_MIN, PH_MAX = 4.0, 10.0
VALIDATION_COPPER_MAX = 0.05

# One reading found, by manual PDF cross-check, to be almost certainly
# transposed with its neighbor IN THE SOURCE DOCUMENT ITSELF (Темірлік
# өзені's "Жалпы фосфор" 0,0024 mg/dm3 is ~100x lower than every other
# river's phosphorus that month, while its "Мыс" 0,254 mg/dm3 is ~100x
# higher than every other river's copper — and 0,0024/0,254 are exactly the
# *typical* magnitudes for copper/phosphorus respectively). Per instruction,
# the value is NOT corrected — flagged only, and excluded from the
# exceedance catalog (see backend/services/dashboard_service.py) so a
# probable data-entry error in the bulletin doesn't read as a real spike.
SUSPECTED_SOURCE_ERRORS = {
    ("Balkash-Alakol_2025-01.pdf", "Темірлік өзені", "Copper"),
}


def classify_type(name: str) -> str:
    low = name.lower()
    if any(low.endswith(suf) for suf in LAKE_SUFFIXES):
        return "lake"
    if any(sea in low.split() for sea in SEA_NAMES):
        return "lake"
    return "river"


def _strip_junk_words(name: str) -> str:
    words = name.split()
    while words and words[0].lower() in JUNK_WORDS:
        words = words[1:]
    while words and words[-1].lower() in JUNK_WORDS:
        words = words[:-1]
    return " ".join(words)


def clean_water_body_name(name: str) -> str:
    name = _strip_junk_words(name)
    name = NAME_FIXUPS.get(name, name)
    return CANONICAL_NAMES.get(name, name)


def is_plausible_name(name: str) -> bool:
    """
    Reject header-parsing artifacts: stray boilerplate/data tokens that ended
    up glued onto a real name, or two+ distinct water-body names concatenated.

    Counting substring occurrences of "көл"/"өз" would misfire on names like
    "Алакөл көлі", where the proper noun itself ends in "-көл" *and* the
    generic classifier "көлі" follows — both legitimate, one name. Instead
    count only STANDALONE classifier tokens (a word that IS "көл"/"көлі"/...,
    not a compound word ending in it); a real name has at most one.
    """
    if not name or len(name) < 4 or len(name) > 40 or re.search(r"\d", name):
        return False
    tokens = name.lower().split()
    if len(tokens) == 1 and tokens[0] in STANDALONE_CLASSIFIERS:
        return False
    return sum(1 for t in tokens if t in STANDALONE_CLASSIFIERS) <= 1


def _term_for(prefix: str) -> tuple[str, float] | None:
    p = re.sub(r"\s+", " ", prefix).strip().lower().rstrip(")").strip()
    for term in TERM_KEYS:
        if p == term or p.endswith(" " + term):
            return TERMS[term]
    return None


def _is_ambiguous_cell(lines: list[str], i: int, window: int = AMBIGUOUS_CELL_WINDOW) -> bool:
    count = 0
    for k in range(max(0, i - window), min(len(lines), i + window + 1)):
        if k == i:
            continue
        if lines[k].strip().lower() in BARE_PARAM_WORDS:
            count += 1
    return count >= 2


def _repair_number_split(rest: str) -> str:
    # pdftotext -layout sometimes splits "0,174" into "0," + "174" across a
    # column break; repair that artifact before tokenizing.
    return re.sub(r"(\d),\s+(\d+)\s*$", r"\1,\2", rest)


def _resolve_block_name(lines: list[str], label_idx: int, boundary: int) -> tuple[str | None, str | None]:
    """
    Resolve the water-body name that owns a "Кесте" class-label block.

    The name is looked for, in order: on the SAME line as the label (before
    or after it — matched from line-start, so "Үлбі өзені   6 – сынып ..."
    and "Темірлік өзені   -   3 класс ..." both resolve directly); then
    forward, up to `boundary` (the next label's line, i.e. never crossing
    into the next block), for either a complete name line or a name split
    across lines by column wrapping (orphan first word(s) + a trailing
    suffix fragment landing on its own line, possibly after a value line).
    """
    wbm = LEADING_WB_RE.match(lines[label_idx])
    if wbm:
        name = clean_water_body_name(re.sub(r"\s+", " ", wbm.group(1)).strip())
        if is_plausible_name(name):
            return name, classify_type(name)

    limit = min(boundary, label_idx + 1 + BLOCK_NAME_LOOKAHEAD)
    k = label_idx + 1
    while k < limit:
        wbm = LEADING_WB_RE.match(lines[k])
        if wbm:
            name = clean_water_body_name(re.sub(r"\s+", " ", wbm.group(1)).strip())
            if is_plausible_name(name):
                return name, classify_type(name)
            k += 1
            continue
        om = ORPHAN_NAME_RE.match(lines[k])
        if om:
            for j in range(k + 1, min(limit, k + 1 + ORPHAN_LOOKAHEAD)):
                sm = ORPHAN_SUFFIX_ONLY_RE.match(lines[j])
                if sm:
                    name = clean_water_body_name(f"{om.group(1).strip()} {sm.group(1).strip()}")
                    if is_plausible_name(name):
                        return name, classify_type(name)
                    break
        k += 1
    return None, None


def _scan_class_label_blocks(lines: list[str]) -> tuple[list[int], dict[int, tuple[str, str]]]:
    """
    Find every "Кесте" class-label line and resolve the water-body name
    each one's block belongs to. A value line's block is whichever label
    line is nearest at-or-before it (see bisect usage in _process_bulletin)
    — replacing plain nearest-line-distance attribution, which get the
    block boundary wrong whenever a value line sits closer (in raw line
    count) to the WRONG neighboring name than to its own block's label.
    """
    label_lines = [i for i, ln in enumerate(lines) if CLASS_LABEL_RE.search(ln)]
    names: dict[int, tuple[str, str]] = {}
    for k, label_idx in enumerate(label_lines):
        boundary = label_lines[k + 1] if k + 1 < len(label_lines) else len(lines)
        name, wtype = _resolve_block_name(lines, label_idx, boundary)
        if name:
            names[label_idx] = (name, wtype)
    return label_lines, names


def _repeated_prefix_columns(header_lines: list[str]) -> tuple[list[int], list[str]]:
    """
    Recover column positions/names for a table that prints the lake/river
    classifier as a PREFIX repeated on every column ("Көл Копа  Көл Зеренді
    Көл Бурабай ...") instead of once per name as a suffix. Proximity
    clustering (the normal path) merges adjacent columns here because they
    sit closer together than a single wrapped 2-word name — so columns are
    anchored instead on the x-positions of the repeated classifier tokens
    themselves (one per column, always present), and every other header
    word is assigned to its NEAREST anchor rather than merged by distance
    to its neighbors.
    """
    SKIP = {
        "ингредиенттердің", "ингредиентердің", "ингредиенттер", "ингредиенттердіңатауы",
        "атауы", "өлшем", "бірлігі", "бірліктер", "бірліктері", "өлшембірлігі", "№", "р/р",
    } | KAZAKH_MONTHS
    best_positions: list[int] = []
    for hl in header_lines:
        positions = [m.start() for m in re.finditer(r"\S+", hl) if m.group().lower() in PREFIX_CLASSIFIER_TOKENS]
        if len(positions) > len(best_positions):
            best_positions = positions
    if len(best_positions) < 3:
        return [], []

    anchors = sorted(best_positions)
    n = len(anchors)
    # Fragments left of the first classifier token are unrelated header
    # boilerplate wrapped onto this band by coincidence (e.g. "і"/"ния" —
    # leftover pieces of "Өлшем бірліктері"), not part of any lake's name.
    left_margin = anchors[0] - 5
    columns: list[list[str]] = [[] for _ in range(n)]
    for hl in header_lines:
        # Skip the "<Month> <year>" banner row entirely — a bare month name
        # (e.g. "Шілде 2025") has no digits of its own to filter per-word,
        # so it would otherwise get glued onto whichever column its x
        # position happens to land nearest.
        if re.search(r"\d{4}|жылғы|айында", hl):
            continue
        for m in re.finditer(r"\S+", hl):
            token = m.group()
            if m.start() < left_margin:
                continue
            low = token.lower().strip(",.")
            if low in SKIP or re.search(r"\d", token):
                continue
            idx = min(range(n), key=lambda k: abs(anchors[k] - m.start()))
            columns[idx].append(token)

    names: list[str] = []
    for words in columns:
        raw = ""
        for w in words:
            # A short lowercase fragment is a mid-WORD wrap (e.g.
            # "Майба"/"лық" -> "Майбалық"), not a new word — join without a
            # space; anything else (a capitalized word, or a recognized
            # suffix) is genuinely separate.
            if raw and w[:1].islower() and len(w) <= 5:
                raw += w
            else:
                raw = f"{raw} {w}" if raw else w
        low_words = raw.lower().split()
        if low_words and low_words[0] in PREFIX_CLASSIFIER_TO_SUFFIX:
            suffix = PREFIX_CLASSIFIER_TO_SUFFIX[low_words[0]]
            raw = " ".join(raw.split()[1:] + [suffix])
        name = clean_water_body_name(re.sub(r"\s+", " ", raw).strip())
        names.append(name if is_plausible_name(name) else "")
    return anchors, names


def _find_table_end(lines: list[str], data_start: int, max_span: int = 60) -> int:
    limit = min(len(lines), data_start + max_span)
    for i in range(data_start, limit):
        if re.search(r"Ингредиент", lines[i]) or "Қосымша" in lines[i]:
            return i
    return limit


def _extract_label_row_values(
    lines: list[str], start: int, end: int, anchors: list[int], label_re: re.Pattern
) -> dict[int, float] | None:
    for i in range(start, end):
        m = label_re.search(lines[i])
        if not m:
            continue
        values: dict[int, float] = {}
        for nm in NUM_TOKEN_RE.finditer(lines[i], m.end()):
            try:
                val = float(nm.group().replace(",", "."))
            except ValueError:
                continue
            idx = min(range(len(anchors)), key=lambda k: abs(anchors[k] - nm.start()))
            values[idx] = val
        return values
    return None


def _validate_repeated_prefix_table(
    lines: list[str], data_start: int, table_end: int, anchors: list[int]
) -> tuple[bool, str]:
    """
    Physical-plausibility check for a recovered repeated-prefix table,
    applied per table INSTANCE (all-or-nothing): every column's pH must be
    in a normal range, mineralization must exceed hardness, and copper must
    be at a trace concentration. A genuine row-shift (see Esil_2024-06.pdf,
    found via this exact symptom: pH-range values under the wrong label)
    fails at least one of these for at least one column.
    """
    ph = _extract_label_row_values(lines, data_start, table_end, anchors, PH_LABEL_RE)
    mineralization = _extract_label_row_values(lines, data_start, table_end, anchors, MINERALIZATION_LABEL_RE)
    hardness = _extract_label_row_values(lines, data_start, table_end, anchors, HARDNESS_LABEL_RE)
    copper = _extract_label_row_values(lines, data_start, table_end, anchors, COPPER_LABEL_RE)
    if not (ph and mineralization and hardness and copper):
        return False, "could not locate pH/mineralization/hardness/copper rows to validate"
    for idx in range(len(anchors)):
        if idx not in ph or not (PH_MIN <= ph[idx] <= PH_MAX):
            return False, f"column {idx}: pH {ph.get(idx)} outside [{PH_MIN}, {PH_MAX}]"
        if idx not in mineralization or idx not in hardness or not (mineralization[idx] > hardness[idx]):
            return False, (
                f"column {idx}: mineralization {mineralization.get(idx)} "
                f"<= hardness {hardness.get(idx)}"
            )
        if idx not in copper or copper[idx] >= VALIDATION_COPPER_MAX:
            return False, f"column {idx}: copper {copper.get(idx)} >= {VALIDATION_COPPER_MAX}"
    return True, "ok"


def _parse_ingredient_header(
    lines: list[str], start_idx: int, stem: str = ""
) -> tuple[list[int], list[str], int]:
    """Find water-body column headers for a numbered 'Ингредиент(тер)дің атауы' table."""
    header_lines: list[str] = []
    i = start_idx
    limit = min(len(lines), start_idx + 10)
    while i < limit:
        # Row 1 varies by bulletin ("Көзбен шолу", "Көрнекі бақылаулар", ...) but
        # is always the bare index "1" followed by text with no digits (it's a
        # qualitative visual-inspection row, never a numeric measurement).
        row1 = re.match(r"^\s*1\s+(\S.*)$", lines[i])
        if row1 and not re.search(r"\d", row1.group(1)):
            break
        header_lines.append(lines[i])
        i += 1
    data_start = i

    # Some bulletins repeat the classifier as a prefix for every column
    # ("Көл Копа   Көл Зеренді   Көл Бурабай ...") instead of once per name
    # via a suffix ("X көлі"). Proximity-based column clustering below
    # merges wrapped two-line names (e.g. "Үлкен" + "Алматы көлі") but would
    # also wrongly merge adjacent columns in this tighter-spaced repeated-
    # prefix layout — recover it separately (anchored on the classifier
    # tokens' positions) and validate each recovered instance before
    # trusting it (a prior version of this exact layout, Esil_2024-06.pdf,
    # turned out to have a genuine row-shift — see _validate_repeated_prefix_table).
    standalone_prefix_count = sum(
        1 for hl in header_lines for w in re.findall(r"\S+", hl) if w.lower() in ("көл", "өз")
    )
    if standalone_prefix_count >= 3:
        anchors, names = _repeated_prefix_columns(header_lines)
        if len(anchors) >= 3 and all(names):
            table_end = _find_table_end(lines, data_start)
            ok, reason = _validate_repeated_prefix_table(lines, data_start, table_end, anchors)
            if ok:
                # `anchors` are the classifier tokens' own x-positions —
                # correct for NEAREST-distance column assignment (used above
                # for validation), but the main extraction loop below looks
                # up a value's column via bisect (boundary semantics: "which
                # column START is this value at-or-past"). Re-express as
                # boundaries at the midpoint between each pair of anchors so
                # the two methods agree on where a value between two closely
                # spaced columns actually belongs.
                boundaries = [anchors[0]] + [
                    (anchors[k] + anchors[k + 1]) // 2 for k in range(len(anchors) - 1)
                ]
                return boundaries, names, data_start
            logger.warning(
                "Excluded repeated-prefix table %s at line %d (%s): %s",
                stem, start_idx + 1, reason, names,
            )
        return [], [], data_start

    SKIP = {
        "ингредиенттердің", "ингредиентердің", "ингредиенттер", "ингредиенттердіңатауы",
        "атауы", "өлшем", "бірлігі", "бірліктер", "бірліктері", "өлшембірлігі", "№", "р/р",
    } | KAZAKH_MONTHS
    clusters: list[list] = []  # each: [start_char, text]
    for hl in header_lines:
        # Skip the "<Month> <year>" banner row entirely — a bare month name
        # (e.g. "Шілде 2025") has no digits of its own to filter per-word,
        # so it would otherwise get glued onto whichever column its x
        # position happens to land nearest.
        if re.search(r"\d{4}|жылғы|айында", hl):
            continue
        words = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\S+", hl)]
        words = [w for w in words if w[2].lower().strip(",.") not in SKIP and not re.search(r"\d", w[2])]
        if not words:
            continue
        line_clusters = []
        cur = [words[0][0], words[0][1], words[0][2]]
        for s, e, t in words[1:]:
            if s - cur[1] <= 2:
                cur[1] = e
                cur[2] += " " + t
            else:
                line_clusters.append(cur)
                cur = [s, e, t]
        line_clusters.append(cur)

        for s, e, t in line_clusters:
            merged = False
            for c in clusters:
                if abs(c[0] - s) <= 8:
                    c[1] = c[1] + " " + t
                    merged = True
                    break
            if not merged:
                clusters.append([s, t])

    clusters.sort(key=lambda c: c[0])
    starts, names = [], []
    for c in clusters:
        name = clean_water_body_name(re.sub(r"\s+", " ", c[1]).strip())
        if not is_plausible_name(name):
            continue
        starts.append(c[0])
        names.append(name)
    return starts, names, data_start


def _scan_water_body_lines(lines: list[str]) -> dict[int, tuple[str, str]]:
    """
    Pre-scan every "worst_parameter" water-body name occurrence, registered
    at the line index a nearest-neighbor lookup should associate with it.

    Two shapes are recognized:
      - a complete name on one line (LEADING_WB_RE) — the common case.
      - a name split by column wrapping across up to `ORPHAN_LOOKAHEAD`
        lines, where the trailing classifier suffix ("өзені", "қоймасы", ...)
        appears alone on its own line — sometimes only after the object's
        value line. Registered at the FIRST fragment's line index, so a
        nearest-neighbor search from any line in between (including the
        value line itself) finds it close by.
    """
    wb_by_line: dict[int, tuple[str, str]] = {}
    claimed_suffix_lines: set[int] = set()
    for idx, ln in enumerate(lines):
        wbm = LEADING_WB_RE.match(ln)
        if wbm:
            name = clean_water_body_name(re.sub(r"\s+", " ", wbm.group(1)).strip())
            if is_plausible_name(name):
                wb_by_line[idx] = (name, classify_type(name))
                continue

        om = ORPHAN_NAME_RE.match(ln)
        if not om:
            continue
        for k in range(idx + 1, min(len(lines), idx + 1 + ORPHAN_LOOKAHEAD)):
            if k in claimed_suffix_lines:
                continue
            sm = ORPHAN_SUFFIX_ONLY_RE.match(lines[k])
            if sm:
                name = clean_water_body_name(f"{om.group(1).strip()} {sm.group(1).strip()}")
                if is_plausible_name(name):
                    wb_by_line[idx] = (name, classify_type(name))
                    claimed_suffix_lines.add(k)
                break
    return wb_by_line


def download_bulletins(manifest_path: Path, pdf_dir: Path) -> None:
    """Download every bulletin PDF listed in the manifest (skips existing files)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for key, url in manifest.items():
        out = pdf_dir / f"{key}.pdf"
        if out.exists() and out.stat().st_size > 10_000:
            continue
        subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", "-o", str(out), url], check=False)
        if not out.exists() or out.stat().st_size < 10_000:
            logger.warning("Bulletin download failed or too small: %s (%s)", key, url)


def _pdf_to_text(pdf_path: Path, txt_dir: Path) -> Path:
    txt_path = txt_dir / (pdf_path.stem + ".txt")
    if not txt_path.exists() or txt_path.stat().st_mtime < pdf_path.stat().st_mtime:
        subprocess.run(["pdftotext", "-layout", str(pdf_path), str(txt_path)], check=True)
    return txt_path


def _process_bulletin(txt_path: Path) -> list[dict]:
    stem = txt_path.stem
    if stem in EXCLUDED_BULLETINS:
        return []
    basin, year_month = stem.rsplit("_", 1)
    year, month = year_month.split("-")
    region = BASIN_REGION[basin]
    date = f"{year}-{month}-{MONTH_LAST_DAY[month]}"

    lines = txt_path.read_text(encoding="utf-8", errors="ignore").split("\n")

    # Primary attribution for "Кесте" rows: which class-label block a line
    # falls in (see _scan_class_label_blocks). Bodies of text with no class
    # labels at all (e.g. a bare single-row test fixture) fall through to
    # the older nearest-line-distance scan below as a fallback.
    label_lines, block_names = _scan_class_label_blocks(lines)

    wb_by_line = _scan_water_body_lines(lines)
    wb_line_indices = sorted(wb_by_line)

    def _crosses_boundary(a: int, b: int) -> bool:
        lo, hi = min(a, b), max(a, b)
        return any("Қосымша" in lines[k] for k in range(lo, hi + 1))

    def nearest_wb(line_idx: int, window: int = 3) -> tuple[str | None, str | None]:
        best, best_dist = None, window + 1
        for cand in wb_line_indices:
            d = abs(cand - line_idx)
            if d <= window and d < best_dist and not _crosses_boundary(cand, line_idx):
                best, best_dist = cand, d
        return wb_by_line[best] if best is not None else (None, None)

    def resolve_wb(line_idx: int) -> tuple[str | None, str | None]:
        pos = bisect.bisect_right(label_lines, line_idx) - 1
        if pos >= 0:
            name, wtype = block_names.get(label_lines[pos], (None, None))
            if name:
                return name, wtype
        return nearest_wb(line_idx)

    rows: list[dict] = []
    in_ingredient_table = False
    col_starts: list[int] = []
    col_names: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]

        if "Қосымша" in line:
            in_ingredient_table = False

        if re.search(r"Ингредиент", line):
            col_starts, col_names, data_start = _parse_ingredient_header(lines, i, stem)
            # Always treat this as an ingredient-table region and jump past its
            # header, whether or not column names could be attributed. The
            # bailout in _parse_ingredient_header (repeated-prefix layout, e.g.
            # "Көл Копа  Көл Зеренді  Көл Бурабай ...") returns col_names=[] —
            # falling through to the worst_parameter nearest_wb scanner here
            # would be *worse* than no attribution: that scanner isn't
            # column-aware, so it would confidently glue one name onto every
            # water body's values in this multi-column table.
            in_ingredient_table = True
            i = data_start
            continue

        # `in_ingredient_table and not col_starts` means the repeated-prefix
        # table could not be recovered/validated for this instance. Skip the
        # table's VALUES entirely here, not only water_body: a wrong
        # concentration is worse than a missing one.
        skip_table = in_ingredient_table and not col_starts
        # Mask class-label digits ("3 класс") out of the line before matching:
        # LINE_RE's prefix (the pollutant term) may never contain a digit, so
        # an inline class-label between the water-body name and the term on
        # the same physical row (e.g. "Түрген өзені - 3 класс   Мыс   мг/дм3")
        # would otherwise block the match outright.
        line_for_value = CLASS_LABEL_RE.sub(lambda cm: " " * len(cm.group()), line) if not skip_table else line
        m = LINE_RE.match(line_for_value) if not skip_table else None
        if m and not in_ingredient_table and _is_ambiguous_cell(lines, i):
            # Multiple parameter names stacked around one value (pdftotext
            # linearized several visually-stacked rows into one) — cannot
            # tell which parameter the number belongs to. See
            # Ertis_2025-11.pdf p.15, "Бұқтырма өзені" block.
            m = None
        if m:
            term = _term_for(m.group("prefix"))
            if term:
                pollutant, factor = term
                rest = _repair_number_split(m.group("rest"))
                rest_offset = m.start("rest")
                nums = list(NUM_TOKEN_RE.finditer(rest))
                if not nums and not in_ingredient_table:
                    # The value can land alone at the end of the next 1-2
                    # lines instead of on the term's own line (e.g.
                    # Balkash-Alakol_2025-01.pdf: "Мыс   мг/дм3" ends the
                    # line; "0,0011" is the last token of the next line).
                    for k in range(i + 1, min(n, i + 3)):
                        if CLASS_LABEL_RE.search(lines[k]):
                            break
                        lm = NEXT_VALUE_RE.search(lines[k])
                        if lm:
                            nums = [lm]
                            break
                for nm in nums:
                    try:
                        val = float(nm.group().replace(",", "."))
                    except ValueError:
                        continue
                    if val < 0:
                        continue
                    below_detection = val == 0
                    concentration = round(val * factor, 6)
                    # A real, recurring extreme reading (documented mining
                    # contamination in specific Ertis-basin rivers) is worth
                    # more than a silently-dropped row — flag rather than
                    # drop, so an unusually large value stays visible and
                    # auditable instead of vanishing.
                    exceeds_plausible = not below_detection and concentration > PLAUSIBLE_MAX[pollutant]

                    if in_ingredient_table and col_starts:
                        abs_pos = rest_offset + nm.start()
                        idx = bisect.bisect_right(col_starts, abs_pos) - 1
                        idx = max(0, min(idx, len(col_names) - 1))
                        wb, wbt = col_names[idx], classify_type(col_names[idx])
                    else:
                        wb, wbt = resolve_wb(i)

                    suspected_source_error = (stem + ".pdf", wb or "", pollutant) in SUSPECTED_SOURCE_ERRORS

                    rows.append(
                        {
                            "Date": date,
                            "Basin": basin,
                            "Region": region,
                            "Pollutant": pollutant,
                            "Concentration": concentration,
                            "MPC": POLLUTANTS[pollutant].mpc,
                            "below_detection": below_detection,
                            "exceeds_plausible": exceeds_plausible,
                            "suspected_source_error": suspected_source_error,
                            "water_body": wb or "",
                            "water_body_type": wbt or "",
                            "table_type": "full_panel" if in_ingredient_table else "worst_parameter",
                            "station": "",
                            "source_bulletin": stem + ".pdf",
                        }
                    )
        i += 1

    return rows


def extract_pollution_records(pdf_dir: Path, txt_dir: Path) -> list[dict]:
    """Convert every downloaded bulletin to text and extract pollutant readings."""
    txt_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        txt_path = _pdf_to_text(pdf_path, txt_dir)
        all_rows.extend(_process_bulletin(txt_path))

    seen: set[tuple] = set()
    deduped = []
    for row in all_rows:
        key = (row["Basin"], row["Region"], row["Date"], row["Pollutant"], row["Concentration"], row["water_body"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    deduped.sort(key=lambda r: (r["Basin"], r["Date"], r["Pollutant"], r["Concentration"]))
    return deduped


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "ID", "Date", "Basin", "Region", "Pollutant", "Concentration", "MPC",
        "below_detection", "exceeds_plausible", "suspected_source_error",
        "water_body", "water_body_type", "table_type", "station", "source_bulletin",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i, row in enumerate(rows, 1):
            writer.writerow({"ID": i, **row})
    logger.info("Wrote %d real pollution records to %s", len(rows), out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", default="2025")
    args = parser.parse_args()

    manifest_path = OLLAMA_DIR / f"kazhydromet_bulletin_manifest_{args.year}.json"
    pdf_dir = OLLAMA_DIR / "bulletin_pdfs" / args.year
    txt_dir = OLLAMA_DIR / "bulletin_txt" / args.year
    out_path = OLLAMA_DIR.parent / "db" / f"kazhydromet_real_pollution_{args.year}.csv"

    download_bulletins(manifest_path, pdf_dir)
    rows = extract_pollution_records(pdf_dir, txt_dir)
    write_csv(rows, out_path)
    with_wb = sum(1 for r in rows if r["water_body"])
    full_panel = sum(1 for r in rows if r["table_type"] == "full_panel")
    pct = 100 * with_wb / len(rows) if rows else 0
    print(f"✅ Extracted {len(rows)} real Kazhydromet chemical readings for {args.year} -> {out_path}")
    print(f"   water_body attributed: {with_wb}/{len(rows)} ({pct:.1f}%)")
    print(f"   table_type: full_panel={full_panel}, worst_parameter={len(rows) - full_panel}")


if __name__ == "__main__":
    main()
