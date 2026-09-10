"""
ETL for real Kazhydromet monthly environmental bulletins (surface water chemistry).

Kazhydromet's oblast branches publish a monthly "Информационный бюллетень о
состоянии окружающей среды" (PDF) per region, which includes a hydrochemical
table for surface water objects: pollutant name, unit (mg/dm3 or mg/l), and
the measured concentration for that month. This module downloads those PDFs,
extracts the hydrochemical tables, and produces
db/kazhydromet_real_pollution_<year>.csv — real measured values, replacing
the previous statistically-reconstructed demo dataset.

Requires the `pdftotext` binary (poppler-utils): `brew install poppler` /
`apt-get install poppler-utils`.

Pipeline:
    1. download_bulletins()  — fetch PDFs listed in a manifest JSON
       (ollama/kazhydromet_bulletin_manifest_<year>.json: "{Basin}_{Y-M}" -> URL)
    2. extract_pollution_records() — pdftotext + regex extraction of the 6
       pollutants with a Kazakhstan SanPiN fishery MPC (config.settings.POLLUTANTS)
    3. main() — run both steps and write the CSV consumed by data/build_dataset.py

Run: python3 -m data.kazhydromet_bulletin_etl --year 2025
"""

from __future__ import annotations

import argparse
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
TERMS: dict[str, tuple[str, float]] = {
    "нитраттар": ("Nitrates", 1.0),
    "нитрат-ионы": ("Nitrates", 1.0),
    "нитраты": ("Nitrates", 1.0),
    "нитратты азот": ("Nitrates", 4.4268),  # NO3-N -> NO3- (molar mass ratio 62/14)
    "мыс": ("Copper", 1.0),
    "еріген мыс": ("Copper", 1.0),
    "сульфаттар": ("Sulfates", 1.0),
    "сульфаты": ("Sulfates", 1.0),
    "мырыш": ("Zinc", 1.0),
    "цинк": ("Zinc", 1.0),
    "фенолдар": ("Phenols", 1.0),
    "фенолы": ("Phenols", 1.0),
    "ұшпа фенолдар": ("Phenols", 1.0),
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

LINE_RE = re.compile(r"^\s*(?:\d+\s+)?(?P<prefix>[^\d\n]+?)\s+мг/(?P<unit>дм3|л)\s+(?P<rest>[-\d\s.,]+)\s*$")
NUM_TOKEN_RE = re.compile(r"-?\d+(?:[.,]\d+)?")

MONTH_LAST_DAY = {
    "01": "31", "02": "28", "03": "31", "04": "30", "05": "31", "06": "30",
    "07": "31", "08": "31", "09": "30", "10": "31", "11": "30", "12": "31",
}


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


def _extract_numbers(rest: str) -> list[float]:
    # pdftotext -layout sometimes splits "0,174" into "0," + "174" across a
    # column break; repair that artifact before tokenizing.
    rest = re.sub(r"(\d),\s+(\d+)\s*$", r"\1,\2", rest)
    values = []
    for tok in NUM_TOKEN_RE.findall(rest):
        try:
            values.append(float(tok.replace(",", ".")))
        except ValueError:
            continue
    return values


def _match_term(prefix: str) -> tuple[str, float] | None:
    normalized = re.sub(r"\s+", " ", prefix).strip().lower().rstrip(")").strip()
    for term in TERM_KEYS:
        if normalized == term or normalized.endswith(" " + term):
            return TERMS[term]
    return None


def _process_bulletin(txt_path: Path) -> list[dict]:
    stem = txt_path.stem
    if stem in EXCLUDED_BULLETINS:
        return []
    basin, year_month = stem.rsplit("_", 1)
    year, month = year_month.split("-")
    region = BASIN_REGION[basin]
    date = f"{year}-{month}-{MONTH_LAST_DAY[month]}"

    rows = []
    for line in txt_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        term = _match_term(m.group("prefix"))
        if not term:
            continue
        pollutant, factor = term
        for value in _extract_numbers(m.group("rest")):
            if value <= 0:
                continue
            concentration = round(value * factor, 6)
            if concentration > PLAUSIBLE_MAX[pollutant]:
                continue
            rows.append(
                {
                    "Date": date,
                    "Basin": basin,
                    "Region": region,
                    "Pollutant": pollutant,
                    "Concentration": concentration,
                    "MPC": POLLUTANTS[pollutant].mpc,
                    "source_bulletin": stem + ".pdf",
                }
            )
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
        key = (row["Basin"], row["Region"], row["Date"], row["Pollutant"], row["Concentration"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    deduped.sort(key=lambda r: (r["Basin"], r["Date"], r["Pollutant"], r["Concentration"]))
    return deduped


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["ID", "Date", "Basin", "Region", "Pollutant", "Concentration", "MPC", "source_bulletin"]
        )
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
    print(f"✅ Extracted {len(rows)} real Kazhydromet chemical readings for {args.year} -> {out_path}")


if __name__ == "__main__":
    main()
