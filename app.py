"""
app.py
======
NutriScan – Instant Ingredient Safety & Additive Scanner.
"""

from __future__ import annotations

import base64
import io
import os
from pathlib import Path
import time
import traceback
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from PIL import Image

# ── Load environment keys ───────────────────────────────────────────────────
env_file = Path(__file__).parent / ".env"
env_example = Path(__file__).parent / ".env.example"

if env_file.exists():
    load_dotenv(dotenv_path=env_file, override=True)
elif env_example.exists():
    load_dotenv(dotenv_path=env_example, override=True)
else:
    load_dotenv()

# ── Asset Helpers ────────────────────────────────────────────────────────────
_ASSETS_DIR = Path(__file__).parent / "assets"
_LOGO_PATH = _ASSETS_DIR / "logo.png"

def get_logo_base64() -> str:
    """Return base64 encoded string of the logo emblem."""
    if _LOGO_PATH.exists():
        try:
            with open(_LOGO_PATH, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass
    return ""

_LOGO_B64 = get_logo_base64()

# ── Page Configuration ───────────────────────────────────────────────────────
_fav = Image.open(_LOGO_PATH) if _LOGO_PATH.exists() else None
st.set_page_config(
    page_title="NutriScan",
    page_icon=_fav,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Declare Native Camera & Gallery Custom Component ─────────────────────────
_FRONTEND_DIR = Path(__file__).parent / "frontend"
_camera_gallery = components.declare_component(
    "camera_gallery_uploader",
    path=str(_FRONTEND_DIR),
)

# ─────────────────────────────────────────────────────────────────────────────
# Ultra-Modern Luxury Glassmorphism CSS
# ─────────────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

:root {
    --bg-main: #06090e;
    --bg-surface: rgba(15, 22, 36, 0.78);
    --bg-card: rgba(19, 29, 49, 0.65);
    --bg-glass: rgba(255, 255, 255, 0.03);
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-glow: rgba(6, 182, 212, 0.35);
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-emerald: #10b981;
    --accent-cyan: #06b6d4;
    --accent-blue: #3b82f6;
    --grade-a: #10b981;
    --grade-b: #14b8a6;
    --grade-c: #f59e0b;
    --grade-d: #f43f5e;
}

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    background-color: var(--bg-main) !important;
    color: var(--text-primary) !important;
}

.stApp {
    background: 
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(16, 185, 129, 0.15), transparent 70%),
        radial-gradient(ellipse 60% 40% at 85% 15%, rgba(6, 182, 212, 0.12), transparent 60%),
        radial-gradient(circle at 15% 85%, rgba(59, 130, 246, 0.08), transparent 50%),
        #06090e !important;
    background-attachment: fixed !important;
}

#MainMenu, footer, header { visibility: hidden; }

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2.5rem !important;
    padding-left: 0.9rem !important;
    padding-right: 0.9rem !important;
    max-width: 780px !important;
    margin: 0 auto !important;
}

/* ── Hero Box (Clean Header with Emblem Logo) ── */
.hero-box {
    background: var(--bg-surface);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: 24px;
    padding: 1.6rem 1.2rem 1.4rem;
    text-align: center;
    margin-bottom: 1.2rem;
    box-shadow: 0 16px 40px -12px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    position: relative;
    overflow: hidden;
}

.hero-box::before {
    content: '';
    position: absolute;
    top: 0;
    left: 20%;
    right: 20%;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.6), rgba(16, 185, 129, 0.6), transparent);
}

.logo-container {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    position: relative;
    margin-bottom: 0.85rem;
}

.logo-glow-ring {
    position: absolute;
    width: 88px;
    height: 88px;
    border-radius: 26px;
    background: linear-gradient(135deg, #10b981, #06b6d4, #3b82f6);
    filter: blur(14px);
    opacity: 0.55;
    animation: pulseGlow 4s ease-in-out infinite alternate;
}

@keyframes pulseGlow {
    0% { opacity: 0.4; transform: scale(0.96); }
    100% { opacity: 0.75; transform: scale(1.08); }
}

.app-logo-img {
    position: relative;
    width: 78px;
    height: 78px;
    border-radius: 22px;
    border: 1.5px solid rgba(255, 255, 255, 0.25);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5);
    object-fit: cover;
}

