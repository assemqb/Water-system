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


def test_russian_med_recognized_as_copper(tmp_path):
    """Ertis_2025-06.pdf/2025-08.pdf: Еміл өзені reports Copper via the
    Russian "медь" spelling instead of Kazakh "мыс" — was not extracted."""
    body = (
        "   Еміл өзені                        (жоғары       медь        мг/дм3   0,0012\n"
        "                                   ластанған)\n"
    )
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    assert len(rows) == 1
    assert rows[0]["water_body"] == "Еміл өзені"
    assert rows[0]["Concentration"] == 0.0012


def test_russian_reversed_nitrate_nitrogen_recognized(tmp_path):
    """"Азот нитратный" (Russian, reversed word order vs the Kazakh-loan
    "нитратты азот") is nitrate-nitrogen too — same NO3-N -> NO3- factor."""
    body = "Азот нитратный     мг/дм3      0,1\n"
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Nitrates")
    assert len(rows) == 1
    assert rows[0]["Concentration"] == round(0.1 * 4.4266, 6)


def test_below_detection_flag_kept_not_dropped(tmp_path):
    body = "Сульфаттар      мг/дм3     0\n"
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Sulfates")
    assert len(rows) == 1
    assert rows[0]["Concentration"] == 0.0
    assert rows[0]["below_detection"] is True


