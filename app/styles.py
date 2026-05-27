"""Global CSS for AWSomeQuiz.

Light-theme palette inspired by Claude's "Competitive Intelligence" artifact:
- Light gray page background (#F9FAFB)
- White cards with subtle 1px gray-200 border and soft shadow
- Inter typography, tight letter-spacing on headings
- Tiny uppercase muted labels above metric numbers
- Blue (#2563EB) primary, emerald for "correct", red for "wrong",
  amber for warnings, slate-900 dark blocks for emphasis

Use `render_combined_css(dark: bool)` in streamlit_app.py to inject CSS in a
SINGLE st.markdown call. Splitting into two st.markdown calls (base + dark
override) was causing the dark-mode toggle to shift page content because
the conditional second markdown adds an extra element to the DOM whose
wrapper takes a few pixels of padding.
"""


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}

/* Preserve Material Symbols icon font on Streamlit's :material/<name>: spans.
   Without this, the broader Inter font rule above cascades down and the
   icon ligature renders as literal text (e.g. "code" instead of <> glyph). */
.material-icons,
.material-symbols-outlined,
.material-symbols-rounded,
.material-symbols-sharp,
[class*="material-icons"],
[class*="material-symbols"],
[class*="MaterialSymbols"] {
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
    color: #111827 !important;
    letter-spacing: -0.015em;
    margin-bottom: 0.5rem;
}
h2, .stMarkdown h2 {
    font-size: 1.25rem !important;
    font-weight: 600 !important;
    color: #111827 !important;
    letter-spacing: -0.01em;
    margin-top: 1.5rem;
}
h3, .stMarkdown h3 {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #111827 !important;
}
.stCaption, [data-testid="stCaptionContainer"] {
    color: #6B7280 !important;
    font-size: 0.8125rem !important;
}

