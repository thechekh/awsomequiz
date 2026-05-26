"""Global CSS for AWSomeQuiz.

Light-theme palette inspired by Claude's "Competitive Intelligence" artifact:
- Light gray page background (#F9FAFB)
- White cards with subtle 1px gray-200 border and soft shadow
- Inter typography, tight letter-spacing on headings
- Tiny uppercase muted labels above metric numbers
- Blue (#2563EB) primary, emerald for "correct", red for "wrong",
  amber for warnings, slate-900 dark blocks for emphasis

Injected once in streamlit_app.py via `st.markdown(CUSTOM_CSS, unsafe_allow_html=True)`.
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
    box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.04);
    padding: 1rem 1.25rem;
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
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.01em;
}
[data-testid="stMetricDelta"] {
    font-size: 0.75rem !important;
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
.stAlert {
    border-radius: 6px !important;
    font-size: 0.9rem;
}
.stAlert [data-baseweb="notification"] {
    border-radius: 6px;
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
    font-size: 1.4rem;
    font-weight: 500;
    color: #111827;
    line-height: 1.45;
    padding: 1.25rem 0;
}
.flashcard-back {
    font-size: 1rem;
    color: #374151;
    line-height: 1.6;
    padding: 0.75rem 0;
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

/* ----- Streamlit's "Deploy" / "Manage app" hamburger - dim it ----------- */
#MainMenu, header [data-testid="stToolbar"] {
    visibility: hidden;
}
footer {
    visibility: hidden;
}
</style>
"""
