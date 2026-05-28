"""Theme palettes + CSS-variable injection.

The app supports 4 theme preferences:
  - "system"             -- follow OS / browser prefers-color-scheme
  - "light"              -- explicit light
  - "dark_slate"         -- comfortable dark, the default dark choice
  - "dark_high_contrast" -- deeper dark, punchier feedback colors

Each palette is exposed as CSS custom properties (--bg, --surface, --text,
--muted, --accent, --correct-text, --correct-bg, --incorrect-text,
--incorrect-bg, --border). `app/styles.py` consumes those variables, so a
theme switch just re-injects the variable block -- no rebuild of the
component-level CSS.

Single source of truth: any new palette goes here, not scattered hex
values across pages.
"""
from __future__ import annotations

from typing import Literal

ThemePreference = Literal["system", "light", "dark_slate", "dark_high_contrast"]

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK_SLATE = "dark_slate"
THEME_DARK_HC = "dark_high_contrast"

VALID_THEMES: tuple[str, ...] = (
    THEME_SYSTEM,
    THEME_LIGHT,
    THEME_DARK_SLATE,
    THEME_DARK_HC,
)

THEME_LABELS: dict[str, str] = {
    THEME_SYSTEM: "System default",
    THEME_LIGHT: "Light",
    THEME_DARK_SLATE: "Dark - Neutral Slate",
    THEME_DARK_HC: "Dark - High Contrast",
}


# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
# Invariants to preserve when tweaking:
#   - never use pure #000000 backgrounds or pure #FFFFFF text
#   - never use fully saturated red/green for feedback rows
# ---------------------------------------------------------------------------


LIGHT_PALETTE: dict[str, str] = {
    "bg":             "#F9FAFB",
    "surface":        "#FFFFFF",
    "surface-2":      "#F3F4F6",   # subtle accent surface
    "text":           "#111827",
    "muted":          "#6B7280",
    "accent":         "#FF9900",
    "accent-text":    "#3D2600",
    "accent-strong":  "#2563EB",   # legacy "primary blue" -- buttons, charts
    "accent-strong-hover": "#1D4ED8",
    "correct-text":   "#065F46",
    "correct-bg":     "#ECFDF5",
    "correct-border": "#10B981",
    "incorrect-text": "#991B1B",
    "incorrect-bg":   "#FEF2F2",
    "incorrect-border": "#EF4444",
    "border":         "#E5E7EB",
    "input-bg":       "#FFFFFF",
    "input-bg-hover": "#FAFAFA",
    "shadow":         "0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.03)",
    "shadow-hover":   "0 4px 12px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04)",
    "stat-block-bg":  "linear-gradient(135deg, #0F172A 0%, #1E293B 100%)",
    "stat-block-text": "#FFFFFF",
    "stat-block-muted": "#94A3B8",
    "github-fill":    "%23111827",
}


DARK_SLATE_PALETTE: dict[str, str] = {
    "bg":             "#1A1D23",
    "surface":        "#22262E",
    "surface-2":      "#2A2E37",
    "text":           "#E8EAED",
    "muted":          "#B4BAC2",
    # Dark-mode accent is AWS console blue (#4F9CF9). Reads as familiar to
    # AWS users and produces more readable button-text contrast on dark
    # surfaces than the warmer orange we use in light mode.
    "accent":         "#4F9CF9",
    "accent-text":    "#0A1A2E",
    "accent-strong":  "#4F9CF9",
    "accent-strong-hover": "#3F8BE0",
    "correct-text":   "#5DCAA5",
    "correct-bg":     "#1F3D2E",
    "correct-border": "#3D9479",
    "incorrect-text": "#F09595",
    "incorrect-bg":   "#3D1F1F",
    "incorrect-border": "#B85F5F",
    "border":         "#2F343C",
    "input-bg":       "#22262E",
    "input-bg-hover": "#2A2E37",
    "shadow":         "0 1px 2px rgba(0,0,0,0.35), 0 1px 1px rgba(0,0,0,0.25)",
    "shadow-hover":   "0 4px 12px rgba(0,0,0,0.45), 0 2px 4px rgba(0,0,0,0.3)",
    "stat-block-bg":  "linear-gradient(135deg, #22262E 0%, #2A2E37 100%)",
    "stat-block-text": "#E8EAED",
    "stat-block-muted": "#B4BAC2",
    "github-fill":    "%23E8EAED",
}


