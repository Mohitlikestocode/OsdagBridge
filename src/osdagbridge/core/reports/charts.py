# =============================================================================
# Report charts
# -----------------------------------------------------------------------------
# Matplotlib figures embedded in the design report:
#   * Section 5.5  - utilization ratio (UR = Demand / Capacity) charts
#   * Chapter 7    - material quantity charts (steel tonnage, concrete vs rebar)
#
# Each ``make_*`` function writes PNG files into ``out_dir`` (a temporary
# directory owned by the report generator, deleted after compilation) and
# returns the file paths.  ``figure_tex`` turns a path into a LaTeX figure.
# All colours, sizes and fonts come from ``styles``.
# =============================================================================
import os
import re
import logging

from osdagbridge.core.reports import styles

logger = logging.getLogger(__name__)

# Element groups used for the UR charts, in display order.
GROUP_GIRDER = "Steel Plate Girders"
GROUP_DECK = "Concrete Deck Slab"
GROUP_BRACING = "Cross Bracing"
GROUP_DIAPHRAGM = "End Diaphragms"
GROUP_ORDER = [GROUP_GIRDER, GROUP_DECK, GROUP_BRACING, GROUP_DIAPHRAGM]
GROUP_COLORS = {
    GROUP_GIRDER: "steelBlue",
    GROUP_DECK: "concreteGrey",
    GROUP_BRACING: "rebarOrange",
    GROUP_DIAPHRAGM: "passGreen",
}


def group_for_label(label):
    """Map a Table 5.22 row label to one of the four element groups."""
    lab = str(label)
    if lab.startswith("Girder"):
        return GROUP_GIRDER
    if lab.startswith("Cross Bracing"):
        return GROUP_BRACING
    if lab.startswith("End Diaphragm"):
        return GROUP_DIAPHRAGM
    if "slab" in lab.lower() or lab.startswith("Deck"):
        return GROUP_DECK
    return None


