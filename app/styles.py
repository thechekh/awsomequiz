"""Global CSS for AWSomeQuiz, theme-agnostic.

All color values come from CSS custom properties defined by app/theme.py
(`--bg`, `--surface`, `--text`, `--muted`, `--accent`, `--correct-*`,
`--incorrect-*`, `--border`, etc.). Swapping themes is a matter of
re-emitting the :root vars block; this CSS does not change.

Layout, typography, and shape rules live here. Color rules use var() so
they pick up the active palette automatically.
"""


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: var(--bg) !important;
    color: var(--text);
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"], .main {
    background: var(--bg) !important;
    color: var(--text) !important;
}
.main .block-container { background: transparent !important; }

/* Preserve Material Symbols icon font on Streamlit's :material/<name>: spans.
   Without this, the broader Inter font rule above cascades down and the
   icon ligature renders as literal text (e.g. "code" instead of <> glyph). */
.material-icons,
.material-symbols-outlined,
.material-symbols-rounded,
.material-symbols-sharp,
[class*="material-icons"],
[class*="material-symbols"],
[class*="MaterialSymbols"],
[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"] * {
    font-family: 'Material Symbols Outlined', 'Material Symbols Rounded',
                 'Material Symbols Sharp', 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-feature-settings: 'liga' !important;
    -webkit-font-smoothing: antialiased !important;
    text-transform: none !important;
    letter-spacing: normal !important;
    line-height: 1 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
}

/* Page chrome */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 4rem;
    max-width: 1280px;
}

/* ----- Headings ---------------------------------------------------------- */
h1, h1 a, .stMarkdown h1 {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    letter-spacing: -0.015em;
    margin-bottom: 0.5rem;
}
h2, .stMarkdown h2 {
    font-size: 1.25rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    letter-spacing: -0.01em;
    margin-top: 1.5rem;
}
h3, .stMarkdown h3 {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: var(--text) !important;
}
.stMarkdown, .stMarkdown p, .stMarkdown li,
.stMarkdown strong, .stMarkdown em { color: var(--text); }
.stMarkdown a { color: var(--accent-strong) !important; }
.stCaption, [data-testid="stCaptionContainer"] {
    color: var(--muted) !important;
    font-size: 0.8125rem !important;
}
.stCaption *, [data-testid="stCaptionContainer"] * { color: var(--muted); }

