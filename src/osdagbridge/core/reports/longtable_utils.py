# =============================================================================
# Longtable post-processing for the OsdagBridge report
# -----------------------------------------------------------------------------
# Every chapter module emits its tables as LaTeX ``longtable`` environments with
# the same shape:
#
#     \begin{longtable}{<colspec>}
#     \caption{...}              (optional)
#     \hline
#     <header row> \\
#     \hline
#     <body rows ...>
#     \end{longtable}
#
# ``process_longtables`` rewrites each of those so that
#   1. the caption and column-header row are emitted with \endfirsthead and the
#      header row (plus a "(continued)" caption) is repeated with \endhead on
#      every following page, and
#   2. rows that belong to one \multirow group are glued together with ``\\*``
#      so a group (for example the rows of one girder) is never split across a
#      page break.
#
# Tables that already define \endhead / \endfirsthead are left untouched.
# Doing this once in a single place keeps the chapter modules free of
# page-break bookkeeping.
# =============================================================================
import re

from osdagbridge.core.reports import styles

_BEGIN = r"\begin{longtable}"
_END = r"\end{longtable}"


def _match_brace(s, i):
    """Return the index just after the brace group that starts at s[i] == '{'."""
    assert s[i] == "{"
    depth = 0
    j = i
    n = len(s)
    while j < n:
        c = s[j]
        if c == "\\":          # skip escaped characters such as \{ \} \\
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return -1


def _row_end(s, start):
    """Index just after the first top-level row terminator ``\\`` (+ optional
    ``*`` and ``[len]``) at or after ``start``; -1 if none."""
    depth = 0
    j = start
    n = len(s)
    while j < n:
        c = s[j]
        if c == "\\":
            if s.startswith("\\\\", j) and depth == 0:
                j += 2
                if j < n and s[j] == "*":
                    j += 1
                m = re.match(r"\[[^\]]*\]", s[j:])
                if m:
                    j += m.end()
                return j
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        j += 1
    return -1


def _split_rows(body):
    """Split ``body`` into [(row_text, terminator)] at top-level ``\\``."""
    rows, pos = [], 0
    while True:
        end = _row_end(body, pos)
        if end == -1:
            tail = body[pos:]
            if tail.strip():
                rows.append((tail, ""))
            break
        term_start = body.rfind("\\\\", pos, end)
        rows.append((body[pos:term_start], body[term_start:end]))
        pos = end
    return rows


def _glue_multirow_groups(body):
    """Replace ``\\\\`` with ``\\\\*`` for rows inside a \\multirow group so
    the group cannot break across pages."""
    rows = _split_rows(body)
    out, glue = [], 0
    for text, term in rows:
        m = re.search(r"\\multirow\{(\d+)\}", text)
        if m:
            glue = max(glue, int(m.group(1)))
        if glue > 1 and term and not term.startswith("\\\\*"):
            term = "\\\\*" + term[2:]
        if glue > 0:
            glue -= 1
        out.append(text + term)
    return "".join(out)


_PT_PER_CM = 28.4528
_COL_WIDTH_RE = re.compile(r"([LCRpmb])\{([0-9]*\.?[0-9]+)(cm|mm)\}")


def _strip_braces(text):
    out, depth = [], 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def _fit_colspec(spec):
    """Scale fixed column widths so the table fits inside the text block.

    Several tables have column widths that add up to more than the page text
    width, which pushes them into the right margin. Widths are shrunk
    proportionally (never enlarged) so cells wrap instead of overflowing.
    """
    inner = _strip_braces(spec[1:-1])
    ncols = len(re.findall(r"[lcrpmbLCRX]", inner))
    matches = list(_COL_WIDTH_RE.finditer(spec))
    if not matches or ncols == 0:
        return spec

    def to_cm(m):
        v = float(m.group(2))
        return v / 10.0 if m.group(3) == "mm" else v

    total_fixed = sum(to_cm(m) for m in matches)
    sep_cm = 2 * float(styles.TABLE_COL_SEP.replace("pt", "")) / _PT_PER_CM
    rule_cm = float(styles.TABLE_RULE_WIDTH.replace("pt", "")) / _PT_PER_CM
    overhead = ncols * sep_cm + (ncols + 1) * rule_cm
    # columns without a fixed width (plain l/c/r) are assumed ~1.5 cm
    loose = ncols - len(matches)
    available = styles.TEXT_WIDTH_CM - overhead - 0.15 - loose * 1.5
    if total_fixed <= available or available <= 0:
        return spec
    factor = available / total_fixed

    def scale(m):
        return "%s{%.2fcm}" % (m.group(1), to_cm(m) * factor)

    return _COL_WIDTH_RE.sub(scale, spec)


