"""Shared plotting choices for thesis figures."""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt


PRINT_DPI = 600
HEATMAP_DPI = 240

MISSING_CELL_COLOR = "#f2f2f2"

COLORBLIND_PALETTE = [
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#999999",  # grey
    "#000000",  # black
]

EXTENDED_COLORBLIND_PALETTE = [
    *COLORBLIND_PALETTE[:-1],
    "#332288",
    "#88CCEE",
    "#44AA99",
    "#117733",
    "#DDCC77",
    "#CC6677",
    "#882255",
    "#AA4499",
    "#DDDDDD",
]

PASS_COLOR = "#0072B2"
FAIL_COLOR = "#D55E00"
NEUTRAL_COLOR = "#666666"
OTHER_COLOR = "#C7C7C7"

GOOD_BAD_CMAP = "RdYlGn"
LOW_GOOD_CMAP = "RdYlGn_r"
SEQUENTIAL_CMAP = GOOD_BAD_CMAP
DIVERGING_CMAP = GOOD_BAD_CMAP


def colorblind_cycle(n: int, palette: Sequence[str] = EXTENDED_COLORBLIND_PALETTE) -> list[str]:
    return [palette[index % len(palette)] for index in range(n)]


def colorblind_cmap(name: str = SEQUENTIAL_CMAP):
    cmap = plt.get_cmap(name).copy()
    cmap.set_bad(MISSING_CELL_COLOR)
    return cmap


def heatmap_text_color(value: float, cmap, vmin: float, vmax: float, threshold: float = 0.58) -> str:
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    red, green, blue, _alpha = cmap(norm(value))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "#111111" if luminance >= threshold else "white"