/* ----- Cards (st.container(border=True)) -------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    box-shadow: var(--shadow);
    padding: 1.25rem 1.5rem;
    transition: box-shadow 0.15s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: var(--shadow-hover);
}

/* ----- Metric blocks ----------------------------------------------------- */
[data-testid="stMetric"] { background: transparent; }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
    color: var(--muted) !important;
    font-size: 0.7rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {
    color: var(--text) !important;
    font-size: 1.875rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* ----- Section label (tiny uppercase muted heading) -------------------- */
.section-label {
    color: var(--muted);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 1.5rem 0 0.5rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}

/* ----- Dark stat surface (the artifact's "Our Proof Points" pattern) --- */
.dark-stat-block {
    background: var(--stat-block-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.75rem 2rem;
    color: var(--stat-block-text);
    margin: 0.5rem 0 1.25rem 0;
    box-shadow: var(--shadow);
}
.dark-stat-block-title {
    color: var(--stat-block-muted);
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    margin-bottom: 1rem;
}
.dark-stat-row {
    display: flex;
    flex-wrap: wrap;
    gap: 2rem 3rem;
    align-items: flex-end;
}
.dark-stat-item {
    flex: 1 1 auto;
    min-width: 140px;
}
.dark-stat-label {
    color: var(--stat-block-muted);
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.4rem;
}
.dark-stat-value {
    color: var(--stat-block-text);
    font-size: 2rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.dark-stat-value.accent-emerald { color: var(--correct-text); }
.dark-stat-value.accent-amber   { color: var(--accent); }

/* ----- Welcome intro paragraph (top of home page) ----------------------- */
.welcome-intro {
    color: var(--muted);
    font-size: 0.95rem;
    line-height: 1.6;
    margin: 0 0 1.25rem 0;
    max-width: 760px;
}

/* ----- Buttons ----------------------------------------------------------- */
.stButton > button, .stDownloadButton > button, .stLinkButton > a, .stFormSubmitButton > button {
    border-radius: 6px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    border: 1px solid var(--border) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
    transition: all 0.15s ease;
    padding: 0.45rem 0.9rem !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover, .stFormSubmitButton > button:hover {
    border-color: var(--muted) !important;
    background: var(--surface-2) !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: var(--accent-strong) !important;
    border-color: var(--accent-strong) !important;
    color: var(--accent-text) !important;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: var(--accent-strong-hover) !important;
    border-color: var(--accent-strong-hover) !important;
}
.stButton > button:disabled {
    background: var(--surface-2) !important;
    color: var(--muted) !important;
    border-color: var(--border) !important;
    cursor: not-allowed;
}

/* ----- Form widget labels + Radio/checkbox option labels ---------------- */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
.stRadio label, .stRadio label p,
.stCheckbox label, .stCheckbox label p,
.stSelectbox label, .stMultiSelect label,
.stTextInput label, .stTextArea label, .stNumberInput label,
label[data-baseweb="form-control-label"] {
    color: var(--text) !important;
}
.stRadio [role="radiogroup"] label,
.stRadio [role="radiogroup"] label *,
.stCheckbox [data-baseweb="checkbox"] *,
[data-baseweb="radio"] *,
[data-baseweb="checkbox"] * {
    color: var(--text) !important;
}
.stSelectbox [data-baseweb="select"] *,
.stMultiSelect [data-baseweb="select"] * {
    color: var(--text) !important;
}

/* ----- Tabs (used on review.py, stats.py review tabs, etc.) ------------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid var(--border) !important;
    margin-bottom: 1rem;
}
.stTabs [data-baseweb="tab"] {
    padding: 0.6rem 1rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: var(--muted) !important;
}
.stTabs [aria-selected="true"][data-baseweb="tab"] {
    color: var(--accent-strong) !important;
    border-bottom: 2px solid var(--accent-strong) !important;
}

/* ----- Sidebar ----------------------------------------------------------- */
[data-testid="stSidebar"] {
    background: var(--surface) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text); }
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
}
[data-testid="stSidebarContent"] { background: var(--surface) !important; }

/* ----- Sidebar collapse / expand controls always visible --------------- */
/* The collapse arrow inside the sidebar header was opacity:0 until hover,
   making it look like there was no way back once you opened it. Pin to
   visible regardless of mouse position. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] button {
    opacity: 1 !important;
    visibility: visible !important;
    color: var(--text) !important;
}
[data-testid="stExpandSidebarButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 1000 !important;
}

/* ----- Alerts (st.success / info / warning / error) --------------------- */
.stAlert {
    border-radius: 6px !important;
    font-size: 0.9rem;
}
.stAlert [data-baseweb="notification"] {
    border-radius: 6px;
    border-left-width: 4px !important;
    background: var(--surface-2) !important;
    color: var(--text) !important;
}

/* ----- Inputs ------------------------------------------------------------ */
.stTextInput [data-baseweb="input"],
.stTextArea [data-baseweb="textarea"],
.stTextArea [data-baseweb="base-input"],
.stNumberInput [data-baseweb="input"],
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    border-radius: 6px !important;
    border: 1px solid var(--border) !important;
    background: var(--input-bg) !important;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.stTextInput [data-baseweb="input"]:hover,
.stTextArea [data-baseweb="textarea"]:hover,
.stTextArea [data-baseweb="base-input"]:hover,
.stNumberInput [data-baseweb="input"]:hover,
.stSelectbox [data-baseweb="select"]:hover > div,
.stMultiSelect [data-baseweb="select"]:hover > div {
    border-color: var(--muted) !important;
    background: var(--input-bg-hover) !important;
}
.stTextInput [data-baseweb="input"]:focus-within,
.stTextArea [data-baseweb="textarea"]:focus-within,
.stTextArea [data-baseweb="base-input"]:focus-within,
.stNumberInput [data-baseweb="input"]:focus-within {
    border-color: var(--accent-strong) !important;
    background: var(--input-bg) !important;
    box-shadow: 0 0 0 3px rgba(255, 153, 0, 0.12) !important;
}
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: transparent !important;
    border: none !important;
    color: var(--text) !important;
    caret-color: var(--text) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    box-shadow: none !important;
    border: none !important;
    outline: none !important;
}
.stTextInput [data-baseweb="input"] > div,
.stTextInput [data-baseweb="input"] button {
    background: transparent !important;
}
.stTextInput [data-baseweb="input"] button,
.stTextInput [data-baseweb="input"] button:hover,
.stTextInput [data-baseweb="input"] button:focus,
.stTextInput [data-baseweb="input"] button:active {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* Hide the "Press Enter to submit form" hint that Streamlit shows below
   text inputs inside a form. */
[data-testid="InputInstructions"],
[data-testid="stWidgetInstructions"],
.stTextInput div[data-baseweb="form-control-counter"] {
    display: none !important;
}

/* ----- Radio + Checkbox -------------------------------------------------- */
.stRadio > div, .stCheckbox > label {
    font-size: 0.9rem;
}

/* ----- Dividers ---------------------------------------------------------- */
hr, [data-testid="stDivider"] {
    border-color: var(--border) !important;
    margin: 1.25rem 0 !important;
}

/* ----- Dataframe / Table ------------------------------------------------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
}

/* ----- GitHub sign-in button --------------------------------------------- */
.stLinkButton a[href*="provider=github"] p::before {
    content: "";
    display: inline-block;
    width: 18px;
    height: 18px;
    margin-right: 0.5rem;
    vertical-align: -3px;
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="var(--github-fill)"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>');
    background-repeat: no-repeat;
    background-size: 18px 18px;
}

/* ----- Flashcard-specific (see pages/flashcards.py) --------------------- */
.flashcard-front {
    font-size: 1.75rem;
    font-weight: 500;
    color: var(--text);
    line-height: 1.4;
    padding: 2rem 0.5rem;
    text-align: center;
    letter-spacing: -0.01em;
}
.flashcard-back {
    font-size: 1.05rem;
    color: var(--text);
    line-height: 1.65;
    padding: 1rem 0.5rem;
    text-align: center;
}
.flashcard-category {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    background: var(--surface-2);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

/* ----- Option rows (post-submit review) -------------------------------- */
.opt-row {
    padding: 0.6rem 0.85rem;
    border-radius: 6px;
    margin-bottom: 0.45rem;
    border-left: 3px solid var(--border);
    background: var(--surface-2);
    color: var(--text);
    font-size: 0.95rem;
    line-height: 1.5;
}
.opt-row.correct {
    background: var(--correct-bg);
    border-left-color: var(--correct-border);
    color: var(--correct-text);
}
.opt-row.correct b { color: var(--correct-text) !important; }
.opt-row.wrong {
    background: var(--incorrect-bg);
    border-left-color: var(--incorrect-border);
    color: var(--incorrect-text);
}
.opt-row.wrong b { color: var(--incorrect-text) !important; }
.opt-row .opt-tag {
    display: inline-block;
    margin-left: 0.5rem;
    font-size: 0.75rem;
    color: var(--muted);
    font-weight: 500;
}
.opt-explanation {
    padding: 0.5rem 0.85rem 0.9rem 0.85rem;
    font-size: 0.95rem;
    line-height: 1.55;
    color: var(--muted);
}
.opt-related {
    padding: 0 0.85rem 0.5rem 0.85rem;
    font-size: 0.875rem;
    font-style: italic;
    color: var(--muted);
}

/* ----- Sidebar mini-stats panel (top of sidebar, all auth pages) ------- */
.sidebar-mini-stats {
    background: var(--stat-block-bg);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin: 0 0 0.75rem 0;
    color: var(--stat-block-text);
}
.sidebar-mini-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.2rem 0;
}
.sidebar-mini-row + .sidebar-mini-row {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    margin-top: 0.25rem;
    padding-top: 0.45rem;
}
.sidebar-mini-label {
    color: var(--stat-block-muted);
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sidebar-mini-value {
    color: var(--stat-block-text);
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}

/* ----- Glossary entries (pages/glossary.py) ---------------------------- */
.glossary-entry {
    padding: 0.55rem 0.85rem;
    margin-bottom: 0.45rem;
    border-left: 3px solid var(--accent);
    background: var(--surface);
    border: 1px solid var(--border);
    border-left-width: 3px;
    border-radius: 4px;
}
.glossary-term {
    font-weight: 600;
    font-size: 1.02rem;
    color: var(--text);
}
.glossary-meta {
    margin-left: 0.55rem;
    font-size: 0.72rem;
    color: var(--muted);
    white-space: nowrap;
}
.glossary-definition {
    margin-top: 0.25rem;
    line-height: 1.45;
    color: var(--text);
}
.glossary-letter {
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--accent) !important;
    margin: 1.1rem 0 0.45rem 0;
    padding-bottom: 0.15rem;
    border-bottom: 1px solid var(--border);
}

/* ----- Streamlit's "Deploy" / "Manage app" hamburger - hidden ----------- */
#MainMenu, header [data-testid="stToolbar"] { visibility: hidden; }
footer { visibility: hidden; }

/* ----- Hide invisible utility components (cookie manager) -------------- */
[data-testid="stAppViewContainer"] .element-container:has(iframe[title*="extra_streamlit_components"]),
[data-testid="stAppViewContainer"] .element-container:has(iframe[title*="CookieManager"]),
[data-testid="stAppViewContainer"] .element-container:has(iframe[height="0"]),
[data-testid="stAppViewContainer"] [data-testid="stCustomComponentV1"]:has(iframe[title*="extra_streamlit_components"]),
[data-testid="stAppViewContainer"] [data-testid="stCustomComponentV1"]:has(iframe[title*="CookieManager"]),
[data-testid="stAppViewContainer"] [data-testid="stCustomComponentV1"]:has(iframe[height="0"]) {
    display: block !important;
    visibility: visible !important;
    position: absolute !important;
    left: -9999px !important;
    top: -9999px !important;
    height: 1px !important;
    width: 1px !important;
    overflow: hidden !important;
    pointer-events: none !important;
    margin: 0 !important;
    padding: 0 !important;
}
iframe[title*="extra_streamlit_components"],
iframe[title*="CookieManager"],
iframe[height="0"] {
    display: block !important;
    visibility: hidden !important;
    height: 1px !important;
    width: 1px !important;
}

/* Sidebar widths */
[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 244px !important;
    width: 244px !important;
}

/* Style-only st.markdown injections shouldn't take page space. */
.stMarkdown:has(> style),
.element-container:has(> .stMarkdown > style),
.stMarkdown:has(> script) {
    display: none !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 0 !important;
}
</style>
"""


def render_combined_css(_dark: bool = False) -> str:
    """Return the global stylesheet. Theme colors come from CSS vars set in
    app/theme.py; the `_dark` arg is kept for backwards-compat callsites but
    is otherwise ignored -- light/dark is now driven by the var palette.
    """
    return CUSTOM_CSS