def _process_one(block):
    """``block`` is the text between \\begin{longtable} and \\end{longtable}."""
    i = 0
    n = len(block)
    while i < n and block[i] in " \n\t":
        i += 1
    if i >= n or block[i] != "{":
        return block
    spec_end = _match_brace(block, i)
    spec = _fit_colspec(block[i:spec_end])
    rest = block[spec_end:]

    # Tables that already define their own heads keep them; only fit the spec.
    if "\\endhead" in block or "\\endfirsthead" in block:
        return block[:i] + spec + rest

    # optional caption
    caption_text = ""
    caption_raw = ""
    cm = re.match(r"\s*\\caption\s*", rest)
    if cm:
        brace_start = cm.end()
        if brace_start < len(rest) and rest[brace_start] == "{":
            brace_end = _match_brace(rest, brace_start)
            caption_raw = rest[:brace_end]
            caption_text = rest[brace_start + 1: brace_end - 1]
            rest = rest[brace_end:]
            # optional \label directly after the caption
            lm = re.match(r"\s*\\label\{[^}]*\}", rest)
            if lm:
                caption_raw += rest[:lm.end()]
                rest = rest[lm.end():]
            # a trailing \\ after the caption belongs to the caption
            m = re.match(r"\s*\\\\(\[[^\]]*\])?", rest)
            if m:
                caption_raw += rest[:m.end()]
                rest = rest[m.end():]

    # longtable requires the caption row to end with \\ ; the chapter modules
    # omit it, which makes TeX report "Misplaced \omit" and recover on every
    # table. Add it here once.
    if caption_raw and not re.search(r"\\\\(\[[^\]]*\])?\s*$", caption_raw):
        caption_raw = caption_raw.rstrip() + "\\\\"

    # \hline <header row> \hline  -- tables without a header row (for example
    # the per-girder tables whose first row is a \multirow data row) only get
    # their multirow groups glued together.
    def glue_only():
        return spec + _glue_multirow_groups(
            (caption_raw + rest) if caption_raw else rest)

    hm = re.match(r"\s*\\hline\s*", rest)
    if not hm:
        return glue_only()
    header_start = hm.end()
    header_end = _row_end(rest, header_start)
    if header_end == -1:
        return glue_only()
    header_row = rest[header_start:header_end].strip()
    tail = rest[header_end:]
    hm2 = re.match(r"\s*\\hline", tail)
    if not hm2 or "\\multirow" in header_row:
        return glue_only()
    body = tail[hm2.end():]

    shade = ""
    if styles.TABLE_HEADER_SHADE and "\\rowcolor" not in header_row:
        shade = "\\rowcolor{%s} " % styles.TABLE_HEADER_SHADE

    head_core = "\\hline\n%s%s\n\\hline\n" % (shade, header_row)
    first_head = (caption_raw.strip() + "\n" if caption_raw else "") + head_core + "\\endfirsthead\n"
    if caption_text:
        cont_caption = "\\caption[]{%s %s}\\\\\n" % (caption_text, styles.TABLE_CONTINUED_TEXT)
    else:
        cont_caption = ""
    cont_head = cont_caption + head_core + "\\endhead\n"

    return spec + "\n" + first_head + cont_head + _glue_multirow_groups(body.lstrip("\n"))


def process_longtables(tex):
    """Apply repeating headers and multirow gluing to every longtable in ``tex``."""
    out, pos = [], 0
    while True:
        b = tex.find(_BEGIN, pos)
        if b == -1:
            out.append(tex[pos:])
            break
        e = tex.find(_END, b)
        if e == -1:
            out.append(tex[pos:])
            break
        out.append(tex[pos:b])
        inner = tex[b + len(_BEGIN): e]
        out.append(_BEGIN + _process_one(inner))
        pos = e
    return "".join(out)