.hero-title {
    font-family: 'Outfit', sans-serif !important;
    font-size: 2.1rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0 0 0.3rem 0;
    background: linear-gradient(135deg, #ffffff 30%, #a5f3fc 70%, #6ee7b7 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.ny-tag {
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    font-weight: 800;
    background: linear-gradient(135deg, #10b981, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding: 2px 8px;
    border-radius: 8px;
    border: 1px solid rgba(6, 182, 212, 0.35);
    background-color: rgba(6, 182, 212, 0.08);
    letter-spacing: 0.5px;
}

.hero-subtitle {
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin: 0 0 0.75rem 0;
    font-weight: 500;
}

.hero-dev-tag {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: #67e8f9;
    background: rgba(6, 182, 212, 0.08);
    border: 1px solid rgba(6, 182, 212, 0.22);
    padding: 0.25rem 0.85rem;
    border-radius: 50px;
    text-transform: uppercase;
}

/* ── Compact Response Language Selector ── */
.lang-header {
    text-align: center;
    margin: -0.2rem 0 0.5rem;
}
.lang-label {
    font-size: 0.72rem;
    color: #64748b;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}

/* Language selector buttons */
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] .lang-btn button {
    min-height: 40px !important;
    height: 40px !important;
    padding: 0.2rem 0.6rem !important;
    font-size: 0.84rem !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    letter-spacing: 0.2px !important;
    transition: all 0.2s ease !important;
}

/* ── Grade Badge Card ── */
.grade-box {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.3rem;
    padding: 1.35rem 1.25rem;
    background: var(--bg-surface);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: 22px;
    margin-bottom: 0.95rem;
    box-shadow: 0 10px 32px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.grade-circle {
    width: 86px;
    height: 86px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Outfit', sans-serif;
    font-size: 2.8rem;
    font-weight: 900;
    flex-shrink: 0;
    position: relative;
}
.grade-circle.A { background: rgba(16, 185, 129, 0.15); border: 3px solid var(--grade-a); color: var(--grade-a); box-shadow: 0 0 28px rgba(16, 185, 129, 0.35); }
.grade-circle.B { background: rgba(20, 184, 166, 0.15); border: 3px solid var(--grade-b); color: var(--grade-b); box-shadow: 0 0 28px rgba(20, 184, 166, 0.35); }
.grade-circle.C { background: rgba(245, 158, 11, 0.15); border: 3px solid var(--grade-c); color: var(--grade-c); box-shadow: 0 0 28px rgba(245, 158, 11, 0.35); }
.grade-circle.D { background: rgba(244, 63, 94, 0.15); border: 3px solid var(--grade-d); color: var(--grade-d); box-shadow: 0 0 28px rgba(244, 63, 94, 0.35); }

.grade-info { flex: 1; min-width: 140px; }
.grade-name { font-family: 'Outfit', sans-serif; font-size: 1.25rem; font-weight: 800; letter-spacing: -0.2px; }
.grade-score { font-family: 'Outfit', sans-serif; font-size: 1.75rem; font-weight: 800; line-height: 1.1; margin: 0.15rem 0; }
.score-track { background: rgba(255, 255, 255, 0.08); height: 9px; border-radius: 50px; overflow: hidden; margin-top: 0.45rem; }
.score-fill { height: 100%; border-radius: 50px; }

/* ── Mobile Metrics Grid ── */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.55rem;
    margin-bottom: 0.95rem;
}
@media (max-width: 580px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
.stat-box {
    background: var(--bg-card);
    backdrop-filter: blur(14px);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 0.75rem 0.5rem;
    text-align: center;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}
.stat-val { font-family: 'Outfit', sans-serif; font-size: 1.45rem; font-weight: 800; }
.stat-lbl { font-size: 0.68rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 700; letter-spacing: 0.6px; }

/* ── Summary & Recommendation ── */
.verdict-box {
    background: rgba(6, 182, 212, 0.08);
    border: 1px solid rgba(6, 182, 212, 0.25);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.75rem;
    font-size: 0.9rem;
    line-height: 1.55;
    box-shadow: 0 4px 20px rgba(6, 182, 212, 0.08);
}
.action-box {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    margin-bottom: 0.95rem;
    font-size: 0.9rem;
    line-height: 1.55;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.08);
}
.allergen-banner {
    background: rgba(244, 63, 94, 0.1);
    border: 1px solid rgba(244, 63, 94, 0.35);
    border-radius: 14px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.95rem;
    font-size: 0.88rem;
    color: #fda4af;
    box-shadow: 0 4px 18px rgba(244, 63, 94, 0.12);
}
.unreadable-banner {
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 16px;
    padding: 1.2rem;
    margin-bottom: 1.1rem;
    font-size: 0.92rem;
    color: #fef08a;
    line-height: 1.55;
    text-align: center;
    box-shadow: 0 4px 24px rgba(245, 158, 11, 0.15);
}

/* ── Ingredient Item Card ── */
.ing-card {
    background: var(--bg-card);
    backdrop-filter: blur(14px);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 0.95rem 1rem;
    margin-bottom: 0.65rem;
    transition: transform 0.15s ease, border-color 0.15s ease;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2);
}
.ing-card:hover {
    border-color: rgba(255, 255, 255, 0.16);
    transform: translateY(-1px);
}
.ing-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.35rem;
}
.ing-title { font-weight: 700; font-size: 0.94rem; color: #ffffff; }
.ing-cat { font-size: 0.76rem; color: var(--text-secondary); }
.ing-details { font-size: 0.84rem; color: #cbd5e1; line-height: 1.45; margin-top: 0.35rem; }
.ing-status { font-size: 0.72rem; color: #64748b; margin-top: 0.3rem; font-family: monospace; }

/* ── Risk Chips ── */
.chip {
    padding: 0.22rem 0.65rem;
    border-radius: 50px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.3px;
}
.chip-safe { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
.chip-low { background: rgba(20, 184, 166, 0.18); color: #5eead4; border: 1px solid rgba(20, 184, 166, 0.35); }
.chip-mod { background: rgba(245, 158, 11, 0.18); color: #fde047; border: 1px solid rgba(245, 158, 11, 0.35); }
.chip-high { background: rgba(244, 63, 94, 0.18); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.35); }

/* ── Streamlit Buttons ── */
div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #059669 0%, #0d9488 50%, #0284c7 100%) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.25) !important;
    border-radius: 16px !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 4px 20px rgba(16, 185, 129, 0.35) !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stButton"] button[kind="secondary"] {
    background: rgba(19, 29, 49, 0.85) !important;
    color: #cbd5e1 !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 16px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    background: rgba(28, 41, 68, 0.95) !important;
    color: #ffffff !important;
    border-color: rgba(6, 182, 212, 0.4) !important;
}

/* ── Product Info Card (Barcode Scan) ── */
.product-banner {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    background: var(--bg-surface);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(6, 182, 212, 0.35);
    border-radius: 20px;
    padding: 1.1rem;
    margin-bottom: 1rem;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35), 0 0 20px rgba(6, 182, 212, 0.12);
}
.product-thumb {
    width: 72px;
    height: 72px;
    border-radius: 14px;
    object-fit: cover;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: #0b111e;
    flex-shrink: 0;
}
.product-thumb-placeholder {
    width: 72px;
    height: 72px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    background: rgba(6, 182, 212, 0.1);
    border: 1px solid rgba(6, 182, 212, 0.25);
    flex-shrink: 0;
}
.product-details { flex: 1; min-width: 0; }
.product-brand {
    font-size: 0.76rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #67e8f9;
    letter-spacing: 0.8px;
}
.product-name {
    font-family: 'Outfit', sans-serif;
    font-size: 1.25rem;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.25;
    margin: 0.15rem 0 0.4rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.product-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
}
.barcode-pill {
    font-size: 0.72rem;
    font-family: monospace;
    font-weight: 700;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 0.15rem 0.55rem;
    border-radius: 50px;
}
.nutri-pill {
    font-size: 0.72rem;
    font-weight: 800;
    padding: 0.15rem 0.55rem;
    border-radius: 50px;
    text-transform: uppercase;
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
}

/* ── Developer Badge (Footer) ── */
.dev-banner {
    text-align: center;
    margin-top: 2.8rem;
    margin-bottom: 1.2rem;
}
.dev-badge {
    display: inline-block;
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 182, 212, 0.12));
    border: 1px solid rgba(6, 182, 212, 0.35);
    color: #67e8f9;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 1.6px;
    padding: 0.5rem 1.4rem;
    border-radius: 50px;
    box-shadow: 0 0 20px rgba(6, 182, 212, 0.2);
    text-transform: uppercase;
}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Configurations & Grade Theme
# ─────────────────────────────────────────────────────────────────────────────

GRADE_INFO = {
    "A": {"name": "Excellent – Safe", "color": "#10b981", "fill": "linear-gradient(90deg, #059669, #10b981)", "desc": "Clean, natural & safe ingredients"},
    "B": {"name": "Good – Generally Safe", "color": "#14b8a6", "fill": "linear-gradient(90deg, #0d9488, #14b8a6)", "desc": "Permitted additives in safe moderation"},
    "C": {"name": "Caution – Moderate Risk", "color": "#f59e0b", "fill": "linear-gradient(90deg, #d97706, #f59e0b)", "desc": "Contains artificial sweeteners or additives"},
    "D": {"name": "Hazardous – High Risk", "color": "#f43f5e", "fill": "linear-gradient(90deg, #e11d48, #f43f5e)", "desc": "Highly ultra-processed / harmful additives"},
    "SPEC VERIFIED": {"name": "Verified Specifications", "color": "#38bdf8", "fill": "linear-gradient(90deg, #0284c7, #38bdf8)", "desc": "Non-food item. Technical specifications verified."},
    "CAUTION": {"name": "Handling Safety", "color": "#f59e0b", "fill": "linear-gradient(90deg, #d97706, #f59e0b)", "desc": "Household formulation. Follow safety handling precautions."},
    "REGULATED": {"name": "Regulated Product", "color": "#38bdf8", "fill": "linear-gradient(90deg, #0284c7, #38bdf8)", "desc": "Pharmaceutical item. Consult physician for dosage."},
}


def _get_key(name: str) -> str:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, "").strip()


