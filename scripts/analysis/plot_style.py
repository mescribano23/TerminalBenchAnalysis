"""Shared plotting choices for thesis figures."""

from __future__ import annotations

from collections.abc import Sequence
import textwrap

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


def thesis_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 12,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 11,
            "legend.title_fontsize": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 120,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def paper_axis_labels(fig: plt.Figure) -> None:
    """Use consistent, compact axis text across paper figures."""
    width, height = fig.get_size_inches()
    if height < 3.2:
        fig.set_figheight(3.2)
        height = 3.2
    label_size = 12.0
    tick_size = 10.0
    for ax in fig.axes:
        colorbar = ax.get_label() == "<colorbar>"
        size = 11.0 if colorbar else label_size
        panel_height = ax.get_position().height * height
        y_size = min(size, 11.0) if panel_height < 1.3 else size
        for axis, font_size, wrap_width in (
            (ax.xaxis, size, 40 if width >= 9 else 32),
            (ax.yaxis, y_size, max(12, min(24, int(panel_height * 72 / (y_size * 0.85))))),
        ):
            label = axis.label
            if label.get_text():
                label.set_text("\n".join(
                    textwrap.fill(line, width=wrap_width, break_long_words=False, break_on_hyphens=False)
                    for line in label.get_text().splitlines()
                ))
                label.set_fontsize(font_size)
                axis.labelpad = 7
        xlabels = ax.get_xticklabels()
        ylabels = ax.get_yticklabels()
        x_size = min(tick_size, 9.5) if len(xlabels) > 12 else tick_size
        multiline_heatmap = bool(ax.images) and any("\n" in label.get_text() for label in xlabels)
        if multiline_heatmap:
            x_size = min(x_size, 9.5)
            if len(xlabels) > 6:
                for label in xlabels:
                    label.set_rotation(60)
                    label.set_horizontalalignment("right")
        y_size = min(tick_size, 9.5) if len(ylabels) > 24 else tick_size
        if any("\n" in label.get_text() for label in ylabels):
            y_size = min(y_size, 9.5)
        ax.tick_params(axis="x", labelsize=x_size)
        ax.tick_params(axis="y", labelsize=y_size)
        if len(xlabels) > 6 and not multiline_heatmap:
            if any(max(map(len, label.get_text().splitlines()), default=0) > 8 for label in xlabels):
                for label in xlabels:
                    label.set_rotation(55)
                    label.set_horizontalalignment("right")


def save_paper_figure(fig: plt.Figure, path, **kwargs) -> None:
    """Fit axis text after layout, then export every label in full."""
    main_axes = [ax for ax in fig.axes if not hasattr(ax, "_colorbar")]
    if len(main_axes) == 2 and main_axes[0].get_position().bounds == main_axes[1].get_position().bounds:
        # Twin-axis token plots need room on both sides for their long labels.
        fig.subplots_adjust(left=0.20, right=0.79, bottom=0.30, top=0.96)
        for ax in main_axes:
            ax.yaxis.label.set_fontsize(11)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    height_factor = 1.0
    for ax in main_axes:
        if ax.images and ax.texts:
            rows = ax.images[0].get_array().shape[0]
            cell_height = ax.get_window_extent(renderer).height / rows
            text_height = max(t.get_window_extent(renderer).height for t in ax.texts)
            height_factor = max(height_factor, 1.12 * text_height / cell_height)
    if height_factor > 1.0:
        fig.set_figheight(fig.get_figheight() * height_factor)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

    def wrap_label(label, available):
        words = label.get_text().split()
        if not words:
            return
        properties = label.get_fontproperties()
        lines, line = [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            width = renderer.get_text_width_height_descent(candidate, properties, False)[0]
            if line and width > available:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        label.set_text("\n".join(lines))

    for ax in fig.axes:
        bounds = ax.get_window_extent(renderer)
        wrap_label(ax.xaxis.label, bounds.width * 0.96)
        wrap_label(ax.yaxis.label, bounds.height * 0.95)
        visible = [t for t in ax.get_yticklabels() if t.get_visible() and t.get_text()]
        if len(visible) > 1:
            largest = max(t.get_window_extent(renderer).height for t in visible)
            available = bounds.height / len(visible) * 0.88
            if largest > available:
                for label in visible:
                    label.set_fontsize(max(9.5, label.get_fontsize() * available / largest))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axis_text = [t for ax in fig.axes for t in [ax.xaxis.label, *ax.get_xticklabels()]
                 if t.get_visible() and t.get_text()]
    for ax in main_axes:
        legend = ax.get_legend()
        if legend is None:
            continue
        box = legend.get_window_extent(renderer)
        axes_box = ax.get_window_extent(renderer)
        if box.y1 <= axes_box.y0 + 10:
            labels = [ax.xaxis.label, *ax.get_xticklabels()]
            bottom = min(t.get_window_extent(renderer).y0 for t in labels if t.get_visible() and t.get_text())
            legend.set_loc("upper center")
            legend.set_bbox_to_anchor(((axes_box.x0 + axes_box.width / 2) / fig.bbox.width,
                                       (bottom - 12) / fig.bbox.height), transform=fig.transFigure)
    for legend in fig.legends:
        box = legend.get_window_extent(renderer)
        if any(box.overlaps(t.get_window_extent(renderer)) for t in axis_text):
            bottom = min(t.get_window_extent(renderer).y0 for t in axis_text)
            legend.set_loc("upper center")
            legend.set_bbox_to_anchor((0.5, (bottom - 12) / fig.bbox.height), transform=fig.transFigure)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for note in fig.texts:
        if not note.get_visible() or not note.get_text():
            continue
        box = note.get_window_extent(renderer)
        obstacles = [t.get_window_extent(renderer) for t in axis_text]
        obstacles += [legend.get_window_extent(renderer) for legend in fig.legends]
        if any(box.overlaps(other) for other in obstacles):
            note.set_verticalalignment("top")
            note.set_y((min(other.y0 for other in obstacles) - 12) / fig.bbox.height)
    fig.savefig(path, **{**kwargs, "bbox_inches": "tight"})
