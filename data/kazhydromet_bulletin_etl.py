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
    "мыс": ("Copper", 1.0),
    "еріген мыс": ("Copper", 1.0),
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

# Generous plausibility ceilings (mg/dm3) covering documented extreme cases
# (Nura-Sarysu mining pollution, Tengiz/Aral hypersalinity) while rejecting
# PDF text-layer column-misalignment artifacts.
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

LINE_RE = re.compile(r"^\s*(?:\d+\s+)?(?P<prefix>[^\d\n]+?)\s+мг/(?:дм3|л)(?P<rest>[-\d\s.,]+)\s*$")
NUM_TOKEN_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

MONTH_LAST_DAY = {
    "01": "31", "02": "28", "03": "31", "04": "30", "05": "31", "06": "30",
    "07": "31", "08": "31", "09": "30", "10": "31", "11": "30", "12": "31",
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
}

# Sea names that appear as bare proper nouns in ingredient-table column
# headers (e.g. "Солтүстік Каспий" = "Northern Caspian") without a generic
# "теңізі" suffix attached — classified as lake/still-water like any sea.
SEA_NAMES = ("каспий", "арал")


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


def _parse_ingredient_header(lines: list[str], start_idx: int) -> tuple[list[int], list[str], int]:
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
    # via a suffix ("X көлі"). Proximity-based column clustering reliably
    # merges wrapped two-line names (e.g. "Үлкен" + "Алматы көлі") but is not
    # reliable at separating this repeated-prefix layout — bail out to no
    # attribution for this table rather than risk merging two lakes' values.
    standalone_prefix_count = sum(
        1 for hl in header_lines for w in re.findall(r"\S+", hl) if w.lower() in ("көл", "өз")
    )
    if standalone_prefix_count >= 3:
        return [], [], data_start

    SKIP = {
        "ингредиенттердің", "ингредиентердің", "ингредиенттер", "ингредиенттердіңатауы",
        "атауы", "өлшем", "бірлігі", "бірліктер", "бірліктері", "өлшембірлігі", "№", "р/р",
    }
    clusters: list[list] = []  # each: [start_char, text]
    for hl in header_lines:
        if re.search(r"\d{4}\s*жыл|жылғы|айында", hl):
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
            col_starts, col_names, data_start = _parse_ingredient_header(lines, i)
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
        # bailout fired for this table. Investigating one such table
        # (Esil_2024-06.pdf, "Мамыр 2024" sub-table) found it also had a
        # genuine ROW-level shift — a blank pH row pushed every later labeled
        # row (hardness/mineralization swapped, Copper-labeled row showing
        # BOD5-scale magnitudes) up by one — not just an unattributable
        # column layout. Skip the table's VALUES entirely here, not only
        # water_body: a wrong concentration is worse than a missing one.
        skip_table = in_ingredient_table and not col_starts
        m = LINE_RE.match(line) if not skip_table else None
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
                for nm in NUM_TOKEN_RE.finditer(rest):
                    try:
                        val = float(nm.group().replace(",", "."))
                    except ValueError:
                        continue
                    if val < 0:
                        continue
                    below_detection = val == 0
                    concentration = round(val * factor, 6)
                    if not below_detection and concentration > PLAUSIBLE_MAX[pollutant]:
                        continue

                    if in_ingredient_table and col_starts:
                        abs_pos = rest_offset + nm.start()
                        idx = bisect.bisect_right(col_starts, abs_pos) - 1
                        idx = max(0, min(idx, len(col_names) - 1))
                        wb, wbt = col_names[idx], classify_type(col_names[idx])
                    else:
                        wb, wbt = nearest_wb(i)

                    rows.append(
                        {
                            "Date": date,
                            "Basin": basin,
                            "Region": region,
                            "Pollutant": pollutant,
                            "Concentration": concentration,
                            "MPC": POLLUTANTS[pollutant].mpc,
                            "below_detection": below_detection,
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
        "below_detection", "water_body", "water_body_type", "table_type",
        "station", "source_bulletin",
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