DARK_HC_PALETTE: dict[str, str] = {
    "bg":             "#13161C",
    "surface":        "#1C2027",
    "surface-2":      "#23272F",
    "text":           "#F2F3F5",
    "muted":          "#A8AEB8",
    "accent":         "#4F9CF9",
    "accent-text":    "#0A1A2E",
    "accent-strong":  "#4F9CF9",
    "accent-strong-hover": "#3F8BE0",
    "correct-text":   "#5DCAA5",
    "correct-bg":     "#1F3D2E",
    "correct-border": "#3D9479",
    "incorrect-text": "#F09595",
    "incorrect-bg":   "#3D1F1F",
    "incorrect-border": "#B85F5F",
    "border":         "#262B33",
    "input-bg":       "#1C2027",
    "input-bg-hover": "#23272F",
    "shadow":         "0 1px 3px rgba(0,0,0,0.55), 0 1px 2px rgba(0,0,0,0.4)",
    "shadow-hover":   "0 4px 14px rgba(0,0,0,0.6), 0 2px 5px rgba(0,0,0,0.45)",
    "stat-block-bg":  "linear-gradient(135deg, #1C2027 0%, #23272F 100%)",
    "stat-block-text": "#F2F3F5",
    "stat-block-muted": "#A8AEB8",
    "github-fill":    "%23F2F3F5",
}


PALETTES: dict[str, dict[str, str]] = {
    THEME_LIGHT: LIGHT_PALETTE,
    THEME_DARK_SLATE: DARK_SLATE_PALETTE,
    THEME_DARK_HC: DARK_HC_PALETTE,
}


def _vars_block(palette: dict[str, str]) -> str:
    return "\n".join(f"  --{k}: {v};" for k, v in palette.items())


def resolve_palette_name(theme_pref: str | None) -> str:
    """Map a stored preference to a concrete palette name (drops 'system')."""
    if theme_pref == THEME_LIGHT:
        return THEME_LIGHT
    if theme_pref == THEME_DARK_SLATE:
        return THEME_DARK_SLATE
    if theme_pref == THEME_DARK_HC:
        return THEME_DARK_HC
    # "system" / None / unknown -> let the @media rule decide; we emit BOTH
    # palettes wrapped in prefers-color-scheme media queries.
    return THEME_SYSTEM


def render_theme_css(theme_pref: str | None) -> str:
    """Return a <style> block setting CSS custom properties for the theme.

    For "system" (or unset): emit Light vars in the no-preference state and
    swap to Dark Slate inside an `@media (prefers-color-scheme: dark)` block.
    For explicit choices: emit a single :root block with that palette.
    """
    name = resolve_palette_name(theme_pref)
    if name == THEME_SYSTEM:
        light_vars = _vars_block(LIGHT_PALETTE)
        dark_vars = _vars_block(DARK_SLATE_PALETTE)
        return f"""
<style>
:root {{
{light_vars}
  --color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
{dark_vars}
    --color-scheme: dark;
  }}
}}
html {{ color-scheme: var(--color-scheme); }}
</style>
"""
    palette = PALETTES[name]
    is_dark = name in (THEME_DARK_SLATE, THEME_DARK_HC)
    vars_str = _vars_block(palette)
    return f"""
<style>
:root {{
{vars_str}
  --color-scheme: {'dark' if is_dark else 'light'};
}}
html {{ color-scheme: var(--color-scheme); }}
</style>
"""