def parse_ur(cell):
    """Extract the numeric UR from a table cell such as
    ``\\textcolor{red}{1.02}`` or ``0.87``. Returns None for N/A cells."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(cell).replace("\\textcolor{red}", ""))
    return float(m.group()) if m else None


def _clean_label(label):
    """Strip LaTeX dashes so labels read well on a chart axis."""
    return (str(label).replace(r"\,", " ").replace("---", "-")
            .replace(r"\_", "_").replace("  ", " ").strip())


def _value_label(ax, x, u, size=7, bold=False):
    """Bar value label. Placed inside the bar when it would sit on the UR = 1.0
    line (0.90 <= UR <= 1.0), otherwise just above the bar."""
    weight = "bold" if bold else "normal"
    if 0.90 <= u <= 1.0:
        ax.text(x, u - 0.02, "%.2f" % u, ha="center", va="top", fontsize=size,
                color="white", fontweight=weight)
    else:
        ax.text(x, u + 0.015, "%.2f" % u, ha="center", va="bottom", fontsize=size,
                fontweight=weight)


def _threshold(ax):
    ax.axhline(1.0, color=styles.color_hex(styles.CHART_THRESHOLD_COLOR),
               linestyle="--", linewidth=1.4, zorder=3,
               label=styles.CHART_THRESHOLD_LABEL)


def figure_tex(path, caption, label=None, width=None):
    """LaTeX figure environment for a PNG that sits next to the .tex file."""
    p = path.replace("\\", "/")
    lab = (r"\label{%s}" % label) if label else ""
    return (r"\begin{figure}[H]" + "\n"
            r"\centering" + "\n"
            r"\includegraphics[width=" + (width or styles.CHART_FIGURE_WIDTH) + "]{" + p + "}\n"
            r"\caption{" + caption + "}" + lab + "\n"
            r"\end{figure}" + "\n")


# ── Utilization ratio charts (Section 5.5) ──────────────────────────────────
def make_ur_charts(records, out_dir):
    """Create the UR charts.

    ``records`` is a list of ``(group, label, ur)`` with ``ur`` a float or None.
    Returns ``{"ur_checks": path, "ur_governing": path}`` (keys missing when
    there is no data to plot).
    """
    data = [(g, _clean_label(l), u) for g, l, u in records if g and u is not None]
    if not data:
        return {}
    plt = styles.apply_chart_theme()
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    os.makedirs(out_dir, exist_ok=True)
    out = {}
    fail = styles.color_hex("failRed")
    thr_handle = Line2D([0], [0], color=fail, linestyle="--", linewidth=1.4,
                        label=styles.CHART_THRESHOLD_LABEL)

    # Chart 1: every check, grouped by element.
    data.sort(key=lambda r: GROUP_ORDER.index(r[0]))
    fig, ax = plt.subplots(figsize=styles.CHART_FIGSIZE_WIDE)
    xs = range(len(data))
    for i, (g, lab, u) in zip(xs, data):
        failing = u > 1.0
        ax.bar(i, u, width=0.7,
               color=fail if failing else styles.color_hex(GROUP_COLORS[g]),
               edgecolor="black" if failing else "none", linewidth=0.8, zorder=2)
        _value_label(ax, i, u, size=7)
    _threshold(ax)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([d[1] for d in data], rotation=40, ha="right", fontsize=7)
    ax.set_ylabel("Utilization Ratio (Demand / Capacity)")
    ax.set_ylim(0, max(1.15, max(d[2] for d in data) * 1.12))
    present = [g for g in GROUP_ORDER if any(d[0] == g for d in data)]
    handles = [Patch(color=styles.color_hex(GROUP_COLORS[g]), label=g) for g in present]
    if any(d[2] > 1.0 for d in data):
        handles.append(Patch(color=fail, label="Fails (UR > 1.0)"))
    ax.legend(handles=handles + [thr_handle], ncol=3, loc="upper center",
              bbox_to_anchor=(0.5, 1.2), fontsize=7.5)
    p = os.path.join(out_dir, "ur_checks.png")
    fig.savefig(p)
    plt.close(fig)
    out["ur_checks"] = p

    # Chart 2: governing (maximum) UR per element.
    gov = {}
    for g, lab, u in data:
        if g not in gov or u > gov[g][0]:
            gov[g] = (u, lab)
    fig, ax = plt.subplots(figsize=styles.CHART_FIGSIZE_WIDE)
    names = [g for g in GROUP_ORDER if g in gov]
    for i, g in enumerate(names):
        u = gov[g][0]
        failing = u > 1.0
        ax.bar(i, u, width=0.55,
               color=fail if failing else styles.color_hex(GROUP_COLORS[g]),
               edgecolor="black" if failing else "none", linewidth=0.8, zorder=2)
        _value_label(ax, i, u, size=8, bold=True)
    _threshold(ax)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(["%s\n(%s)" % (g, gov[g][1]) for g in names], fontsize=7.5)
    ax.set_ylabel("Governing Utilization Ratio")
    ax.set_ylim(0, max(1.15, max(v[0] for v in gov.values()) * 1.12))
    ax.legend(handles=[thr_handle], loc="upper right", fontsize=7.5)
    p = os.path.join(out_dir, "ur_governing.png")
    fig.savefig(p)
    plt.close(fig)
    out["ur_governing"] = p
    return out


# ── Material quantity charts (Chapter 7) ────────────────────────────────────
def _num(value):
    """Float from a quantity string; None for 'N.A.' / empty / placeholders."""
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def steel_quantities(q):
    """Structural steel tonnage per component as ``[(label, MT or None)]``."""
    parts = [q.get("bracing_top_wt_total"), q.get("bracing_bot_wt_total"),
             q.get("bracing_diag_wt_total")]
    nums = [_num(v) for v in parts]
    bracing = sum(n for n in nums if n is not None) if any(n is not None for n in nums) else None
    return [
        ("Girders", _num(q.get("steel_girders_wt_total"))),
        ("Cross Bracing", bracing),
        ("End Diaphragms", _num(q.get("end_diaphragm_wt_total"))),
    ]


def make_quantity_charts(q, out_dir):
    """Create the Chapter 7 charts from the quantity dict.

    Returns ``{"qty_steel": path, "qty_concrete_rebar": path}`` (keys missing
    when the numbers needed are not available).
    """
    plt = styles.apply_chart_theme()
    os.makedirs(out_dir, exist_ok=True)
    out = {}
    steel_c = styles.color_hex("steelBlue")

    # Chart 1: structural steel tonnage.
    steel = steel_quantities(q)
    if any(v is not None for _, v in steel):
        fig, ax = plt.subplots(figsize=styles.CHART_FIGSIZE_HALF)
        labels = [l for l, _ in steel]
        vals = [v if v is not None else 0.0 for _, v in steel]
        bars = ax.bar(labels, vals, color=steel_c, width=0.6, zorder=2)
        top = max(vals) if max(vals) > 0 else 1.0
        for b, (lab, v) in zip(bars, steel):
            txt = "%.2f" % v if v is not None else "n/a"
            ax.text(b.get_x() + b.get_width() / 2, (v or 0) + top * 0.02, txt,
                    ha="center", va="bottom", fontsize=8)
        ax.set_ylabel("Structural steel (MT)")
        ax.set_ylim(0, top * 1.18)
        ax.set_title("Structural steel tonnage")
        fig.tight_layout()
        p = os.path.join(out_dir, "qty_steel.png")
        fig.savefig(p)
        plt.close(fig)
        out["qty_steel"] = p

    # Chart 2: concrete volume vs reinforcement weight (two panels, own units).
    conc = _num(q.get("concrete_deck_vol_total"))
    rebar = _num(q.get("rebar_deck_wt_total"))
    if conc is not None and rebar is not None:
        fig, (a1, a2) = plt.subplots(1, 2, figsize=styles.CHART_FIGSIZE_HALF)
        a1.bar(["Concrete"], [conc], color=styles.color_hex("concreteGrey"), width=0.5, zorder=2)
        a1.text(0, conc * 1.02, "%.2f" % conc, ha="center", va="bottom", fontsize=8)
        a1.set_ylabel("Volume (m$^3$)")
        a1.set_ylim(0, conc * 1.18 if conc > 0 else 1)
        a2.bar(["Reinforcement"], [rebar], color=styles.color_hex("rebarOrange"), width=0.5, zorder=2)
        a2.text(0, rebar * 1.02, "%.2f" % rebar, ha="center", va="bottom", fontsize=8)
        a2.set_ylabel("Weight (MT)")
        a2.set_ylim(0, rebar * 1.18 if rebar > 0 else 1)
        density = (rebar * 1000.0 / conc) if conc > 0 else None
        title = "Concrete volume vs reinforcement weight"
        if density is not None:
            title += "\n(%.0f kg of steel per m$^3$ of concrete)" % density
        fig.suptitle(title, fontsize=styles.CHART_FONT_SIZE + 0.5)
        fig.tight_layout()
        p = os.path.join(out_dir, "qty_concrete_rebar.png")
        fig.savefig(p)
        plt.close(fig)
        out["qty_concrete_rebar"] = p
    return out
