"""
Color text helpers (no Painter import, so they can be tested outside Painter).

All RGB tuples here are 0..1 floats in display (sRGB) space.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

RGB = Tuple[float, float, float]

_HEX6 = re.compile(r"^#?([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?$")
_HEX3 = re.compile(r"^#?([0-9a-fA-F]{3})$")
_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_FUNC = re.compile(r"^rgba?\s*\((.*)\)$", re.IGNORECASE)


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


def to_255(rgb: RGB) -> Tuple[int, int, int]:
    return tuple(int(round(clamp01(c) * 255.0)) for c in rgb[:3])  # type: ignore[return-value]


def to_hex(rgb: RGB) -> str:
    r, g, b = to_255(rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def to_rgb255_text(rgb: RGB) -> str:
    r, g, b = to_255(rgb)
    return f"{r}, {g}, {b}"


def to_float_text(rgb: RGB) -> str:
    return ", ".join(f"{clamp01(c):.4f}" for c in rgb[:3])


def parse_color(text: str) -> Optional[RGB]:
    """Parse '#RRGGBB', 'RRGGBB', '#RGB', '#RRGGBBAA' (alpha ignored),
    'rgb(255, 128, 0)', '255, 128, 0' or '1.0, 0.5, 0.0'.

    Three numbers that are all <= 1 are read as 0..1 floats, otherwise as 0..255.
    Returns None if the text is not a color.
    """
    if not text:
        return None
    t = text.strip().strip("'\"").strip()
    m = _HEX6.match(t)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    m = _HEX3.match(t)
    if m:
        h = m.group(1)
        return tuple(int(c * 2, 16) / 255.0 for c in h)  # type: ignore[return-value]
    m = _FUNC.match(t)
    if m:
        t = m.group(1)
    nums = re.findall(_NUM, t)
    rest = re.sub(_NUM, "", t)
    if len(nums) not in (3, 4) or re.search(r"[^\s,;/()]", rest):
        return None
    vals = [float(n) for n in nums[:3]]
    has_dot = any("." in n for n in nums[:3])
    if has_dot and all(0.0 <= v <= 1.0 for v in vals):
        return tuple(vals)  # type: ignore[return-value]
    if all(0.0 <= v <= 255.0 for v in vals):
        return tuple(v / 255.0 for v in vals)  # type: ignore[return-value]
    return None