/* ----- Cards (st.container(border=True)) -------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.03);
    padding: 1.25rem 1.5rem;
    transition: box-shadow 0.15s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04);
}

/* ----- Metric blocks ----------------------------------------------------- */
[data-testid="stMetric"] {
    background: transparent;
}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
    color: #6B7280 !important;
    font-size: 0.7rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {
    color: #111827 !important;
    font-size: 1.875rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
[data-testid="stMetricDelta"] {
    font-size: 0.75rem !important;
}

/* ----- Section label (tiny uppercase muted heading) -------------------- */
.section-label {
    color: #6B7280;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 1.5rem 0 0.5rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #E5E7EB;
}

/* ----- Dark stat surface (the artifact's "Our Proof Points" pattern) --- */
/* High-contrast block to anchor the page visually. */
.dark-stat-block {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    border: 1px solid #1E293B;
    border-radius: 10px;
    padding: 1.75rem 2rem;
    color: #FFFFFF;
    margin: 0.5rem 0 1.25rem 0;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.18);
}
.dark-stat-block-title {
    color: #94A3B8;
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
    color: #94A3B8;
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.4rem;
}
.dark-stat-value {
    color: #FFFFFF;
    font-size: 2rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.dark-stat-value.accent-emerald { color: #34D399; }
.dark-stat-value.accent-amber   { color: #FBBF24; }

/* ----- Welcome intro paragraph (top of home page) ----------------------- */
.welcome-intro {
    color: #4B5563;
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
    border: 1px solid #D1D5DB !important;
    background: #FFFFFF !important;
    color: #111827 !important;
    transition: all 0.15s ease;
    padding: 0.45rem 0.9rem !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover, .stFormSubmitButton > button:hover {
    border-color: #9CA3AF !important;
    background: #F9FAFB !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: #2563EB !important;
    border-color: #2563EB !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: #1D4ED8 !important;
    border-color: #1D4ED8 !important;
}
.stButton > button:disabled {
    background: #F3F4F6 !important;
    color: #9CA3AF !important;
    border-color: #E5E7EB !important;
    cursor: not-allowed;
}

/* ----- Tabs (used on review.py, stats.py review tabs, etc.) ------------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid #E5E7EB !important;
    margin-bottom: 1rem;
}
.stTabs [data-baseweb="tab"] {
    padding: 0.6rem 1rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
}
.stTabs [aria-selected="true"][data-baseweb="tab"] {
    color: #2563EB !important;
    border-bottom: 2px solid #2563EB !important;
}

/* ----- Sidebar ----------------------------------------------------------- */
[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}
[data-testid="stSidebar"] .stButton > button {
    width: 100%;
}

/* ----- Alerts (st.success / info / warning / error) --------------------- */
/* Thicker left border for more visual presence, like the artifact's "Key
   Pattern" amber banners. */
.stAlert {
    border-radius: 6px !important;
    font-size: 0.9rem;
}
.stAlert [data-baseweb="notification"] {
    border-radius: 6px;
    border-left-width: 4px !important;
}

/* ----- Inputs ------------------------------------------------------------ */
/* Style the BaseWeb wrapper (not the inner <input>) so the eye-icon button
   inside the password field inherits the same bg. Inner input is set to
   transparent so it shows the wrapper bg through it. Caret stays dark
   against the white wrapper. */
.stTextInput [data-baseweb="input"],
.stTextArea [data-baseweb="textarea"],
.stTextArea [data-baseweb="base-input"],
.stNumberInput [data-baseweb="input"],
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    border-radius: 6px !important;
    border: 1px solid #D1D5DB !important;
    background: #FFFFFF !important;
    transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}
.stTextInput [data-baseweb="input"]:hover,
.stTextArea [data-baseweb="textarea"]:hover,
.stTextArea [data-baseweb="base-input"]:hover,
.stNumberInput [data-baseweb="input"]:hover,
.stSelectbox [data-baseweb="select"]:hover > div,
.stMultiSelect [data-baseweb="select"]:hover > div {
    border-color: #9CA3AF !important;
    background: #FAFAFA !important;
}
.stTextInput [data-baseweb="input"]:focus-within,
.stTextArea [data-baseweb="textarea"]:focus-within,
.stTextArea [data-baseweb="base-input"]:focus-within,
.stNumberInput [data-baseweb="input"]:focus-within {
    border-color: #2563EB !important;
    background: #FFFFFF !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
}

/* The actual <input>/<textarea> goes transparent so the wrapper's bg + the
   eye-icon button (same parent) read as one continuous field. Also kill the
   default focus outline since the wrapper already shows focus. */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: transparent !important;
    border: none !important;
    color: #111827 !important;
    caret-color: #111827 !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    box-shadow: none !important;
    border: none !important;
    outline: none !important;
}

/* Password reveal (eye) button + any other inline button inside the input
   wrapper. BaseWeb renders these with their own hover/focus bg, which appears
   as a stray gray block next to the field. Force everything transparent so
   the wrapper bg reads as one continuous field. */
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
    border-color: #E5E7EB !important;
    margin: 1.25rem 0 !important;
}

/* ----- Dataframe / Table ------------------------------------------------- */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    background: #FFFFFF;
}

/* ----- GitHub sign-in button --------------------------------------------- */
/* pages/login.py uses st.link_button (NOT raw HTML) so the link escapes
   Streamlit's sandboxed iframe and can top-navigate to github.com. Since
   link_button only accepts Material Symbols / emoji for `icon=` (and
   Material Symbols has no brand logos), we inject the GitHub octocat as
   a ::before pseudo-element INSIDE the label paragraph (so the icon ends
   up as inline content right next to the text, not as a separate flex
   sibling pinned to the button's left edge). */
.stLinkButton a[href*="provider=github"] p::before {
    content: "";
    display: inline-block;
    width: 18px;
    height: 18px;
    margin-right: 0.5rem;
    vertical-align: -3px;
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="%23111827"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>');
    background-repeat: no-repeat;
    background-size: 18px 18px;
}

