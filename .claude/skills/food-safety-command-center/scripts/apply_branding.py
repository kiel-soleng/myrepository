#!/usr/bin/env python3
"""
apply_branding.py — executable first pass over reference/branding.md's
manual checklist for the Food Safety Command Center exemplar.

Usage:
    python3 apply_branding.py \
        --input ../examples/chipotle-exemplar-spec.json \
        --output /path/to/branded-spec.json \
        --customer-name "Big Sky Grill" \
        --brand-hex "#1f6f4a" \
        [--logo-url https://.../logo.svg] \
        [--texture-url https://.../texture.svg]   # omit to drop decorative texture \
        [--font-family "Inter"]                   # omit to use theme default, not Gotham \
        [--compliance-url https://... --compliance-label "..."]

Only performs the substitutions `reference/branding.md` marks as safe for
an automated pass (see that file's "Practical recipe for a new customer"
and the JSON-key safety table in its §2). Everything that doc explicitly
requires individual judgment on — semantic risk/status colors, the
Risk Profile Report's own separate branding pass, the report-embed URLs
that point at the *existing* Chipotle Report resource — is left untouched
and reported at the end under "MANUAL REVIEW STILL NEEDED", not guessed.

Does NOT wire in customer data sources (that happens after the CSV
upload step, once real element ids exist for the uploaded tables — see
reference/data-seeding.md). This script is branding only.

Note on dates: the exemplar's Current/Prior Week/Month period logic is
already computed by each Custom SQL table as `MAX(date column) FROM
<table>`, not a hardcoded literal date — see the "MAX(date)-relative SQL
pattern" note in reference/data-seeding.md. This script does not need to
(and does not) rewrite any date formulas; that pattern must simply be
preserved (never replaced with a literal date) when a later step rewires
these tables to the customer's own data.
"""
import argparse
import json
import re

# Confirmed clean brand-red hex per branding.md §2 — every occurrence in the
# exemplar sits under a plain `color`/`name.color` key, never a semantic one.
CLEAN_BRAND_HEX = "#a81712"

# The 6 decorative background-texture elements named in branding.md §4.
TEXTURE_ELEMENT_IDS = [
    "ug36f8WhFL", "CafGDFhOFO", "ymFZTtQ1D4",
    "3UJGdXWX9D", "0Jp3vChmAM", "XVexK_rOb4",
]

LOGO_ELEMENT_ID = "xc-logo"

# Elements whose text/formula body contains the literal company name,
# located by walking the exemplar for "chipotle" (case-insensitive) and
# recording the enclosing element id (see history.md 2026-09-28 entry for
# how this list was produced) — not a blind whole-spec find/replace.
COMPANY_NAME_TEXT_ELEMENT_IDS = [
    "xc-ai-tx",     # Exec Command Center AI-narrative static text
    "86WI_CaLjc",   # CallText(...) formula body, Exec Command Center
    "tzgXfV-q4K",   # CallText(...) formula body, Manager Report
    "L6mVTEw_Nt",   # Manager Report static header ("Chipotle #1002")
    "rgytWBhfBX",   # Attestation disclaimer text
]

COMPLIANCE_LINK_ELEMENT_ID = "_D_dTcDI2K"

# Report-embed elements that point at the *existing* Chipotle companion
# Report resource by its live Sigma URL slug — out of scope for this
# script (see branding.md §5); flagged, never auto-rewritten.
REPORT_EMBED_ELEMENT_IDS = ["4Q2ISmPwUl", "qS155Dvj84"]


class BrandingResult:
    def __init__(self):
        self.applied = []
        self.manual_review = []

    def note(self, msg):
        self.applied.append(msg)

    def flag(self, msg):
        self.manual_review.append(msg)


def find_element(elements, element_id):
    for e in elements:
        if e.get("id") == element_id:
            return e
    return None