def test_exceeds_plausible_flag_kept_not_dropped(tmp_path):
    """Ertis_2024-09.pdf: Kishi Karakozha Copper 32,9 mg/dm3 — above
    PLAUSIBLE_MAX (25.0) but confirmed real on manual review (that river has
    recurring severe Cu contamination: 22.7, 9.04, 32.9 across other
    months). Flag it, don't silently discard genuine extreme data."""
    body = "Мыс             мг/дм3    32,9\n"
    path = _write_bulletin(tmp_path, "Ertis_2024-09", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    assert len(rows) == 1
    assert rows[0]["Concentration"] == 32.9
    assert rows[0]["exceeds_plausible"] is True
    assert rows[0]["below_detection"] is False


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


def test_class_label_block_boundary_balkash_alakol(tmp_path):
    """Balkash-Alakol_2025-01.pdf p.13: 'Кесте' blocks here inline the class
    label on the SAME line as the name ("Іле өзені - 3 класс ..."), with
    every following line up to the NEXT such name+label line belonging to
    the same block regardless of how many untracked parameters come first.
    Іле's Copper sits 4 lines after its own name+label line; Баянкөл's sits
    after a name-only continuation split by an "мг/дм 3" unit typo."""
    body = (
        "   Іле өзені         -         3 класс    Магний         мг/дм3\n"
        "                              (орташа                                  25,3\n"
        "                             ластанған)   Аммоний ионы   мг/дм3       0,558\n"
        "                                          Сульфаттар     мг/дм3       105,1\n"
        "                                          Мыс            мг/дм3      0,00205\n"
        "   Баянкөл өзені     -         3 класс    Жалпы фосфор   мг/дм   3\n"
        "                                                                      0,304\n"
        "                              (орташа\n"
        "                             ластанған)   Мыс            мг/дм3       0,0014\n"
    )
    path = _write_bulletin(tmp_path, "Balkash-Alakol_2025-01", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    by_wb = {r["water_body"]: r["Concentration"] for r in rows}
    assert by_wb.get("Іле өзені") == 0.00205
    assert by_wb.get("Баянкөл өзені") == 0.0014


def test_orphan_name_sharing_a_line_with_a_value_cell(tmp_path):
    """Balkash-Alakol_2025-10.pdf p.14, Кесте 9: this table has a SECOND
    class column for the previous year ("қазан 2024 жыл"), filled with a
    bare "-" when no prior classification exists — so the object's own
    class label ("3 класс") sits alone on the line BEFORE its name, and the
    name's first fragment ("Кіші Алматы") shares its line with an unrelated
    parameter's value ("жалпы темір ... 0,11") instead of being alone on
    it. The orphan-name scan required the whole line to be just the name,
    so it missed this fragment entirely and fell back to the nearest
    *registered* name instead — Есентай өзені, one block over. Copper
    0,00148 belongs to Кіші Алматы, not Есентай (which has its own,
    different Copper reading, 0,00109, right after)."""
    body = (
        "                                3 класс          магний       мг/дм3         26,267\n"
        " Кіші Алматы                                   жалпы темір    мг/дм3          0,11\n"
        "                      -        (орташа\n"
        "    өзені\n"
        "                             ластанған)           мыс         мг/дм3        0,00148\n"
        "                                3 класс        жалпы темір    мг/дм3         0,165\n"
        " Есентай өзені        -        (орташа\n"
        "                             ластанған)            мыс        мг/дм3        0,00109\n"
    )
    path = _write_bulletin(tmp_path, "Balkash-Alakol_2025-10", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    by_wb = {r["water_body"]: r["Concentration"] for r in rows}
    assert by_wb.get("Кіші Алматы өзені") == 0.00148
    assert by_wb.get("Есентай өзені") == 0.00109


def test_suspected_source_error_flagged_not_corrected(tmp_path):
    """Balkash-Alakol_2025-01.pdf p.13: Темірлік өзені's phosphorus
    (0,0024 — ~100x lower than every other river that month) and copper
    (0,254 — ~100x higher than every other river) read as though transposed
    in the source PDF itself. The value is kept as printed and flagged, not
    corrected; the block ends at Лепсі's own name+label line, so Лепсі must
    NOT receive this value (the bug this replaced: nearest-line attribution
    wrongly gave Лепсі the 0,254 reading)."""
    body = (
        "   Темірлік өзені    -         3 класс    Магний         мг/дм3         27\n"
        "                              (орташа     Жалпы фосфор   мг/дм3       0,0024\n"
        "                             ластанған)\n"
        "                                          Мыс            мг/дм3        0,254\n"
        "   Лепсі өзені       -         3 класс    Жалпы фосфор   мг/дм3        0,231\n"
        "                              (орташа     Аммоний ионы   мг/дм3\n"
        "                             ластанған)                                0,51\n"
    )
    path = _write_bulletin(tmp_path, "Balkash-Alakol_2025-01", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    by_wb = {r["water_body"]: r for r in rows}
    assert by_wb["Темірлік өзені"]["Concentration"] == 0.254
    assert by_wb["Темірлік өзені"]["suspected_source_error"] is True
    assert "Лепсі өзені" not in by_wb


def test_value_on_next_line_when_missing_from_term_line(tmp_path):
    """Balkash-Alakol_2025-01.pdf p.13: 'Мыс   мг/дм3' ends the line with no
    number — the value is the last token of the FOLLOWING line instead
    ("0,0011", after the "(орташа" continuation text)."""
    body = (
        "   Түрген өзені      -         3 класс    Мыс            мг/дм3\n"
        "                              (орташа                                 0,0011\n"
        "                             ластанған)\n"
    )
    path = _write_bulletin(tmp_path, "Balkash-Alakol_2025-01", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    assert len(rows) == 1
    assert rows[0]["water_body"] == "Түрген өзені"
    assert rows[0]["Concentration"] == 0.0011


def _burabay_table(ph_values: list[str], hardness_values: list[str],
                    mineralization_values: list[str], copper_values: list[str]) -> str:
    """Build a synthetic repeated-classifier-prefix 'Ингредиенттер атауы'
    table (Esil_2025-07.pdf's Burabay-lakes format: 'Көл Копа  Көл Зеренді
    Көл Бурабай' instead of a suffix per name) with 3 lake columns at fixed
    x-positions, for testing the per-table pH/mineralization/hardness/copper
    plausibility check that decides whether to include or exclude it."""
    cols = [40, 52, 64]

    def row(label: str, values: list[str]) -> str:
        chars = list(" " * 80)
        chars[0:len(label)] = label
        for pos, val in zip(cols, values):
            chars[pos:pos + len(val)] = val
        return "".join(chars).rstrip() + "\n"

    lines = [
        "№  Ингредиенттер атауы  Өлшем бірліктер\n",
        row("", ["Көл", "Көл", "Көл"]),
        row("", ["Копа", "Зеренді", "Бурабай"]),
        "1   Көрнекі бақылаулар\n",
        row("3  Сутектік көрсеткіш  мг/дм3", ph_values),
        row("9  Кермектік  ммоль/дм3", hardness_values),
        row("10 Минерализация  мг/дм3", mineralization_values),
        row("22 Мыс  мг/дм3", copper_values),
    ]
    return "".join(lines)


def test_repeated_prefix_burabay_table_included_when_plausible(tmp_path):
    body = _burabay_table(
        ph_values=["6,8", "5,7", "6,4"],
        hardness_values=["5,5", "5,7", "2,1"],
        mineralization_values=["614", "794", "195"],
        copper_values=["0,002", "0,0002", "0,0005"],
    )
    path = _write_bulletin(tmp_path, "Esil_2025-07", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    by_wb = {r["water_body"]: r["Concentration"] for r in rows}
    assert by_wb.get("Копа көлі") == 0.002
    assert by_wb.get("Зеренді көлі") == 0.0002
    assert by_wb.get("Бурабай көлі") == 0.0005


def test_repeated_prefix_table_excluded_when_ph_implausible(tmp_path):
    """Esil_2024-06.pdf found a real case of this: a row-shift left a
    hardness- or BOD-scale value under the pH label. A table instance where
    ANY column's checks fail is excluded whole, not just that column."""
    body = _burabay_table(
        ph_values=["6,8", "25,0", "6,4"],  # column 2 implausible (row-shift-like)
        hardness_values=["5,5", "5,7", "2,1"],
        mineralization_values=["614", "794", "195"],
        copper_values=["0,002", "0,0002", "0,0005"],
    )
    path = _write_bulletin(tmp_path, "Esil_2024-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Copper")
    assert rows == []


def test_water_quality_class_assigned_for_river(tmp_path):
    """Order No. 111-НҚ classes apply to rivers — Zinc 0.036 mg/dm3 is
    within the class-1 bound (<=0.04)."""
    body = "  Оба өзені                        (өте        мырыш        мг/дм3    0,036\n"
    path = _write_bulletin(tmp_path, "Ertis_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Zinc")
    assert len(rows) == 1
    assert rows[0]["water_quality_class"] == 1


def test_water_quality_class_blank_for_lake(tmp_path):
    """The order's own scope note excludes seas and lakes (Balkhash named
    explicitly) — same Zinc value as the river case above, but no class."""
    body = "Балқаш көлі                        мырыш        мг/дм3     0,036\n"
    path = _write_bulletin(tmp_path, "Balkash-Alakol_2025-06", body)
    rows = _rows_by_pollutant(_process_bulletin(path), "Zinc")
    assert len(rows) == 1
    assert rows[0]["water_body"] == "Балқаш көлі"
    assert rows[0]["water_quality_class"] == ""


def test_water_quality_class_assigned_for_channel_reservoir(tmp_path):
    """A 'су қоймасы' (reservoir) in this dataset is always a dammed RIVER
    reservoir (Бұқтырма, Өскемен, Қапшағай, Кеңгір) — in scope for the
    order's classes even though water_body_type groups it with 'lake' for
    the unrelated natural-mineralization concern (L7). Copper 0,0011 is
    within the class-1 bound (<=0.002)."""
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
    by_wb = {r["water_body"]: r for r in rows}
    assert by_wb["Бұқтырма су қоймасы"]["water_body_type"] == "lake"
    assert by_wb["Бұқтырма су қоймасы"]["water_quality_class"] == 1
