import streamlit as st

THEMES = {
    "detective": {
        "bg": "#f1e7cf",
        "bg_secondary": "#e3d2a8",
        "sidebar_bg": "#d9c294",
        "text": "#3b2a1a",
        "accent": "#7a1f1f",
        "accent_text": "#f4ecd8",
        "button_bg": "#6b4226",
        "button_hover": "#8a5a3c",
        "border": "#c9a227",
        # Matches st.info's own background (rgba(28,131,255,0.1) over this
        # theme's light page background), sampled from a real render.
        "select_bg": "#e6f3ff",
        "select_text": "#000000",
        "image": "assets/detective_case.png",
        "tagline": "Case files, sepia ink, and one lead at a time.",
    },
    "boss_fight": {
        "bg": "#1c1622",
        "bg_secondary": "#2a2033",
        "sidebar_bg": "#150f1a",
        "text": "#ece4f5",
        "accent": "#ff8a3d",
        "accent_text": "#2b1620",
        "button_bg": "#4b2e83",
        "button_hover": "#6842a8",
        "border": "#ff8a3d",
        # Matches st.info's own background (rgba(28,131,255,0.1) over this
        # theme's dark page background), sampled from a real render.
        "select_bg": "#1c2038",
        "select_text": "#ece4f5",
        "image": "assets/boss_dragon.png",
        "tagline": "Torchlight, old stone, and one very unhappy boss.",
    },
}


def inject_theme(mode: str):
    """Inject mode-specific CSS. Called every run so the palette always
    matches the currently selected mode, even before a game has started."""
    theme = THEMES[mode]
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

        .stApp {{
            background-color: {theme['bg']};
        }}
        [data-testid="stHeader"] {{
            background-color: {theme['bg']};
        }}
        [data-testid="stToolbar"] button svg, [data-testid="stHeader"] svg {{
            fill: {theme['text']};
        }}

        .stApp, .stApp p, .stApp li, .stMarkdown, .stCaption,
        [data-testid="stMarkdownContainer"], [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"], [data-testid="stWidgetLabel"] label {{
            color: {theme['text']} !important;
        }}

        h1, h2, h3 {{
            font-family: 'Press Start 2P', monospace !important;
            color: {theme['accent']} !important;
            letter-spacing: 1px;
        }}

        [data-testid="stSidebar"] {{
            background-color: {theme['sidebar_bg']};
        }}
        [data-testid="stSidebar"] * {{
            color: {theme['text']} !important;
        }}

        /* Sidebar collapse/expand toggle — a different element depending on
           whether the sidebar is open (stSidebarCollapseButton) or hidden
           (stExpandSidebarButton), both need a contrast-safe color per theme. */
        [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
        [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{
            color: {theme['text']} !important;
        }}

        /* Selectbox closed box (mode/tier dropdowns) */
        [data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
            background-color: {theme['select_bg']} !important;
        }}
        [data-testid="stSelectbox"] div[data-baseweb="select"] * {{
            color: {theme['select_text']} !important;
        }}

        /* Selectbox open dropdown list — renders in a portal outside the sidebar */
        div[data-baseweb="popover"] li,
        div[data-baseweb="popover"] ul {{
            background-color: {theme['select_bg']} !important;
            color: {theme['select_text']} !important;
        }}

        /* Guess textbox */
        [data-testid="stTextInput"] input {{
            background-color: {theme['select_bg']} !important;
            color: {theme['select_text']} !important;
        }}

        .stButton > button, .stFormSubmitButton > button {{
            background-color: {theme['button_bg']};
            color: {theme['accent_text']} !important;
            border: 2px solid {theme['border']};
            border-radius: 6px;
            font-weight: 600;
        }}
        .stButton > button:hover, .stFormSubmitButton > button:hover {{
            background-color: {theme['button_hover']};
            border-color: {theme['border']};
        }}
        /* Button label text renders inside a MarkdownContainer, which the
           broad text-color rule above would otherwise clobber (higher
           specificity here wins regardless of rule order). */
        .stButton [data-testid="stMarkdownContainer"],
        .stFormSubmitButton [data-testid="stMarkdownContainer"],
        .stButton [data-testid="stMarkdownContainer"] p,
        .stFormSubmitButton [data-testid="stMarkdownContainer"] p {{
            color: {theme['accent_text']} !important;
        }}

        [data-testid="stForm"] {{
            background-color: {theme['bg_secondary']};
            border: 2px solid {theme['border']};
            border-radius: 10px;
            padding: 1rem;
        }}

        [data-testid="stMetric"] {{
            background-color: {theme['bg_secondary']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 0.5rem;
        }}

        [data-testid="stExpander"] {{
            background-color: {theme['bg_secondary']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
        }}

        hr {{
            border-color: {theme['border']} !important;
        }}

        [data-testid="stProgressBarTrack"] {{
            background-color: {theme['bg_secondary']} !important;
        }}
        [data-testid="stProgressBarTrack"] > div {{
            background-color: {theme['accent']} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def theme_image(mode: str) -> str:
    return THEMES[mode]["image"]


def theme_tagline(mode: str) -> str:
    return THEMES[mode]["tagline"]
