"""Shared aesthetic system for sigma-office-of-finance page builders.

Ported from sigma-input-table-app's verified "restrained light +
comparison-delta KPI" system (SKILL.md -> "Aesthetics — restrained, light,
element-level"). That skill's Rolling Forecast pattern is already a
dependency of this one, and unlike sigma-company-dashboard-v2 (bank/lending-
branding-specific: 14 hardcoded companies, PDF/logo/plugin machinery tied to
a different org) its aesthetic system is generic and verified against
staging. Deliberately NOT porting sigma-company-dashboard-v2's brand.py.

These are style *fragments* — dicts merged into each page builder's own
element-construction helpers, not a full element-building API. Each page
keeps control of its own source/column wiring (correctness-critical,
page-specific); this module only supplies the "look."
"""

# Accent palette — per sigma-input-table-app SKILL.md "Aesthetics".
NAVY = "#1e3558"          # header/toolbar/accent-card border
TEAL_GOOD = "#3bb5b3"     # comparison-delta "good" color
CORAL_BAD = "#ee465c"     # comparison-delta "bad" color
LIGHT_GREY = "#f7f7f7"    # secondary card background
WHITE = "#ffffff"
BORDER = "#e3e3e3"

# "Barely-there theme" — per-page pageWidth (2026-08 schema: pageWidth moved
# onto the page object itself, not a top-level themeOverrides field).
PAGE_WIDTH = "large"

# Number/date format objects (specification/formatting.md d3-format strings).
CURRENCY_FMT = {"kind": "number", "formatString": "$.3~s"}          # $1.2M style
CURRENCY_FULL_FMT = {"kind": "number", "formatString": "$,.0f"}      # $1,234,567
PERCENT_FMT = {"kind": "number", "formatString": ",.1%"}
DELTA_PERCENT_FMT = {"kind": "number", "formatString": "+,.1%"}
INT_FMT = {"kind": "number", "formatString": ",.0f"}
MONTH_FMT = {"kind": "datetime", "formatString": "%b %Y"}
DATE_FMT = {"kind": "datetime", "formatString": "%b %d, %Y"}


def card_style(accent=False):
    """Pill-radius card style for containers and KPI/table `style` fields.

    accent=True -> primary card: white bg, navy border, heavier weight.
    accent=False -> secondary card: light-grey bg, subtle border.
    """
    if accent:
        return {"backgroundColor": WHITE, "borderRadius": "pill",
                "borderColor": NAVY, "borderWidth": 2}
    return {"backgroundColor": LIGHT_GREY, "borderRadius": "pill",
            "borderColor": BORDER, "borderWidth": 1}


def header_style():
    """Navy header/toolbar band — for the page's title/control container."""
    return {"backgroundColor": NAVY, "borderRadius": "round"}


def kpi_name(text):
    """Styled-name object for a KPI card title."""
    return {"text": text, "fontSize": 16, "color": NAVY}


def kpi_comparison(good_is_high=True):
    """comparison-delta shape for a kpi-chart element.

    Pair with a period (date) column in the KPI's `columns` for automatic
    period-over-period delta, OR with `comparisonColumn` pointed at a
    sibling baseline column for an explicit vs.-baseline delta — see
    sigma-input-table-app SKILL.md "Verified shape gotchas" ->
    "Comparison-delta KPI vs a baseline sibling."

    good_is_high=True: an increase reads good (teal), a decrease reads bad
    (coral) — e.g. Revenue, Total Forecast. Set False for cost/expense
    lines where an increase reads bad (over-budget spend).
    """
    return {
        "display": "delta",
        "colorGood": TEAL_GOOD if good_is_high else CORAL_BAD,
        "colorBad": CORAL_BAD if good_is_high else TEAL_GOOD,
        "fontSize": 14,
    }


def title_body(text, subtitle=None, color=WHITE):
    """Markdown body for a page title text element.

    Default color is WHITE for use inside the navy header container
    (see `header_style()`) — per sigma-input-table-app's "light theme
    base, dark accents" rule (#5): the header/toolbar band is the one
    place that's filled dark, so its text must be light, not navy-on-navy.
    Pass color=NAVY for a title placed directly on a light/white page.

    Only documented text-element markup used here (specification/text.md):
    a heading, bold, and `<span style="color:...">` — no undocumented
    `<p style="color:...">` shape.
    """
    body = f'# **<span style="color: {color}">{text}</span>**'
    if subtitle:
        body += f'\n\n<p class="p-small"><span style="color: {color}">{subtitle}</span></p>'
    return body
