# =============================================================================
# OsdagBridge Report Style System  (single source of truth)
# -----------------------------------------------------------------------------
# Every layout rule and visual attribute used by the report generator lives in
# this module: page geometry, fonts, colour palette, table padding, header /
# footer themes and chart styling.  Chapter generators and the preamble import
# from here instead of hard-coding values, so a global look-and-feel change is
# a one-line edit.
#
# Sections
#   1. Document          - class, font size, line spacing, page geometry
#   2. Colours           - palette shared by LaTeX and matplotlib
#   3. Tables            - padding, rules, row height, page-break thresholds
#   4. Header / footer   - fancyhdr page styles
#   5. Charts            - matplotlib theme and figure sizes
#   6. LaTeX builders    - functions that turn the constants above into LaTeX
# =============================================================================

# ── 1. Document ──────────────────────────────────────────────────────────────
DOCUMENT_CLASS = "report"
DOCUMENT_OPTIONS = "12pt,a4paper"
LINE_STRETCH = 1.15

# Page geometry. The bottom margin and footskip are larger than the LaTeX
# defaults so table rows and figures never run into the footer rule.
PAGE_MARGIN_LEFT = "1in"
PAGE_MARGIN_RIGHT = "1in"
PAGE_MARGIN_TOP = "1in"
PAGE_MARGIN_BOTTOM = "1.2in"
HEADER_SEP = "0.3in"
FOOT_SKIP = "0.5in"

PAGE_WIDTH_CM = 21.0                 # A4
PAGE_MARGIN_SIDE_CM = 2.54           # 1in; keep in sync with PAGE_MARGIN_LEFT/RIGHT
TEXT_WIDTH_CM = PAGE_WIDTH_CM - 2 * PAGE_MARGIN_SIDE_CM

# ── 2. Colours ───────────────────────────────────────────────────────────────
# name -> hex (no leading '#').  Registered in LaTeX with \definecolor and
# reused by the charts so the PDF and the plots share one palette.
COLORS = {
    "osdagGreen": "91B014",
    "passGreen": "4C8C2B",
    "failRed": "D62728",
    "steelBlue": "3B6EA8",
    "concreteGrey": "8C8C8C",
    "rebarOrange": "D98324",
    "tableHeader": "EEF3D8",
}


def color_hex(name):
    """Return '#RRGGBB' for a palette colour (for matplotlib)."""
    return "#" + COLORS[name]


# ── 3. Tables ────────────────────────────────────────────────────────────────
TABLE_COL_SEP = "6pt"
TABLE_ARRAY_STRETCH = 1.12
TABLE_RULE_WIDTH = "0.5pt"
TABLE_EXTRA_ROW_HEIGHT = "0.6pt"
LONGTABLE_PRE = "0pt"
LONGTABLE_POST = "6pt"
# If fewer than this many baseline-skips remain on the page, a (float) table
# starts on the next page instead of splitting immediately.
TABLE_NEEDSPACE_BASELINES = 6
# Shade applied to repeated header rows (None disables shading).
TABLE_HEADER_SHADE = "tableHeader"
# Text appended to a table caption on continuation pages.
TABLE_CONTINUED_TEXT = r"\textit{(continued)}"

# ── 4. Header / footer ───────────────────────────────────────────────────────
FOOTER_LEFT = r"Osdag $|$ FOSSEE $|$ Indian Institute of Technology Bombay"
FOOTER_RIGHT = r"Page \thepage\ of \pageref{LastPage}"
HEADER_RULE_WIDTH = "1pt"
FOOTER_RULE_WIDTH = "1pt"
SOFTWARE_DEFAULT_NOTE = r"* Software default value"

# ── 5. Charts ────────────────────────────────────────────────────────────────
CHART_DPI = 200
CHART_FIGSIZE_WIDE = (7.4, 3.6)      # inches; fits the 6.27in text width
CHART_FIGSIZE_HALF = (3.6, 3.2)
CHART_FONT_SIZE = 8.5
CHART_THRESHOLD_COLOR = "failRed"
CHART_THRESHOLD_LABEL = "UR = 1.0 (limit)"
CHART_FIGURE_WIDTH = r"0.95\textwidth"
CHART_FIGURE_WIDTH_SMALL = r"0.55\textwidth"   # for the narrow quantity charts


def apply_chart_theme():
    """Apply the shared matplotlib theme. Safe to call repeatedly."""
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.size": CHART_FONT_SIZE,
        "axes.titlesize": CHART_FONT_SIZE + 1,
        "axes.labelsize": CHART_FONT_SIZE,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "-",
        "axes.axisbelow": True,
        "legend.frameon": False,
        "figure.dpi": CHART_DPI,
        "savefig.dpi": CHART_DPI,
        "savefig.bbox": "tight",
    })
    return plt


