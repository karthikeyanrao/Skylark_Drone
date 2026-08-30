"""Skylark Deal Tracker — AI-powered deal & work-order intelligence (White & Orange Theme)."""

from __future__ import annotations

import streamlit as st

from src.agent.analytical import SessionMemory, run_analytical_agent
from src.agent.llm_agent import run_llm_agent
from src.brief.leadership_brief import generate_leadership_brief
from src.config import (
    AGENT_MODE,
    BRAND_ORANGE,
    BRAND_ORANGE_DARK,
    DEALS_BOARD_ID,
    LLM_MODEL,
    WORK_ORDERS_BOARD_ID,
    monday_setup_missing,
    use_llm_agent,
    use_monday_api,
)
from src.data.loader import data_source_label

st.set_page_config(
    page_title="Skylark AI · Deal Tracker",
    page_icon="🟠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme Management ─────────────────────────────────────────────────────────

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "dark"


def get_theme_css(theme: str) -> str:
    is_dark = theme == "dark"

    bg_app = "#0B0E14" if is_dark else "#FDFDFD"
    bg_sidebar = "#111620" if is_dark else "#F7F8FA"
    bg_card = "#161C26" if is_dark else "#FFFFFF"
    bg_card_hover = "#1C2432" if is_dark else "#FFF9F5"
    text_primary = "#FFFFFF" if is_dark else "#1A1A1A"
    text_secondary = "#9AA5B8" if is_dark else "#5A6578"
    border_color = "rgba(255, 107, 0, 0.2)" if is_dark else "#FFE0CC"
    border_glow = "rgba(255, 107, 0, 0.4)" if is_dark else "rgba(255, 107, 0, 0.3)"
    chat_user_bg = "#1A2230" if is_dark else "#F5F7FA"
    chat_assistant_bg = "#131923" if is_dark else "#FFF8F2"
    stat_num_color = "#FF7A1A" if is_dark else "#E65A00"

    return f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        .stApp {{
            background-color: {bg_app};
            color: {text_primary};
        }}

        header[data-testid="stHeader"] {{
            background-color: {bg_app};
            border-bottom: 1px solid {border_color};
        }}

        [data-testid="stSidebar"] {{
            background-color: {bg_sidebar};
            border-right: 1px solid {border_color};
        }}

        [data-testid="stSidebar"] * {{
            color: {text_primary};
        }}

        h1, h2, h3, h4 {{
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 700 !important;
            color: {text_primary} !important;
            letter-spacing: -0.02em;
        }}

        .skylark-hero {{
            background: {bg_card};
            border: 1px solid {border_color};
            border-radius: 16px;
            padding: 1.75rem 2rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, {'0.35' if is_dark else '0.04'});
            position: relative;
            overflow: hidden;
        }}

        .skylark-hero::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, #FF6B00, #FF9E54, #FF6B00);
        }}

        .skylark-hero h1 {{
            margin: 0;
            color: #FF6B00 !important;
            font-size: 2.2rem;
            font-weight: 800 !important;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        .skylark-hero p {{
            margin: 0.4rem 0 0 0;
            color: {text_secondary};
            font-size: 1rem;
            font-weight: 400;
        }}

        .skylark-stat {{
            background: {bg_card};
            border: 1px solid {border_color};
            border-radius: 14px;
            padding: 1.25rem 1.5rem;
            text-align: left;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0, 0, 0, {'0.25' if is_dark else '0.03'});
        }}

        .skylark-stat:hover {{
            transform: translateY(-3px);
            border-color: #FF6B00;
            box-shadow: 0 10px 28px rgba(255, 107, 0, {'0.15' if is_dark else '0.1'});
            background: {bg_card_hover};
        }}

        .skylark-stat .lbl {{
            font-size: 0.82rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {text_secondary};
            margin-bottom: 0.35rem;
        }}

        .skylark-stat .num {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            font-weight: 700;
            color: {stat_num_color};
            line-height: 1.1;
        }}

        .skylark-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(255, 107, 0, 0.12);
            color: #FF7A1A;
            border: 1px solid rgba(255, 107, 0, 0.3);
            padding: 0.3rem 0.8rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }}

        .skylark-badge-pulse {{
            width: 7px;
            height: 7px;
            background-color: #FF6B00;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 8px #FF6B00;
        }}

        div[data-testid="stChatMessage"] {{
            background-color: {chat_assistant_bg};
            border: 1px solid {border_color};
            border-radius: 14px;
            padding: 1.25rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 12px rgba(0, 0, 0, {'0.2' if is_dark else '0.02'});
        }}

        div[data-testid="stChatMessage"][data-test-role="user"] {{
            background-color: {chat_user_bg};
            border: 1px solid rgba(255, 107, 0, 0.15);
        }}

        .stButton > button {{
            background-color: #FF6B00 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.6rem 1.2rem !important;
            transition: all 0.2s ease !important;
            box-shadow: 0 4px 14px rgba(255, 107, 0, 0.3) !important;
        }}

        .stButton > button:hover {{
            background-color: #E05E00 !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 20px rgba(255, 107, 0, 0.45) !important;
        }}

        .stTextInput > div > div > input,
        .stChatInput textarea {{
            background-color: {bg_card} !important;
            color: {text_primary} !important;
            border: 1.5px solid {border_color} !important;
            border-radius: 12px !important;
            font-size: 0.95rem !important;
            padding: 0.75rem 1rem !important;
            box-shadow: 0 4px 16px rgba(0, 0, 0, {'0.3' if is_dark else '0.03'}) !important;
        }}

        .stTextInput > div > div > input:focus,
        .stChatInput textarea:focus {{
            border-color: #FF6B00 !important;
            box-shadow: 0 0 0 3px {border_glow} !important;
        }}

        [data-testid="stChatInput"] {{
            padding-bottom: 1.25rem;
            background-color: transparent !important;
        }}

        .setup-banner {{
            background: {bg_card};
            border: 1.5px solid #FF6B00;
            border-radius: 16px;
            padding: 1.75rem 2rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 30px rgba(255, 107, 0, 0.15);
        }}

        code {{
            font-family: 'JetBrains Mono', monospace !important;
            color: #FF8533 !important;
            background: {'#1F2633' if is_dark else '#F0F2F5'} !important;
            padding: 0.15rem 0.4rem !important;
            border-radius: 6px !important;
        }}

        pre {{
            background: {'#12161F' if is_dark else '#F5F7FA'} !important;
            border: 1px solid {border_color} !important;
            border-radius: 10px !important;
            padding: 1rem !important;
        }}

        #MainMenu, footer, .viewerBadge_container {{
            visibility: hidden;
        }}
    </style>
    """


st.markdown(get_theme_css(st.session_state.theme_mode), unsafe_allow_html=True)


# ── Agent mode label ──────────────────────────────────────────────────────────

def _agent_label() -> str:
    if use_llm_agent():
        short = LLM_MODEL.split("/")[-1].upper()
        return short
    if AGENT_MODE == "llm":
        return "LLM (key missing)"
    return "ANALYTICAL"


# ── Session state ─────────────────────────────────────────────────────────────

def init_session() -> None:
    if "messages" not in st.session_state:
        data_note = (
            "Live **monday.com** data" if use_monday_api() else "⚠️ monday.com not yet connected"
        )
        agent_note = (
            f"**{_agent_label()}** AI agent" if use_llm_agent() else "analytical agent"
        )
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    f"👋 Welcome to **Skylark AI Deal Tracker**.\n\n"
                    f"Connected to {data_note} &amp; powered by {agent_note}.\n\n"
                    "Ask any open-ended question about pipeline, revenue, won deals, or work order operations. "
                    "Type **/brief** or click **Leadership Brief** in the sidebar for an executive snapshot."
                ),
            }
        ]
    if "memory" not in st.session_state:
        st.session_state.memory = SessionMemory()
    if "history" not in st.session_state:
        st.session_state.history = []


# ── Agent dispatch ────────────────────────────────────────────────────────────

def run_agent(prompt: str) -> str:
    memory: SessionMemory = st.session_state.memory
    if use_llm_agent():
        return run_llm_agent(prompt, memory, st.session_state.history)
    return run_analytical_agent(prompt, memory)


# ── Setup banner (shown when board IDs are missing) ──────────────────────────

def maybe_show_setup_banner() -> None:
    if not monday_setup_missing():
        return
    st.markdown(
        """
        <div class="setup-banner">
        <h3 style="color:#FF6B00;margin-top:0">⚙️ monday.com Setup Required</h3>
        <p>This app queries <strong>monday.com live boards</strong>. Add your board IDs to continue:</p>
        <ol>
          <li>Open your monday.com Deals board → copy the board ID from the URL
              (<code>https://app.monday.com/boards/<strong>1234567890</strong></code>)</li>
          <li>Repeat for the Work Orders board</li>
          <li>Add to <code>.env</code> (local) or Streamlit Cloud → <em>Secrets</em>:
              <pre>DEALS_BOARD_ID=1234567890
WORK_ORDERS_BOARD_ID=9876543210</pre>
          </li>
          <li>Restart / rerun the app</li>
        </ol>
        <p>Your <code>MONDAY_API_TOKEN</code> is already configured ✅</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────

def sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🟠 Skylark AI")
        agent_lbl = _agent_label()
        st.markdown(
            f'<span class="skylark-badge"><span class="skylark-badge-pulse"></span> MONDAY.COM LIVE</span> '
            f'<span class="skylark-badge">✦ {agent_lbl}</span>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        st.markdown("#### 🎨 Theme Mode")
        theme_choice = st.radio(
            "Select Theme",
            options=["🌙 Dark Mode", "☀️ Light Mode"],
            index=0 if st.session_state.theme_mode == "dark" else 1,
            label_visibility="collapsed",
            horizontal=True,
        )
        new_theme = "dark" if "Dark" in theme_choice else "light"
        if new_theme != st.session_state.theme_mode:
            st.session_state.theme_mode = new_theme
            st.rerun()

        st.markdown(f"**Data Source:** `{data_source_label()}`")
        if DEALS_BOARD_ID:
            st.caption(f"Deals Board: `#{DEALS_BOARD_ID}`")
        if WORK_ORDERS_BOARD_ID:
            st.caption(f"Work Orders Board: `#{WORK_ORDERS_BOARD_ID}`")

        st.markdown("---")
        st.markdown("#### 📊 Quick Actions")
        if st.button("📑 Executive Leadership Brief", use_container_width=True):
            try:
                brief = generate_leadership_brief()
            except Exception as exc:
                brief = f"⚠️ Could not generate brief — monday.com not connected yet. ({exc})"
            st.session_state.messages.append({"role": "user", "content": "/brief"})
            st.session_state.messages.append({"role": "assistant", "content": brief})
            st.rerun()

        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.session_state.history = []
            st.session_state.memory = SessionMemory()
            init_session()
            st.rerun()

        st.markdown("---")
        st.markdown("#### 💡 Example Questions")
        examples = [
            "What's our open pipeline by sector?",
            "How many deals have we won?",
            "Show work order execution status",
            "Any stuck invoices or billing issues?",
            "What's our revenue this quarter?",
            "How's pipeline looking for energy sector?",
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                st.session_state.pending_prompt = ex

        st.markdown("---")
        if not use_llm_agent():
            st.warning(
                "**AI agent disabled** — set `LLM_API_KEY` in `.env` to enable Gemini 2.5 Flash.",
                icon="🔑",
            )


# ── Hero + stats ──────────────────────────────────────────────────────────────

def hero_and_stats() -> None:
    st.markdown(
        """
        <div class="skylark-hero">
            <h1><span>🟠</span> Skylark Deal Tracker AI</h1>
            <p>Autonomous business intelligence for deal pipelines, revenue, and work order operations.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if monday_setup_missing():
        return

    try:
        from src.data.loader import get_deals, get_work_orders

        deals, _ = get_deals()
        wo, _ = get_work_orders()
        open_n = len(deals[deals["Deal Status"].isin(["Open", "On Hold"])])
        won_n = len(deals[deals["Deal Status"] == "Won"])
        pipeline_val = deals[deals["Deal Status"].isin(["Open", "On Hold"])]["Masked Deal value"].sum(
            min_count=1
        ) or 0

        c1, c2, c3, c4 = st.columns(4)
        stats = [
            ("Open Deals", open_n),
            ("Won Deals", won_n),
            ("Work Orders", len(wo)),
            ("Pipeline Value", f"₹{pipeline_val/1e7:.1f}Cr" if pipeline_val >= 1e7 else f"₹{pipeline_val/1e5:.1f}L"),
        ]
        for col, (lbl, num) in zip([c1, c2, c3, c4], stats):
            col.markdown(
                f"""
                <div class="skylark-stat">
                    <div class="lbl">{lbl}</div>
                    <div class="num">{num}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    except Exception as exc:
        st.info(f"Stats unavailable until monday.com is connected. ({exc})")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    init_session()
    sidebar()
    maybe_show_setup_banner()
    hero_and_stats()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🟠"):
            st.markdown(msg["content"])

    pending = st.session_state.pop("pending_prompt", None)
    prompt = pending or st.chat_input("Ask a founder question (e.g. 'How's pipeline looking for energy sector this quarter?')")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🟠"):
            with st.spinner("Analyzing live monday.com data…"):
                try:
                    if monday_setup_missing():
                        response = (
                            "⚠️ **monday.com board IDs are not configured yet.**\n\n"
                            "Please add `DEALS_BOARD_ID` and `WORK_ORDERS_BOARD_ID` to your `.env` "
                            "or Streamlit Cloud secrets, then refresh."
                        )
                    else:
                        response = run_agent(prompt)
                except Exception as exc:
                    response = f"⚠️ Data source error — please check your monday.com credentials and retry. `{exc}`"
            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.history.append({"role": "user", "content": prompt})
        st.session_state.history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