def apply_theme_colors(doc, brand_hex, result):
    settings = doc.setdefault("settings", {})
    theme = settings.setdefault("theme", {})
    theme.pop("name", None)  # org-scoped theme id won't resolve for a new org
    overrides = theme.setdefault("overrides", {})
    colors = overrides.setdefault("colors", {})
    colors["highlight"] = brand_hex
    result.note(f"theme.overrides.colors.highlight -> {brand_hex}")
    for semantic in ("success", "warning", "danger"):
        if semantic in colors:
            result.note(f"left theme.overrides.colors.{semantic} untouched (semantic)")


def replace_clean_hex(obj, brand_hex, result):
    """Walk the whole document and replace the one confirmed-clean brand hex
    wherever it appears as a literal substring, case-insensitively. Every
    other hex is left alone -- see branding.md SS2 for why a blind
    hex-family replace is unsafe."""
    pattern = re.compile(re.escape(CLEAN_BRAND_HEX), re.IGNORECASE)
    count = 0

    def walk(o):
        nonlocal count
        if isinstance(o, dict):
            for k, v in list(o.items()):
                o[k] = walk(v)
            return o
        if isinstance(o, list):
            return [walk(v) for v in o]
        if isinstance(o, str) and pattern.search(o):
            count += 1
            return pattern.sub(brand_hex, o)
        return o

    walk(obj)
    result.note(f"replaced {CLEAN_BRAND_HEX} -> {brand_hex} at {count} location(s)")


def apply_company_name(doc, customer_name, result):
    elements = doc.get("elements", [])
    for eid in COMPANY_NAME_TEXT_ELEMENT_IDS:
        e = find_element(elements, eid)
        if e is None:
            result.flag(f"company-name element '{eid}' not found -- exemplar may have changed, check by hand")
            continue
        if "body" in e and isinstance(e["body"], str):
            before = e["body"]
            e["body"] = re.sub(r"Chipotle", customer_name, before)
            if before != e["body"]:
                result.note(f"replaced company name in element '{eid}' body")

    agents = doc.get("agents", [])
    for i, agent in enumerate(agents):
        instr = agent.get("instructions", "")
        if "chipotle" in instr.lower():
            agent["instructions"] = re.sub(r"Chipotle", customer_name, instr)
            result.note(f"replaced company name in agents[{i}].instructions")

    result.flag(
        "report-embed elements "
        f"{REPORT_EMBED_ELEMENT_IDS} still point at the existing Chipotle companion "
        "Report resource -- rebrand + republish that Report separately (branding.md SS5) "
        "before repointing these"
    )


def apply_compliance_link(doc, customer_name, compliance_url, compliance_label, result):
    elements = doc.get("elements", [])
    e = find_element(elements, COMPLIANCE_LINK_ELEMENT_ID)
    if e is None or "body" not in e:
        result.flag(f"could not find compliance-link element '{COMPLIANCE_LINK_ELEMENT_ID}'")
        return
    if not compliance_url:
        result.flag(
            f"element '{COMPLIANCE_LINK_ELEMENT_ID}' left pointed at chipotle.com/food-safety "
            "-- no --compliance-url given; must be fixed before publishing to this customer"
        )
        return
    label = compliance_label or f"{customer_name} Food Safety Standards and Procedures"
    e["body"] = re.sub(
        r"\[.*?\]\(https://www\.chipotle\.com/food-safety[^)]*\)",
        f'[{label}]({compliance_url} "{label}")',
        e["body"],
    )
    result.note(f"compliance link -> {compliance_url}")


def apply_logo(doc, logo_url, result):
    elements = doc.get("elements", [])
    e = find_element(elements, LOGO_ELEMENT_ID)
    if e is None:
        result.flag(f"logo element '{LOGO_ELEMENT_ID}' not found")
        return
    if logo_url:
        e["source"]["url"] = logo_url
        result.note(f"xc-logo source.url -> {logo_url}")
    else:
        result.flag(f"element '{LOGO_ELEMENT_ID}' left pointed at the Chipotle logo -- no --logo-url given")