/* ----- Flashcard-specific (see pages/flashcards.py) --------------------- */
.flashcard-front {
    font-size: 1.75rem;
    font-weight: 500;
    color: #111827;
    line-height: 1.4;
    padding: 2rem 0.5rem;
    text-align: center;
    letter-spacing: -0.01em;
}
.flashcard-back {
    font-size: 1.05rem;
    color: #374151;
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
    color: #6B7280;
    background: #F3F4F6;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    margin-bottom: 0.5rem;
}

/* ----- Option rows (post-submit review) -------------------------------- */
/* Custom row styling so correct (green) / wrong (red) / neutral (gray)
   options all share the same left padding -- st.success/error have built-in
   alert padding that shifted them rightward, which looked unaligned. */
.opt-row {
    padding: 0.6rem 0.85rem;
    border-radius: 6px;
    margin-bottom: 0.45rem;
    border-left: 3px solid #E5E7EB;
    background: #F9FAFB;
    color: #374151;
    font-size: 0.95rem;
    line-height: 1.5;
}
.opt-row.correct {
    background: #ECFDF5;
    border-left-color: #10B981;
    color: #065F46;
}
.opt-row.wrong {
    background: #FEF2F2;
    border-left-color: #EF4444;
    color: #991B1B;
}
.opt-row .opt-tag {
    display: inline-block;
    margin-left: 0.5rem;
    font-size: 0.75rem;
    color: #6B7280;
    font-weight: 500;
}
.opt-explanation {
    padding: 0.5rem 0.85rem 0.9rem 0.85rem;
    font-size: 0.95rem;
    line-height: 1.55;
    color: #4B5563;
}
.opt-related {
    padding: 0 0.85rem 0.5rem 0.85rem;
    font-size: 0.875rem;
    font-style: italic;
    color: #6B7280;
}

/* ----- Sidebar mini-stats panel (top of sidebar, all auth pages) ------- */
.sidebar-mini-stats {
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin: 0 0 0.75rem 0;
    color: #FFFFFF;
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
    color: #94A3B8;
    font-size: 0.7rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sidebar-mini-value {
    color: #FFFFFF;
    font-size: 1.05rem;
    font-weight: 600;
    letter-spacing: -0.01em;
}

/* ----- Streamlit's "Deploy" / "Manage app" hamburger - dim it ----------- */
#MainMenu, header [data-testid="stToolbar"] {
    visibility: hidden;
}
footer {
    visibility: hidden;
}

/* ----- Hide invisible utility components (cookie manager). Renders as a
   small iframe whose container can take vertical space and cause flicker
   / layout shift on dark-mode toggle rerun. Scoped to the MAIN app area
   only -- a broad :has() rule was inadvertently collapsing sidebar
   containers that share the .element-container class. ------------------- */
[data-testid="stAppViewContainer"] .element-container:has(iframe[title*="extra_streamlit_components"]),
[data-testid="stAppViewContainer"] .element-container:has(iframe[title*="CookieManager"]),
[data-testid="stAppViewContainer"] .element-container:has(iframe[height="0"]),
[data-testid="stAppViewContainer"] [data-testid="stCustomComponentV1"]:has(iframe[title*="extra_streamlit_components"]),
[data-testid="stAppViewContainer"] [data-testid="stCustomComponentV1"]:has(iframe[title*="CookieManager"]),
[data-testid="stAppViewContainer"] [data-testid="stCustomComponentV1"]:has(iframe[height="0"]) {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 0 !important;
}
/* And as a fallback, hide the raw iframes themselves (this rule is safe
   to apply everywhere -- the wrapper visibility is what matters above). */
iframe[title*="extra_streamlit_components"],
iframe[title*="CookieManager"],
iframe[height="0"] {
    display: none !important;
    height: 0 !important;
}

/* Force the sidebar visible. After login (rerun, not cold load), Streamlit
   leaves the sidebar at aria-expanded="false" -- positioned off-screen
   (transform translateX or left: -300px) with width 1px. The auto-rendered
   expand button isn't always reliably visible across Streamlit versions,
   so we override the collapsed positioning unconditionally. Users can
   collapse by clicking the in-sidebar collapse button; React state will
   flip aria-expanded back to false, but our CSS keeps it pinned visible.
   That's an acceptable trade for "navigation always visible after login". */