def get_ai_engine(custom_g: str = ""):
    import importlib
    import ai_handler
    importlib.reload(ai_handler)
    from ai_handler import IngredientSafetyAI

    gk = custom_g or _get_key("GEMINI_API_KEY")
    sig = f"{gk}:v6"

    if "ai_engine" not in st.session_state or st.session_state.get("_sig") != sig:
        try:
            st.session_state["ai_engine"] = IngredientSafetyAI(gemini_key=gk)
            st.session_state["_sig"] = sig
            st.session_state.pop("ai_err", None)
        except Exception as exc:
            st.session_state["ai_err"] = str(exc)
            st.session_state.pop("ai_engine", None)
            return None

    return st.session_state.get("ai_engine")


# ─────────────────────────────────────────────────────────────────────────────
# Render Clean Results
# ─────────────────────────────────────────────────────────────────────────────

def render_results(data: dict) -> None:
    # Handle Barcode Not Found
    if data.get("found") is False:
        bcode = data.get("barcode", "Unknown")
        msg = data.get("message", f"Barcode #{bcode} not found in database.")
        prompt = data.get("action_prompt", "Please capture a clear photo of the ingredient list!")
        st.markdown(f"""
        <div class="unreadable-banner" style="border-color:rgba(245,158,11,0.45);background:rgba(245,158,11,0.1)">
            <div style="font-size:1.1rem;font-weight:800;letter-spacing:1px;color:#fef08a;margin-bottom:0.4rem;">[UNVERIFIED BARCODE]</div>
            <strong style="font-size:1.1rem;color:#fef08a;">{msg}</strong>
            <div style="font-size:0.9rem;color:#fde68a;margin-top:0.45rem;">{prompt}</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Handle Verified Non-Food Item (Hardware, Tools, Electronics, Consumer Goods)
    if data.get("has_ingredients") is False and (data.get("overall_grade") == "SPEC VERIFIED" or not (data.get("analysis_rules") or {}).get("supports_ingredients", True)):
        p_info = data.get("product_info", {})
        p_name = p_info.get("name", "Product")
        p_brand = p_info.get("brand", "")
        p_img = p_info.get("image_url", "")
        bcode = data.get("barcode", "")
        specs = data.get("specifications") or p_info.get("specifications") or "Technical specifications verified."
        cat = data.get("category") or p_info.get("category") or "Manufactured Product"
        summary = data.get("summary") or f"Verified {cat} specifications."
        rec = data.get("recommendation") or "Follow manufacturer safety guidelines."

        img_html = f'<img src="{p_img}" class="product-thumb" alt="{p_name}" />' if p_img else '<div class="product-thumb-placeholder">ITEM</div>'

        st.markdown(f"""
        <div class="product-banner">
            {img_html}
            <div class="product-details">
                <div class="product-brand">{p_brand}</div>
                <div class="product-name">{p_name}</div>
                <div class="product-meta-row">
                    <span class="barcode-pill">BARCODE: {bcode}</span>
                    <span class="barcode-pill" style="background:rgba(6,182,212,0.2);color:#38bdf8;">{cat}</span>
                </div>
            </div>
        </div>
        <div class="unreadable-banner" style="border-color:rgba(6,182,212,0.4);background:rgba(6,182,212,0.08);">
            <div style="font-size:1rem;font-weight:700;color:#38bdf8;margin-bottom:0.3rem;">[VERIFIED SPECIFICATIONS]</div>
            <strong style="font-size:0.95rem;color:#f8fafc;">{summary}</strong>
            <div style="font-size:0.86rem;color:#94a3b8;margin-top:0.35rem;">{specs}</div>
            <div style="font-size:0.86rem;color:#34d399;margin-top:0.35rem;">{rec}</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Handle Barcode found but missing ingredients (Food / Consumable)
    if data.get("has_ingredients") is False:
        p_info = data.get("product_info", {})
        p_name = p_info.get("name", "Product")
        p_brand = p_info.get("brand", "")
        p_img = p_info.get("image_url", "")
        bcode = data.get("barcode", "")
        img_html = f'<img src="{p_img}" class="product-thumb" alt="{p_name}" />' if p_img else '<div class="product-thumb-placeholder">PRODUCT</div>'

        st.markdown(f"""
        <div class="product-banner">
            {img_html}
            <div class="product-details">
                <div class="product-brand">{p_brand}</div>
                <div class="product-name">{p_name}</div>
                <div class="product-meta-row">
                    <span class="barcode-pill">BARCODE: {bcode}</span>
                </div>
            </div>
        </div>
        <div class="unreadable-banner">
            <strong style="font-size:1rem;color:#fef08a;">Ingredient list missing in database</strong>
            <div style="font-size:0.86rem;color:#fde68a;margin-top:0.35rem;">
                Please capture a photo of the back label to analyze this product's health safety!
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Handle Unreadable OCR
    if data.get("is_unreadable", False):
        summary = data.get("summary", "Some ingredients could not be read clearly. Please upload a sharper label photo.")
        rec = data.get("recommendation", "Please capture a clear, well-lit photo of the ingredient list.")
        st.markdown(f"""
        <div class="unreadable-banner">
            <div style="font-size:1.1rem;font-weight:800;letter-spacing:1px;color:#67e8f9;margin-bottom:0.4rem;">[INGREDIENT OCR]</div>
            <strong style="font-size:1.05rem;color:#fef08a;">{summary}</strong>
            <div style="font-size:0.88rem;color:#fde68a;margin-top:0.4rem;">{rec}</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Render Scanned Product Card (if available from Barcode)
    p_info = data.get("product_info")
    if p_info and p_info.get("name"):
        p_name = p_info.get("name")
        p_brand = p_info.get("brand", "Packaged Food")
        p_img = p_info.get("image_url", "")
        p_nutri = p_info.get("nutriscore", "")
        bcode = p_info.get("barcode") or data.get("barcode", "")

        img_html = f'<img src="{p_img}" class="product-thumb" alt="{p_name}" />' if p_img else '<div class="product-thumb-placeholder"></div>'
        nutri_html = f'<span class="nutri-pill">Nutri-Score: {p_nutri}</span>' if p_nutri else ''

        st.markdown(f"""
        <div class="product-banner">
            {img_html}
            <div class="product-details">
                <div class="product-brand">{p_brand}</div>
                <div class="product-name">{p_name}</div>
                <div class="product-meta-row">
                    <span class="barcode-pill">BARCODE: {bcode}</span>
                    {nutri_html}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    grade = data.get("overall_grade", "C").upper()
    score = data.get("overall_score", 50)
    info = GRADE_INFO.get(grade, GRADE_INFO["C"])

    total = data.get("total_ingredients_found", 0)
    concerning = data.get("concerning_ingredients_count", 0)
    allergens = data.get("allergens_detected", [])
    safe_count = max(0, total - concerning)

    # Grade Card
    st.markdown(f"""
    <div class="grade-box">
        <div class="grade-circle {grade}">{grade}</div>
        <div class="grade-info">
            <div class="grade-name" style="color:{info['color']}">{info['name']}</div>
            <div class="grade-score" style="color:{info['color']}">{score} <span style="font-size:0.9rem;color:#94a3b8">/ 100</span></div>
            <div style="font-size:0.8rem;color:#94a3b8">{info['desc']}</div>
            <div class="score-track">
                <div class="score-fill" style="width:{max(5, min(100, score))}%;background:{info['fill']}"></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Metrics Grid
    st.markdown(f"""
    <div class="stats-grid">
        <div class="stat-box"><div class="stat-val" style="color:#38bdf8">{total}</div><div class="stat-lbl">Total</div></div>
        <div class="stat-box"><div class="stat-val" style="color:#34d399">{safe_count}</div><div class="stat-lbl">Safe</div></div>
        <div class="stat-box"><div class="stat-val" style="color:#fb7185">{concerning}</div><div class="stat-lbl">Concerning</div></div>
        <div class="stat-box"><div class="stat-val" style="color:#fde047">{len(allergens)}</div><div class="stat-lbl">Allergens</div></div>
    </div>
    """, unsafe_allow_html=True)

    # Allergen Alert
    if allergens:
        st.markdown(f"""
        <div class="allergen-banner">
            <strong>ALLERGEN ALERT:</strong> {', '.join(allergens)}
        </div>
        """, unsafe_allow_html=True)

    # Summary
    summary = data.get("summary", "")
    rec = data.get("recommendation", "")
    if summary:
        st.markdown(f"""
        <div class="verdict-box">
            <strong style="color:#67e8f9">Chemical Audit:</strong> {summary}
        </div>
        """, unsafe_allow_html=True)

    if rec:
        st.markdown(f"""
        <div class="action-box">
            <strong style="color:#6ee7b7">Safety Advice:</strong> {rec}
        </div>
        """, unsafe_allow_html=True)

    # Ingredient Cards
    ingredients = data.get("ingredients", [])
    if ingredients:
        st.markdown("<h4 style='margin:1.4rem 0 0.7rem 0;font-size:1.05rem;font-weight:800;letter-spacing:-0.2px'> Ingredient Breakdown</h4>", unsafe_allow_html=True)

        for item in ingredients:
            name = item.get("name", "Unknown")
            cat = item.get("category", "General")
            risk = item.get("risk_level", "Safe")
            side_fx = item.get("side_effects", "Safe for regular consumption")
            reg = item.get("regulatory_status", "Approved")
            icon = item.get("icon", "")

            if "Safe" in risk:
                chip_class = "chip-safe"
            elif "Low" in risk:
                chip_class = "chip-low"
            elif "Moderate" in risk:
                chip_class = "chip-mod"
            else:
                chip_class = "chip-high"

            st.markdown(f"""
            <div class="ing-card">
                <div class="ing-header">
                    <div>
                        <span class="ing-title">{icon} {name}</span>
                        <span class="ing-cat"> · {cat}</span>
                    </div>
                    <span class="chip {chip_class}">{risk}</span>
                </div>
                <div class="ing-details">{side_fx}</div>
                <div class="ing-status">{reg}</div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[str, str]:
    with st.sidebar:
        logo_html = f'<img src="data:image/png;base64,{_LOGO_B64}" style="width:48px;height:48px;border-radius:14px;box-shadow:0 0 16px rgba(6,182,212,0.35);margin-bottom:0.4rem;border:1px solid rgba(255,255,255,0.2)" />' if _LOGO_B64 else '<div style="font-size:1.8rem">NUTRISCAN</div>'
        st.markdown(f"""
        <div style="text-align:center;padding:0.5rem 0 1rem;">
            {logo_html}
            <div style="font-weight:800;font-size:1rem;letter-spacing:0.5px">NutriScan</div>
            <div style="font-size:0.75rem;color:#67e8f9;letter-spacing:1px;font-weight:700">AI INGREDIENT & BARCODE SCANNER</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Engine Status
        ai = st.session_state.get("ai_engine")
        if ai:
            st.markdown("**AI Analysis Engine**: `Active & Ready`")
            st.markdown("**Barcode Scanner**: `Open Food Facts Global`")
            st.markdown("**Safety Scoring**: `Deterministic Rules Engine`")
        else:
            st.markdown("**AI Analysis Engine**: `Initializing...`")

        st.divider()

        # Optional Custom Key
        with st.expander("Override API Key", expanded=False):
            cg = st.text_input("Gemini API Key", type="password", value=st.session_state.get("c_gemini", _get_key("GEMINI_API_KEY")), key="c_gemini")
            if st.button("Save Key", use_container_width=True, type="secondary"):
                st.session_state.pop("ai_engine", None)
                st.session_state["_sig"] = None
                st.success("Key updated!")
                st.rerun()

        st.markdown("""
        <div style="font-size:0.72rem;color:#64748b;text-align:center;margin-top:2rem">
            <strong>NutriScan Pro</strong><br>
            AI Food & Barcode Safety Scanner
        </div>
        """, unsafe_allow_html=True)

    return st.session_state.get("c_gemini", "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Sidebar
    custom_gemini = render_sidebar()

    # Premium Hero Header with AI Logo Emblem
    logo_markup = f"""
    <div class="logo-container">
        <div class="logo-glow-ring"></div>
        <img src="data:image/png;base64,{_LOGO_B64}" class="app-logo-img" alt="NutriScan Logo Emblem" />
    </div>
    """ if _LOGO_B64 else '<div style="font-size:3rem;margin-bottom:0.5rem">NUTRISCAN</div>'

    st.markdown(f"""
    <div class="hero-box">
        {logo_markup}
        <h1 class="hero-title">NutriScan <span class="ny-tag">NY</span></h1>
        <p class="hero-subtitle">Smart AI Barcode, Line Code & Ingredient Safety Scanner</p>
        <div class="hero-dev-tag">UNIVERSAL CHEMICAL & INGREDIENT SCANNER</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Compact Response Language Selector ───────────────────────────────────
    st.markdown("""
    <div class="lang-header">
        <span class="lang-label">Response Language</span>
    </div>
    """, unsafe_allow_html=True)

    if "language" not in st.session_state:
        st.session_state["language"] = "Hinglish"

    lang_col1, lang_col2, lang_col3 = st.columns(3)
    curr_lang = st.session_state["language"]

    with lang_col1:
        st.markdown('<div class="lang-btn">', unsafe_allow_html=True)
        if st.button("English", key="lang_en", use_container_width=True,
                     type="primary" if curr_lang == "English" else "secondary"):
            if st.session_state["language"] != "English":
                st.session_state["language"] = "English"
                st.session_state["_lang_changed"] = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with lang_col2:
        st.markdown('<div class="lang-btn">', unsafe_allow_html=True)
        if st.button("Hindi", key="lang_hi", use_container_width=True,
                     type="primary" if curr_lang == "Hindi" else "secondary"):
            if st.session_state["language"] != "Hindi":
                st.session_state["language"] = "Hindi"
                st.session_state["_lang_changed"] = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with lang_col3:
        st.markdown('<div class="lang-btn">', unsafe_allow_html=True)
        if st.button("Hinglish", key="lang_hl", use_container_width=True,
                     type="primary" if curr_lang == "Hinglish" else "secondary"):
            if st.session_state["language"] != "Hinglish":
                st.session_state["language"] = "Hinglish"
                st.session_state["_lang_changed"] = True
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Initialize AI
    ai = get_ai_engine(custom_gemini)

    if ai is None:
        st.markdown("""
        <div class="allergen-banner" style="color:#fde047;border-color:#f59e0b">
            <strong>API Key Required</strong><br>
            Please configure GEMINI_API_KEY in your environment or Streamlit Secrets.
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # ── Real-Time Barcode & Label Camera Custom Component ────────────────────
    uploader_val = _camera_gallery(key="native_cam_gal")

    # ── Process incoming payload (Barcode or Image) ──────────────────────────
    new_scan_arrived = False
    if uploader_val and isinstance(uploader_val, dict):
        ts = uploader_val.get("timestamp")
        if ts and ts != st.session_state.get("_last_ts"):
            st.session_state["_last_ts"] = ts

            # 1. Barcode Payload
            if uploader_val.get("type") == "barcode" or "barcode" in uploader_val:
                bcode = str(uploader_val.get("barcode", "")).strip()
                if bcode:
                    st.session_state["active_barcode"] = bcode
                    st.session_state.pop("active_image", None)
                    st.session_state.pop("scan_data", None)
                    new_scan_arrived = True

            # 2. Image Payload
            elif uploader_val.get("type") == "image" or "data" in uploader_val:
                raw_b64 = uploader_val.get("data", "")
                if "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                try:
                    img_bytes = base64.b64decode(raw_b64)
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    st.session_state["active_image"] = img
                    st.session_state["active_source"] = uploader_val.get("source", "camera")
                    st.session_state.pop("active_barcode", None)
                    st.session_state.pop("scan_data", None)
                    new_scan_arrived = True
                except Exception as e:
                    st.error(f"Could not load image: {e}")

    active_barcode: str | None = st.session_state.get("active_barcode")
    active_img: Image.Image | None = st.session_state.get("active_image")
    lang_changed = st.session_state.pop("_lang_changed", False)

    # ── Trigger Automatic Analysis ───────────────────────────────────────────
    if (new_scan_arrived or lang_changed or ("scan_data" not in st.session_state and (active_barcode or active_img))):
        lang = st.session_state.get("language", "Hinglish")

        if active_barcode:
            spinner_msg = {
                "English":  f"Fetching product details for Barcode {active_barcode}…",
                "Hindi":    f"बारकोड {active_barcode} से उत्पाद की जानकारी प्राप्त हो रही है…",
                "Hinglish": f"Barcode {active_barcode} se product details fetch ho rahi hain…",
            }.get(lang, "Fetching product details…")

            with st.spinner(spinner_msg):
                try:
                    res = ai.fetch_and_analyze_barcode(active_barcode, language=lang)
                    st.session_state["scan_data"] = res
                except Exception as exc:
                    st.error(f"Barcode fetch failed: {exc}")
                    with st.expander("Details"):
                        st.code(traceback.format_exc())

        elif active_img is not None:
            spinner_msg = {
                "English":  "Analyzing ingredients…",
                "Hindi":    "सामग्रियों का विश्लेषण हो रहा है…",
                "Hinglish": "Ingredients ka analysis ho raha hai…",
            }.get(lang, "Analyzing ingredients…")

            with st.spinner(spinner_msg):
                try:
                    res = ai.analyze_image(active_img, language=lang)
                    st.session_state["scan_data"] = res
                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")
                    with st.expander("Details"):
                        st.code(traceback.format_exc())

    # ── Active State Preview & Clear / Retake Option ──────────────────────────
    if active_img is not None:
        source = st.session_state.get("active_source", "camera")
        source_label = "Captured from Camera" if source == "camera" else "Selected from Gallery"

        st.markdown(f"""
        <div style="background:var(--bg-card);border:1px solid rgba(6,182,212,0.4);border-radius:16px;
                    padding:0.6rem 1rem;margin:0.8rem 0 0.6rem;text-align:center;box-shadow:0 0 20px rgba(6,182,212,0.15)">
            <span style="font-size:0.85rem;font-weight:700;color:#67e8f9;letter-spacing:0.5px;">
                {source_label}
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.image(active_img, caption="Product Label", use_container_width=True)

        if st.button("Scan Another Item", key="btn_retake_img", type="secondary", use_container_width=True):
            st.session_state.pop("active_image", None)
            st.session_state.pop("active_barcode", None)
            st.session_state.pop("scan_data", None)
            st.session_state.pop("_last_ts", None)
            st.rerun()

    elif active_barcode is not None:
        if st.button("Scan Another Item", key="btn_retake_bc", type="secondary", use_container_width=True):
            st.session_state.pop("active_barcode", None)
            st.session_state.pop("active_image", None)
            st.session_state.pop("scan_data", None)
            st.session_state.pop("_last_ts", None)
            st.rerun()

    # ── Results Display ───────────────────────────────────────────────────────
    if "scan_data" in st.session_state:
        st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:1.4rem 0;'>", unsafe_allow_html=True)
        render_results(st.session_state["scan_data"])

    # ── Bottom Developer Banner ───────────────────────────────────────────────
    st.markdown("""
    <div class="dev-banner">
        <span class="dev-badge">NutriScan · NY</span>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
