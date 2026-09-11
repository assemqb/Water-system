"""
Regression tests for the multi-line water-body-name attribution bug found
by manual validation of validation_sample.csv (30/30 concentrations correct,
27/30 water bodies correct — all 3 misses were Ertis "Кесте" tables where a
name split across lines let a value get attributed to the water body above
instead of the one it actually belongs to).
"""

from __future__ import annotations

from pathlib import Path

from data.kazhydromet_bulletin_etl import _process_bulletin


def _write_bulletin(tmp_path: Path, stem: str, body: str) -> Path:
    path = tmp_path / f"{stem}.txt"
    path.write_text(body, encoding="utf-8")
    return path


def _rows_by_pollutant(rows: list[dict], pollutant: str) -> list[dict]:
    return [r for r in rows if r["Pollutant"] == pollutant]


def test_orphan_name_suffix_after_value_line(tmp_path):
    """Ertis_2025-11.pdf p.15: 'Глубочанка' / value line / 'өзені' — the
    suffix trails the value line, for the *next* object after Үлбі. Value
    0,076 belongs to Глубочанка, not the previous stateful name (Үлбі)."""
    body = (
        "                                   6 – сынып\n"
        "   Үлбі өзені                        (жоғары         мырыш        мг/дм3     0,224\n"
        "                                   ластанған)\n"
        "                                    6 – сынып\n"
        "  Глубочанка\n"
        "                                     (жоғары         мырыш        мг/дм3     0,076\n"
        "     өзені\n"
        "                                   ластанған)\n"
    )
    path = _write_bulletin(tmp_path, "Ertis_2025-11", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Zinc")
    by_wb = {r["water_body"]: r["Concentration"] for r in rows}
    assert by_wb.get("Үлбі өзені") == 0.224
    assert by_wb.get("Глубочанка өзені") == 0.076


def test_orphan_name_two_words_suffix_after_value_line(tmp_path):
    """Ertis_2025-07.pdf: 'Бұқтырма су' / value line / 'қоймасы' — a
    two-word orphan (second word lowercase, "су" = water) with the
    classifier suffix trailing after the value line. Must not be confused
    with the unrelated "Бұқтырма өзені" (river, a different water body)."""
    body = (
        "    Үржар өзені                                                        мг/дм3     22,7\n"
        "                                       3 – класс\n"
        "    Бұқтырма су\n"
        "                                       (орташа             мыс         мг/дм3    0,0011\n"
        "      қоймасы\n"
        "                                      ластанған)\n"
    )
    path = _write_bulletin(tmp_path, "Ertis_2025-07", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    by_wb = {r["water_body"]: r["Concentration"] for r in rows}
    assert by_wb.get("Бұқтырма су қоймасы") == 0.0011
    assert "Үржар өзені" not in by_wb


def test_name_line_after_value_within_multirow_block(tmp_path):
    """Ertis_2025-12.pdf: a new object's block (class header + value) can
    start before that object's own name line is reached — "Еміл өзені"
    appears one line after its Sulfates value, following Оба's own
    (already-closed) block. Nearest-line attribution, not forward state
    carried over from Оба, must win."""
    body = (
        "                                 5 – сынып\n"
        "   Оба өзені                        (өте        мырыш        мг/дм3    0,036\n"
        "                                ластанған)\n"
        "                                                  ОБТ5       мг/дм3     2,79\n"
        "                                                 магний      мг/дм3     32,8\n"
        "                                 3 – сынып\n"
        "                                               сульфаттар    мг/дм3     242\n"
        "   Еміл өзені                     (орташа\n"
        "                                                  мыс        мг/дм3   0,0017\n"
        "                                ластанған)\n"
    )
    path = _write_bulletin(tmp_path, "Ertis_2025-12", body)
    rows = _process_bulletin(path)
    sulfates = {r["water_body"]: r["Concentration"] for r in _rows_by_pollutant(rows, "Sulfates")}
    copper = {r["water_body"]: r["Concentration"] for r in _rows_by_pollutant(rows, "Copper")}
    assert sulfates.get("Еміл өзені") == 242.0
    assert "Оба өзені" not in sulfates
    assert copper.get("Еміл өзені") == 0.0017


def test_ambiguous_multi_parameter_cell_is_skipped(tmp_path):
    """Ertis_2025-11.pdf p.15: 'Бұқтырма өзені' block stacks марганец / ОБТ5
    / [value] / жалпы темір / мыс around a single number — which listed
    parameter the number belongs to cannot be recovered from the flattened
    text, so it must be dropped rather than guessed (even though "мыс"
    happens to be one of the stacked words)."""
    body = (
        "                                                    марганец\n"
        "                                   3 – сынып\n"
        "                                                      ОБТ5\n"
        " Бұқтырма өзені                     (орташа                       мг/дм3     0,016\n"
        "                                                   жалпы темір\n"
        "                                   ластанған)\n"
        "                                                      мыс\n"
    )
    path = _write_bulletin(tmp_path, "Ertis_2025-11", body)
    rows = _process_bulletin(path)
    assert rows == []


def test_below_detection_flag_kept_not_dropped(tmp_path):
    body = "Сульфаттар      мг/дм3     0\n"
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Sulfates")
    assert len(rows) == 1
    assert rows[0]["Concentration"] == 0.0
    assert rows[0]["below_detection"] is True


def test_ushkysh_fenol_spelling_recognized(tmp_path):
    body = "Ұшқыш фенол      мг/дм3     0,001\n"
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Phenols")
    assert len(rows) == 1
    assert rows[0]["Concentration"] == 0.001


def test_canonical_name_spelling_unified(tmp_path):
    body = "Балкаш көлі                        мырыш        мг/дм3     0,02\n"
    path = _write_bulletin(tmp_path, "Balkash-Alakol_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Zinc")
    assert len(rows) == 1
    assert rows[0]["water_body"] == "Балқаш көлі"


def test_table_type_recorded_for_worst_parameter_row(tmp_path):
    body = "  Оба өзені                        (өте        мырыш        мг/дм3    0,036\n"
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Zinc")
    assert len(rows) == 1
    assert rows[0]["table_type"] == "worst_parameter"
