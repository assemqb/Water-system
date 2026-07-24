"""Natural-language helpers for chat region/year extraction."""

from __future__ import annotations

import re

REGION_ALIASES: dict[str, str] = {
    "almaty": "Almaty",
    "алматы": "Almaty",
    "astana": "Astana",
    "астана": "Astana",
    "karaganda": "Karaganda",
    "караганда": "Karaganda",
    "karagandy": "Karaganda",
    "shymkent": "Shymkent",
    "шымкент": "Shymkent",
    "vko": "VKO",
    "вко": "VKO",
    "east kazakhstan": "VKO",
    "zhambyl": "Zhambyl",
    "жамбыл": "Zhambyl",
    "aktobe": "Aktobe",
    "актобе": "Aktobe",
    "akmoal": "Akmoal",
    "akmola": "Akmoal",
    "акмола": "Akmoal",
}


def extract_regions(message: str, available: list[str]) -> list[str]:
    m = message.lower()
    found: list[str] = []
    for r in available:
        if r.lower() in m and r not in found:
            found.append(r)
    for alias, canonical in REGION_ALIASES.items():
        if alias in m and canonical in available and canonical not in found:
            found.append(canonical)
    return found


def extract_year(message: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", message)
    return int(match.group(1)) if match else None
