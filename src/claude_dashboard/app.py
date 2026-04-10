import streamlit as st

st.set_page_config(
    page_title="Claude Code Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS - theme-aware
st.markdown("""
<style>
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar branding
with st.sidebar:
    st.title("Claude Dashboard")
    st.caption("Claude Code Usage Analytics")
    st.divider()


# Page imports (deferred to avoid circular imports)
def page_overview():
    from claude_dashboard.pages.overview import render
    render()


def page_tokens():
    from claude_dashboard.pages.tokens_cost import render
    render()


def page_tools():
    from claude_dashboard.pages.tool_usage import render
    render()


def page_security():
    from claude_dashboard.pages.security import render
    render()


def page_sessions():
    from claude_dashboard.pages.sessions import render
    render()


def page_projects():
    from claude_dashboard.pages.projects import render
    render()


def page_productivity():
    from claude_dashboard.pages.productivity import render
    render()


# Navigation
pg = st.navigation([
    st.Page(page_overview, title="Overview", icon=":material/dashboard:", default=True),
    st.Page(page_tokens, title="Tokens & Cost", icon=":material/toll:"),
    st.Page(page_tools, title="Tool Usage", icon=":material/build:"),
    st.Page(page_security, title="Security", icon=":material/security:"),
    st.Page(page_sessions, title="Sessions", icon=":material/history:"),
    st.Page(page_projects, title="Projects", icon=":material/folder:"),
    st.Page(page_productivity, title="Productivity", icon=":material/insights:"),
])

pg.run()