def apply_texture(doc, texture_url, result):
    elements = doc.get("elements", [])
    for eid in TEXTURE_ELEMENT_IDS:
        e = find_element(elements, eid)
        if e is None:
            result.flag(f"texture element '{eid}' not found -- exemplar may have changed")
            continue
        if texture_url:
            e["backgroundImage"]["source"]["url"] = texture_url
        else:
            e.pop("backgroundImage", None)
    if texture_url:
        result.note(f"backgroundImage texture -> {texture_url} on {len(TEXTURE_ELEMENT_IDS)} element(s)")
    else:
        result.note(f"removed backgroundImage (falls back to backgroundColor) on {len(TEXTURE_ELEMENT_IDS)} element(s)")


def apply_font(doc, font_family, result):
    if font_family:
        elements = doc.get("elements", [])
        count = 0
        for e in elements:
            body = e.get("body")
            if isinstance(body, str) and "font-family: Gotham" in body:
                e["body"] = body.replace("font-family: Gotham", f"font-family: {font_family}")
                count += 1
        result.note(f"replaced inline font-family: Gotham -> {font_family} on {count} element(s)")
    else:
        result.flag(
            "font left at theme default (Gotham inline spans NOT removed -- Gotham may not be "
            "licensed for this org; pass --font-family to set one explicitly, or manually clear "
            "the inline font-family spans to fall back to the theme default)"
        )


def grep_company_name(doc, allow_element_ids):
    """Self-check: any remaining 'chipotle' hit outside explicitly-deferred
    locations means something was missed."""
    hits = []

    def walk(obj, element_id):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v, element_id)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, element_id)
        elif isinstance(obj, str) and "chipotle" in obj.lower():
            hits.append((element_id, obj[:120]))

    for e in doc.get("elements", []):
        if e.get("id") in allow_element_ids:
            continue
        walk(e, e.get("id"))
    for a in doc.get("agents", []):
        walk(a, "agent")
    return hits


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--customer-name", required=True)
    p.add_argument("--brand-hex", required=True, help='e.g. "#1f6f4a"')
    p.add_argument("--logo-url", default=None)
    p.add_argument("--texture-url", default=None, help="omit to drop the decorative background texture")
    p.add_argument("--font-family", default=None, help="omit to use the theme default instead of Gotham")
    p.add_argument("--compliance-url", default=None)
    p.add_argument("--compliance-label", default=None)
    return p.parse_args()


def main():
    args = parse_args()
    with open(args.input) as f:
        raw = json.load(f)
    doc = raw["document"] if "document" in raw else raw

    result = BrandingResult()
    apply_theme_colors(doc, args.brand_hex, result)
    replace_clean_hex(doc, args.brand_hex, result)
    apply_logo(doc, args.logo_url, result)
    apply_texture(doc, args.texture_url, result)
    apply_company_name(doc, args.customer_name, result)
    apply_compliance_link(doc, args.customer_name, args.compliance_url, args.compliance_label, result)
    apply_font(doc, args.font_family, result)

    with open(args.output, "w") as f:
        json.dump(raw, f)

    allow = set(REPORT_EMBED_ELEMENT_IDS)
    if not args.compliance_url:
        allow.add(COMPLIANCE_LINK_ELEMENT_ID)
    if not args.logo_url:
        allow.add(LOGO_ELEMENT_ID)
    if not args.texture_url:
        pass  # texture URLs are removed, not left as "chipotle" text
    hits = grep_company_name(doc, allow)

    print(f"Wrote {args.output}\n")
    print("Applied:")
    for m in result.applied:
        print(" -", m)
    print("\nMANUAL REVIEW STILL NEEDED:")
    for m in result.manual_review:
        print(" -", m)
    if hits:
        print(f"\nWARNING: {len(hits)} unexpected 'chipotle' mention(s) survived outside deferred locations:")
        for eid, snippet in hits:
            print(f"   [{eid}] {snippet}")
    else:
        print("\nCompany-name grep: clean (zero hits outside explicitly deferred locations).")


if __name__ == "__main__":
    main()