[data-testid="stSidebar"] {
    min-width: 244px !important;
    width: 244px !important;
    left: 0 !important;
    transform: none !important;
    margin-left: 0 !important;
}

/* Style-only st.markdown injections (CSS, JS, hidden helpers) shouldn't
   take page space. Their `.stMarkdown` wrapper would otherwise add ~16px
   of vertical padding and cause layout shift when one is added/removed
   (e.g. dark-mode toggle). */
.stMarkdown:has(> style),
.element-container:has(> .stMarkdown > style),
.stMarkdown:has(> script) {
    display: none !important;
    margin: 0 !important;
    padding: 0 !important;
    height: 0 !important;
}

/* Lock the height of the top header row (the columns wrapping the Dark
   mode toggle) so the page below can't shift even by a pixel when the
   toggle state changes. */
[data-testid="stAppViewBlockContainer"] > [data-testid="stHorizontalBlock"]:first-of-type {
    min-height: 44px !important;
    margin-bottom: 0.25rem !important;
}
</style>
"""


# Injected AFTER CUSTOM_CSS when st.session_state["dark_mode"] is True.
# Additive override -- only re-defines the rules that need to change for dark.
DARK_OVERRIDE_CSS = """
<style>
.stApp, .main, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background: #0B1220 !important;
    color: #E2E8F0 !important;
}
.main .block-container { background: transparent !important; }

h1, h2, h3, h4, h5, h6, .stMarkdown, .stMarkdown p,
.stMarkdown li, .stMarkdown strong, .stMarkdown em, .stMarkdown a {
    color: #F1F5F9 !important;
}
.stMarkdown a { color: #60A5FA !important; }
.stCaption, [data-testid="stCaptionContainer"],
.stCaption *, [data-testid="stCaptionContainer"] * {
    color: #94A3B8 !important;
}
.welcome-intro { color: #CBD5E1 !important; }
.section-label {
    color: #94A3B8 !important;
    border-bottom-color: #1E293B !important;
}

/* Form widget labels (the "Domain", "Number of questions", "Choose one"
   lead text above radios/checkboxes/inputs). Streamlit's default light-mode
   color leaves these unreadable on a dark page. */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
.stRadio label, .stRadio label p,
.stCheckbox label, .stCheckbox label p,
.stSelectbox label, .stMultiSelect label,
.stTextInput label, .stTextArea label, .stNumberInput label,
label[data-baseweb="form-control-label"] {
    color: #E2E8F0 !important;
}

/* Radio + checkbox OPTION labels (the answer text, e.g. "A. Attach another
   EBS volume...") -- without this they render in default dim color. */
.stRadio [role="radiogroup"] label,
.stRadio [role="radiogroup"] label *,
.stCheckbox [data-baseweb="checkbox"] *,
[data-baseweb="radio"] *,
[data-baseweb="checkbox"] * {
    color: #F1F5F9 !important;
}

/* Selectbox / multiselect displayed value */
.stSelectbox [data-baseweb="select"] *,
.stMultiSelect [data-baseweb="select"] * {
    color: #F1F5F9 !important;
}

/* Cards */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #111827 !important;
    border-color: #1F2937 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.35), 0 1px 2px rgba(0,0,0,0.25) !important;
}

/* Metrics */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {
    color: #94A3B8 !important;
}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {
    color: #F1F5F9 !important;
}

/* Buttons */
.stButton > button, .stDownloadButton > button, .stLinkButton > a, .stFormSubmitButton > button {
    background: #1F2937 !important;
    border-color: #374151 !important;
    color: #F1F5F9 !important;
}
.stButton > button:hover, .stLinkButton > a:hover, .stFormSubmitButton > button:hover {
    background: #374151 !important;
    border-color: #4B5563 !important;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background: #3B82F6 !important;
    border-color: #3B82F6 !important;
    color: #FFFFFF !important;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
    background: #2563EB !important;
}
.stButton > button:disabled {
    background: #1F2937 !important;
    color: #6B7280 !important;
    border-color: #374151 !important;
}

/* GitHub button text override (kept readable on dark bg) */
.stLinkButton a[href*="provider=github"] p::before {
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="%23F1F5F9"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"/></svg>') !important;
}

/* Inputs */
.stTextInput [data-baseweb="input"],
.stTextArea [data-baseweb="textarea"],
.stTextArea [data-baseweb="base-input"],
.stNumberInput [data-baseweb="input"],
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
    background: #1F2937 !important;
    border-color: #374151 !important;
}
.stTextInput [data-baseweb="input"]:hover,
.stTextArea [data-baseweb="textarea"]:hover,
.stNumberInput [data-baseweb="input"]:hover {
    background: #374151 !important;
    border-color: #4B5563 !important;
}
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    color: #F1F5F9 !important;
    caret-color: #F1F5F9 !important;
}

