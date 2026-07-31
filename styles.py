"""IBM Carbon Design-inspired CSS styles for Streamlit frontends.

Provides a parameterized theme dict and a CSS generator function.
Override THEME values or pass a custom dict to get_carbon_css() to
customize colors and fonts.
"""

THEME: dict[str, str] = {
    "primary": "#0f62fe",
    "primary_hover": "#0353e9",
    "primary_active": "#002d9c",
    "bg_primary": "#ffffff",
    "bg_secondary": "#f4f4f4",
    "text_primary": "#161616",
    "text_secondary": "#525252",
    "text_helper": "#6f6f6f",
    "text_placeholder": "#a8a8a8",
    "border": "#e0e0e0",
    "success": "#24a148",
    "error": "#da1e28",
    "font_sans": "'IBM Plex Sans', sans-serif",
    "font_mono": "'IBM Plex Mono', monospace",
}


def get_carbon_css(theme: dict[str, str] | None = None) -> str:
    """Return a <style> block with IBM Carbon Design-inspired styles.

    Args:
        theme: Optional dict of theme overrides. Keys should match THEME.
               Missing keys fall back to defaults.
    """
    t = {**THEME, **(theme or {})}
    return f"""
    <style>
    /* IBM Plex fonts */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

    /* Global font override */
    html, body, [class*="css"] {{
        font-family: {t["font_sans"]};
    }}

    /* Hide Streamlit chrome */
    #MainMenu {{visibility: hidden;}}
    header {{visibility: hidden;}}
    footer {{visibility: hidden;}}

    /* Reduce top padding on main content area */
    .stMainBlockContainer {{
        padding-top: 1.5rem !important;
    }}

    /* Logo container - override Streamlit element backgrounds */
    .stMarkdown img {{
        background-color: {t["bg_primary"]} !important;
    }}
    .element-container:has(img) {{
        background: transparent !important;
    }}

    /* Main title */
    h1 {{
        font-family: {t["font_sans"]} !important;
        font-weight: 600 !important;
        color: {t["text_primary"]} !important;
        letter-spacing: -0.02em;
    }}

    /* Subtitle text */
    .subtitle {{
        font-family: {t["font_sans"]};
        font-size: 0.95rem;
        color: {t["text_secondary"]};
        margin-top: -0.8rem;
        margin-bottom: 1.5rem;
    }}

    /* Text input - Carbon underline style */
    .stTextInput > div > div > input {{
        font-family: {t["font_sans"]} !important;
        border: none !important;
        border-bottom: 1px solid {t["border"]} !important;
        border-radius: 0 !important;
        background-color: {t["bg_secondary"]} !important;
        padding: 0.75rem !important;
        font-size: 0.95rem !important;
        color: {t["text_primary"]} !important;
    }}

    .stTextInput > div > div > input:focus {{
        border-bottom: 2px solid {t["primary"]} !important;
        box-shadow: none !important;
    }}

    .stTextInput > div > div > input::placeholder {{
        color: {t["text_placeholder"]} !important;
    }}

    /* Submit / Search button - Carbon primary */
    .stFormSubmitButton > button {{
        font-family: {t["font_sans"]} !important;
        background-color: {t["primary"]} !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0.75rem 2rem !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
        text-transform: none !important;
        min-height: 2.5rem !important;
    }}

    .stFormSubmitButton > button:hover {{
        background-color: {t["primary_hover"]} !important;
    }}

    .stFormSubmitButton > button:active {{
        background-color: {t["primary_active"]} !important;
    }}

    /* Sidebar styling */
    section[data-testid="stSidebar"] {{
        background-color: {t["bg_secondary"]} !important;
        border-right: 1px solid {t["border"]};
    }}

    section[data-testid="stSidebar"] h2 {{
        font-family: {t["font_sans"]} !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        color: {t["text_secondary"]} !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        margin-bottom: 0.75rem;
    }}

    /* Tool card */
    .tool-card {{
        background-color: {t["bg_primary"]};
        border: 1px solid {t["border"]};
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }}

    .tool-card .tool-name {{
        font-family: {t["font_mono"]};
        font-size: 0.8rem;
        font-weight: 500;
        color: {t["primary"]};
        margin-bottom: 0.35rem;
    }}

    .tool-card .tool-args {{
        font-family: {t["font_sans"]};
        font-size: 0.75rem;
        color: {t["text_secondary"]};
        line-height: 1.4;
    }}

    .tool-card .tool-args .arg-key {{
        color: {t["text_helper"]};
    }}

    /* Skill card - distinct from tool cards with blue accent */
    .skill-card {{
        background: linear-gradient(135deg, #e8f4fd 0%, #ffffff 100%);
        border: 1px solid {t["border"]};
        border-left: 3px solid {t["primary"]};
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
    }}

    .skill-card .skill-name {{
        font-family: {t["font_sans"]};
        font-size: 0.85rem;
        font-weight: 600;
        color: {t["primary"]};
        margin-bottom: 0.35rem;
    }}

    .skill-card .skill-desc {{
        font-family: {t["font_sans"]};
        font-size: 0.75rem;
        color: {t["text_secondary"]};
        line-height: 1.4;
    }}

    /* Sidebar ghost button */
    section[data-testid="stSidebar"] .stButton > button {{
        font-family: {t["font_sans"]} !important;
        background-color: transparent !important;
        color: {t["primary"]} !important;
        border: 1px solid {t["primary"]} !important;
        border-radius: 0 !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        padding: 0.5rem 1rem !important;
        width: 100%;
    }}

    section[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: {t["primary"]} !important;
        color: #ffffff !important;
    }}

    /* Health indicator */
    .health-indicator {{
        font-family: {t["font_sans"]};
        font-size: 0.75rem;
        color: {t["text_helper"]};
        padding: 0.5rem 0;
    }}

    .health-indicator .dot-ok {{
        color: {t["success"]};
    }}

    .health-indicator .dot-err {{
        color: {t["error"]};
    }}

    /* Empty state */
    .empty-state {{
        text-align: center;
        padding: 3rem 1rem;
    }}

    .empty-state .empty-title {{
        font-family: {t["font_sans"]};
        font-size: 1.1rem;
        font-weight: 500;
        color: {t["text_primary"]};
        margin-bottom: 0.5rem;
    }}

    .empty-state .empty-desc {{
        font-family: {t["font_sans"]};
        font-size: 0.875rem;
        color: {t["text_secondary"]};
        margin-bottom: 1.5rem;
    }}

    .empty-state .example-query {{
        font-family: {t["font_sans"]};
        font-size: 0.8rem;
        color: {t["text_helper"]};
        background-color: {t["bg_secondary"]};
        padding: 0.4rem 0.75rem;
        margin: 0.25rem auto;
        display: inline-block;
        border-left: 2px solid {t["primary"]};
    }}

    /* Markdown content in main area */
    .stMarkdown {{
        font-family: {t["font_sans"]} !important;
        color: {t["text_secondary"]};
        line-height: 1.6;
    }}

    /* Divider */
    hr {{
        border: none;
        border-top: 1px solid {t["border"]};
        margin: 1rem 0;
    }}
    </style>
    """
