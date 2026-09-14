"""
Boundary tests for config.settings.classify_water_quality() — the Unified
Classification System (Order No. 111-НҚ, 2025-06-04) class table.

Several pollutants repeat the same bound across consecutive classes by
design (see the comment above WATER_QUALITY_CLASSES): this makes some
classes mathematically unreachable from a single pollutant's value alone
(e.g. Copper can never classify as 2 or 4 on its own). That is asserted
here as expected behavior, not worked around.
"""

from __future__ import annotations

import pytest

from config.settings import classify_water_quality


@pytest.mark.parametrize(
    "pollutant,concentration,expected",
    [
        # Sulfates: the only pollutant with a STRICT class-1 bound (<100).
        ("Sulfates", 99.999, 1),
        ("Sulfates", 100.0, 2),  # exactly at the strict bound -> not class 1
        ("Sulfates", 100.001, 3),
        ("Sulfates", 500.0, 3),
        ("Sulfates", 500.001, 4),
        ("Sulfates", 600.0, 4),
        ("Sulfates", 600.001, 5),
        ("Sulfates", 1500.0, 5),
        ("Sulfates", 1500.001, 6),
        # Nitrates (as NO3- ion, matching this dataset's Nitrates column):
        # classes 1-2 share bound 40, classes 3-5 share bound 45 -> classes
        # 2, 4, 5 are unreachable via Nitrates alone.
        ("Nitrates", 40.0, 1),
        ("Nitrates", 40.001, 3),
        ("Nitrates", 45.0, 3),
        ("Nitrates", 45.001, 6),
        # Copper (general form): classes 1-2 share 0.002, classes 3-4 share
        # 2.0 -> classes 2 and 4 unreachable via Copper alone.
        ("Copper", 0.002, 1),
        ("Copper", 0.0021, 3),
        ("Copper", 2.0, 3),
        ("Copper", 2.0001, 5),
        ("Copper", 2.4, 5),
        ("Copper", 2.4001, 6),
        # Zinc (general form): classes 1-3 share bound 0.04.
        ("Zinc", 0.04, 1),
        ("Zinc", 0.0401, 4),
        ("Zinc", 0.12, 4),
        ("Zinc", 0.20, 5),
        ("Zinc", 0.2001, 6),
        # Phenols (volatile): classes 1-3 share bound 0.001.
        ("Phenols", 0.001, 1),
        ("Phenols", 0.0011, 4),
        ("Phenols", 0.002, 4),
        ("Phenols", 0.005, 5),
        ("Phenols", 0.0051, 6),
        # Oil Products: classes 1-2 share bound 0.05.
        ("Oil Products", 0.05, 1),
        ("Oil Products", 0.0501, 3),
        ("Oil Products", 0.10, 3),
        ("Oil Products", 0.30, 5),
        ("Oil Products", 0.3001, 6),
    ],
)
def test_classify_water_quality_boundaries(pollutant, concentration, expected):
    assert classify_water_quality(pollutant, concentration) == expected


def test_classify_water_quality_unknown_pollutant_returns_none():
    assert classify_water_quality("Water_Level_cm", 123.0) is None


def test_classify_water_quality_none_concentration_returns_none():
    assert classify_water_quality("Copper", None) is None