/* Sidebar (slightly lighter than page bg so it's visible -- before this
   both bg's were #0B1220 and the sidebar looked invisible/hidden). */
[data-testid="stSidebar"] {
    background: #111827 !important;
    border-right: 1px solid #1F2937 !important;
}
[data-testid="stSidebar"] * { color: #E2E8F0; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { border-bottom-color: #1F2937 !important; }
.stTabs [data-baseweb="tab"] { color: #94A3B8 !important; }
.stTabs [aria-selected="true"][data-baseweb="tab"] {
    color: #60A5FA !important;
    border-bottom-color: #60A5FA !important;
}

/* Dividers */
hr, [data-testid="stDivider"] { border-color: #1F2937 !important; }

/* Dataframe */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    background: #111827 !important;
    border-color: #1F2937 !important;
    color: #E2E8F0 !important;
}

/* Alerts */
.stAlert [data-baseweb="notification"] {
    background: #1F2937 !important;
    color: #F1F5F9 !important;
}

/* Option rows (post-submit review) */
.opt-row {
    background: #111827;
    border-left-color: #374151;
    color: #E2E8F0;
}
.opt-row.correct {
    background: #052E26;
    border-left-color: #10B981;
    color: #A7F3D0;
}
.opt-row.wrong {
    background: #2A0B0B;
    border-left-color: #EF4444;
    color: #FECACA;
}
.opt-row .opt-tag { color: #94A3B8; }
.opt-explanation { color: #CBD5E1; }
.opt-related { color: #94A3B8; }

/* Flashcards */
.flashcard-front { color: #F1F5F9 !important; }
.flashcard-back { color: #CBD5E1 !important; }
.flashcard-category {
    background: #1F2937 !important;
    color: #94A3B8 !important;
}
</style>
"""


# ---------------------------------------------------------------------------
# Combined-CSS renderer (single injection avoids layout shift on dark toggle).
# ---------------------------------------------------------------------------


def render_combined_css(dark: bool) -> str:
    """Return a single <style> block with light base + optional dark overrides.

    Why one block: each st.markdown call adds an element to the DOM. Even
    with empty visible content, its wrapper takes ~10-20px of padding. Using
    a single injection means the same number of DOM elements regardless of
    theme, so toggling doesn't shift content.
    """
    # Strip the <style>...</style> wrappers and join the contents.
    light_body = CUSTOM_CSS.replace("<style>", "").replace("</style>", "").strip()
    if not dark:
        return f"<style>\n{light_body}\n</style>"
    dark_body = DARK_OVERRIDE_CSS.replace("<style>", "").replace("</style>", "").strip()
    return f"<style>\n{light_body}\n\n/* === DARK MODE OVERRIDES === */\n{dark_body}\n</style>"


# Note: we tried a popup-based same-tab OAuth flow (custom HTML button +
# window.open + BroadcastChannel cookie hand-off). It kept losing the session
# across the popup -> parent boundary (cookie write race, COOP nulled opener,
# inconsistent window.close behavior across browsers). Reverted to the
# default st.link_button which opens in a new tab and reliably signs the
# user in there. The .github-signin-btn class CSS that was here is no
# longer used and has been removed.