# ── 6. LaTeX builders ────────────────────────────────────────────────────────
def color_definitions():
    return "\n".join(
        r"\definecolor{%s}{HTML}{%s}" % (n, h) for n, h in COLORS.items()
    )


def geometry_line():
    return (
        r"\usepackage[a4paper, left=%s, right=%s, top=%s, bottom=%s, "
        r"headsep=%s, footskip=%s]{geometry}"
        % (PAGE_MARGIN_LEFT, PAGE_MARGIN_RIGHT, PAGE_MARGIN_TOP,
           PAGE_MARGIN_BOTTOM, HEADER_SEP, FOOT_SKIP)
    )


# \cline is a one-line mini row, and LaTeX allows a page break right after it.
# That defeats \\* inside \multirow groups (a girder's rows could split across
# pages). This redefinition adds penalties so no break can occur after \cline.
CLINE_NO_BREAK_FIX = r"""
\makeatletter
\def\@cline#1-#2\@nil{\omit\@multicnt#1\advance\@multispan\m@ne
 \ifnum\@multicnt=\@ne\@firstofone{&\omit}\fi
 \@multicnt#2\advance\@multicnt-#1\advance\@multispan\@ne
 \leaders\hrule\@height\arrayrulewidth\hfill
 \cr
 \noalign{\penalty\@M\vskip-\arrayrulewidth\penalty\@M}}
\makeatother
"""


def table_layout_block():
    """Global table padding, rules and page-bottom threshold."""
    block = r"""
% Table layout and spacing (values come from styles.py)
\setlength{\tabcolsep}{@COLSEP@}
\renewcommand{\arraystretch}{@STRETCH@}
\setlength{\LTpre}{@LTPRE@}
\setlength{\LTpost}{@LTPOST@}
\setlength{\arrayrulewidth}{@RULE@}
\setlength{\extrarowheight}{@EXTRA@}

% If fewer than @NEED@ baseline-skips remain, a float table starts on the next page.
% (longtable manages its own page breaks; a needspace hook there conflicts with
% the repeated header rows.)
\BeforeBeginEnvironment{table}{\needspace{@NEED@\baselineskip}}
"""
    block += CLINE_NO_BREAK_FIX
    for token, value in (("@COLSEP@", TABLE_COL_SEP), ("@STRETCH@", TABLE_ARRAY_STRETCH),
                         ("@LTPRE@", LONGTABLE_PRE), ("@LTPOST@", LONGTABLE_POST),
                         ("@RULE@", TABLE_RULE_WIDTH), ("@EXTRA@", TABLE_EXTRA_ROW_HEIGHT),
                         ("@NEED@", TABLE_NEEDSPACE_BASELINES)):
        block = block.replace(token, str(value))
    return block


def page_styles_block(project_name, job_number, report_date, report_version):
    """fancyhdr styles: 'main', 'plain' (same look) and 'firstpage'."""
    footrule = r"""\renewcommand{\footrule}{%
    \ifbool{hasSDonPage}{%
      \vspace{-20pt}%
      \hbox to \headwidth{\textcolor{black}{\footnotesize\textit{""" + SOFTWARE_DEFAULT_NOTE + r"""}}\hfil}%
      \vspace{4pt}%
    }{%
      \vspace{-8pt}%
    }%
    \color{osdagGreen}\hrule width\headwidth height """ + FOOTER_RULE_WIDTH + r""" \vspace{6pt}%
  }"""

    def body(name):
        return r"""\fancypagestyle{%s}{
  \fancyhf{}
  \fancyhead[L]{%s $|$ %s}
  \fancyhead[R]{%s $|$ %s}
  \fancyfoot[L]{%s}
  \fancyfoot[R]{%s}
  \renewcommand{\headrule}{\color{osdagGreen}\hrule width\headwidth height %s \vspace{2pt}}
  %s
}""" % (name, project_name, job_number, report_date, report_version,
        FOOTER_LEFT, FOOTER_RIGHT, HEADER_RULE_WIDTH, footrule)

    first = r"""\fancypagestyle{firstpage}{
  \fancyhf{}
  \renewcommand{\headrulewidth}{0pt}
  \fancyfoot[L]{%s}
  \fancyfoot[R]{%s}
  \renewcommand{\footrule}{\vspace{-8pt}\color{osdagGreen}\hrule width\headwidth height %s \vspace{6pt}}
}""" % (FOOTER_LEFT, FOOTER_RIGHT, FOOTER_RULE_WIDTH)

    return "\n".join([body("main"), body("plain"), first])
