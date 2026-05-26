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

html, body, [class*="st-"], .stApp, [data-testid="stAppViewContainer"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
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
.stTextInput input, .stTextArea textarea, .stNumberInput input,
.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div,
[data-baseweb="input"] {
    border-radius: 6px !important;
    border-color: #D1D5DB !important;
    background: #FFFFFF !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
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
