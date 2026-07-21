import streamlit as st
import json
import time
import os
import socket
import subprocess
from pathlib import Path
from config import OPENAI_MODEL, OPENAI_API_BASE

st.set_page_config(page_title="Helio Architect", page_icon="", layout="wide", initial_sidebar_state="expanded", menu_items={})

AGENT_PORT = 9876

def agent_alive():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(('127.0.0.1', AGENT_PORT))
        s.close()
        return True
    except:
        return False

def agent_send(cmd, timeout=180):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(('127.0.0.1', AGENT_PORT))
    s.sendall(json.dumps(cmd).encode() + b'\n')
    data = b''
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
        except socket.timeout:
            break
    s.close()
    return json.loads(data.decode()) if data else {"status": "error", "msg": "sin respuesta"}

import llm as _llm

def generate_plan(prompt):
    return _llm.generate_plan(prompt)

def refine_plan(current_plan, change):
    return _llm.refine_plan(current_plan, change)

def load_saved_projects():
    renders_dir = Path(__file__).parent / "renders"
    if not renders_dir.exists():
        return []
    plans = []
    for f in renders_dir.glob("plan_*.json"):
        try:
            parts = f.stem.split("_")
            if len(parts) < 2:
                continue
            ts_str = parts[1]
            ts = int(ts_str)
            with open(f, "r", encoding="utf-8") as pf:
                data = json.load(pf)
            # Find matching image
            img_path = renders_dir / f"design_{ts}.png"
            plans.append({
                "ts": ts,
                "name": data.get("project") or data.get("desc") or "Sin título",
                "plan": data,
                "img_path": str(img_path) if img_path.exists() else None,
                "plan_path": str(f)
            })
        except Exception as e:
            pass
    # Sort by timestamp descending
    plans.sort(key=lambda x: x["ts"], reverse=True)
    return plans

if "messages" not in st.session_state: st.session_state.messages = []
if "current_plan" not in st.session_state: st.session_state.current_plan = None
if "available_projects" not in st.session_state: st.session_state.available_projects = []

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Base Reset & Core Fonts */
    * { 
        font-family: 'Inter', -apple-system, system-ui, sans-serif; 
        margin: 0; 
        padding: 0; 
        box-sizing: border-box; 
    }

    /* Clean solid dark background for the app */
    .stApp {
        background-color: #212121 !important;
        color: #ececec !important;
    }
    
    /* Center the main container to match vertical grid layout (ChatGPT style) */
    .main > div { padding: 0 !important; max-width: 100% !important; }
    .block-container { 
        padding-top: 3rem !important;
        padding-bottom: 10rem !important; 
        max-width: 800px !important; 
        margin: 0 auto !important; 
    }

    /* Hide standard Streamlit header/footer decorations */
    #MainMenu, footer { display: none !important; }
    .stDeployButton { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }

    /* Transparent top header for the hamburger sidebar toggle button */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
        color: #ececec !important;
    }
    header[data-testid="stHeader"] button {
        color: #ececec !important;
    }

    /* Sidebar - Clean charcoal black aesthetic */
    [data-testid="stSidebar"] {
        background-color: #171717 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    [data-testid="stSidebarUserContent"] {
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
        padding: 1.5rem 1rem !important;
    }

    /* Sidebar "New Chat" Pill Button */
    .sidebar-new-btn .stButton > button {
        background-color: transparent !important;
        border: 1px solid #3f3f46 !important;
        color: #ececec !important;
        border-radius: 24px !important;
        padding: 0.6rem 1.2rem !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        width: 100%;
        transition: all 0.2s ease !important;
    }
    .sidebar-new-btn .stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border-color: #5f5f66 !important;
        color: #ffffff !important;
    }

    /* Sidebar Projects History Section */
    .sidebar-section-title {
        padding: 1.5rem 0.5rem 0.5rem 0.5rem;
        font-size: 0.75rem;
        color: #8e8e93;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 600;
    }
    .sidebar-history-container {
        display: flex;
        flex-direction: column;
        gap: 4px;
        max-height: 48vh;
        overflow-y: auto;
        padding: 0.25rem 0;
    }
    .sidebar-history-container .stButton > button {
        background-color: transparent !important;
        border: none !important;
        color: #b4b4b4 !important;
        text-align: left !important;
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        padding: 0.6rem 0.75rem !important;
        border-radius: 8px !important;
        justify-content: flex-start !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: block !important;
        width: 100% !important;
        transition: all 0.15s ease !important;
    }
    .sidebar-history-container .stButton > button:hover {
        background-color: #2f2f2f !important;
        color: #ffffff !important;
    }

    /* Sidebar Footer Status Card at the Bottom */
    .sidebar-footer {
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        padding-top: 1.25rem;
        margin-top: auto !important;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        background-color: #171717;
    }
    .status-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.8rem;
        color: #ececec;
    }
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }
    .status-dot.alive {
        background-color: #10a37f;
        box-shadow: 0 0 8px rgba(16, 163, 127, 0.6);
    }
    .status-dot.dead {
        background-color: #ef4444;
        box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
    }
    .model-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.75rem;
        color: #9b9b9b;
    }
    .model-icon {
        opacity: 0.7;
    }

    /* Chat Messages Layout (ChatGPT Clean Style) */
    .stChatMessage {
        background: transparent !important;
        padding: 1.25rem 0 !important;
        border: none !important;
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 auto !important;
    }
    
    /* User Message Bubble styling */
    div[data-testid="stChatMessage"]:has(.msg-indicator-user) {
        flex-direction: row-reverse !important;
    }
    div[data-testid="stChatMessage"]:has(.msg-indicator-user) [data-testid="chatMessageContent"] {
        background-color: #2f2f2f !important;
        border: none !important;
        border-radius: 20px !important;
        padding: 0.85rem 1.35rem !important;
        max-width: 75% !important;
        margin-left: auto !important;
        color: #ececec !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }
    @media (max-width: 768px) {
        div[data-testid="stChatMessage"]:has(.msg-indicator-user) [data-testid="chatMessageContent"] {
            max-width: 85% !important;
        }
    }
    /* Avatar styling */
    [data-testid="chatMessageAvatar"] {
        width: 34px !important;
        height: 34px !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 18px !important;
        line-height: 1 !important;
        flex-shrink: 0 !important;
    }
    div[data-testid="stChatMessage"]:has(.msg-indicator-user) [data-testid="chatMessageAvatar"] {
        background: #7c3aed !important;
    }
    div[data-testid="stChatMessage"]:has(.msg-indicator-assistant) [data-testid="chatMessageAvatar"] {
        background: #10a37f !important;
    }

    /* Assistant Message Bubble styling */
    div[data-testid="stChatMessage"]:has(.msg-indicator-assistant) [data-testid="chatMessageContent"] {
        background-color: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0.75rem 0 !important;
        max-width: 100% !important;
        color: #ececec !important;
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }
    
    /* Spacing between markdown elements inside assistant messages */
    .stChatMessage [data-testid="chatMessageContent"] p {
        margin-bottom: 0.85rem !important;
    }
    .stChatMessage [data-testid="chatMessageContent"] p:last-child {
        margin-bottom: 0 !important;
    }

    /* Chat Input Styling - Large, Correct, Spacious input */
    [data-testid="stChatInput"] {
        background-color: transparent !important;
        border: none !important;
        padding: 1.5rem 0 !important;
    }
    [data-testid="stChatInput"] > div {
        background-color: #2f2f2f !important;
        border: 1px solid #3f3f46 !important;
        border-radius: 28px !important; /* Rounded pill styling */
        padding: 0.5rem 0.75rem !important; /* More spacious padding */
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25) !important;
        max-width: 800px !important;
        width: 100% !important; /* Force to take full layout width */
        margin: 0 auto !important;
        transition: border-color 0.25s, box-shadow 0.25s !important;
    }
    [data-testid="stChatInput"] > div:focus-within {
        border-color: #5f5f66 !important;
        box-shadow: 0 4px 28px rgba(0, 0, 0, 0.35) !important;
    }
    /* Stretch input elements to occupy the full width of the bar */
    [data-testid="stChatInput"] > div > div {
        flex-grow: 1 !important;
        width: 100% !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #ececec !important;
        background-color: transparent !important;
        border: none !important;
        font-size: 1rem !important; /* Larger text for comfortable writing */
        line-height: 1.6 !important;
        padding: 0.8rem 1rem !important; /* Large interior padding */
        box-shadow: none !important;
        outline: none !important;
        resize: none !important;
        width: 100% !important;
        min-height: 52px !important; /* Correct large minimum height */
    }
    [data-testid="stChatInput"] textarea:focus {
        box-shadow: none !important;
        outline: none !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #8e8e93 !important;
    }
    [data-testid="stChatInput"] button {
        background-color: #ececec !important;
        color: #212121 !important;
        border-radius: 50% !important;
        width: 36px !important; /* Larger send button */
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
        margin-right: 4px !important;
    }
    [data-testid="stChatInput"] button:hover {
        background-color: #ffffff !important;
        transform: scale(1.05);
    }

    /* Welcome Screen (ChatGPT style) */
    .welcome-container {
        display: flex; 
        flex-direction: column;
        align-items: center; 
        justify-content: center;
        min-height: 30vh; 
        text-align: center;
        padding: 2rem 1rem 1rem 1rem;
        max-width: 100%;
        margin: 0 auto;
    }
    .welcome-logo {
        width: 64px; 
        height: 64px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background-color: #2f2f2f;
        border: 1px solid #3f3f46;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: transform 0.3s ease;
    }
    .welcome-logo:hover {
        transform: scale(1.05) rotate(5deg);
    }
    .welcome-title {
        font-size: 2.2rem; 
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 0.5rem;
        letter-spacing: -0.5px;
    }
    .welcome-sub {
        font-size: 0.95rem; 
        color: #b4b4b4;
        margin-bottom: 2rem;
        max-width: 520px;
        line-height: 1.5;
    }

    /* Suggestion Grid for 2x2 layout in main area */
    .suggestion-container {
        max-width: 100%;
        margin: 0 auto;
        padding: 0 1.5rem;
    }
    .suggestion-container .stButton > button {
        background-color: #2f2f2f !important;
        border: 1px solid #3f3f46 !important;
        color: #ececec !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        min-height: 80px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important;
        white-space: pre-line !important;
        width: 100%;
        line-height: 1.4 !important;
    }
    /* Force text alignment inside Streamlit buttons to be left-aligned and column styled */
    .suggestion-container .stButton > button > div,
    .suggestion-container .stButton > button span,
    .suggestion-container .stButton > button p {
        text-align: left !important;
        justify-content: flex-start !important;
        align-items: flex-start !important;
        display: flex !important;
        flex-direction: column !important;
        width: 100% !important;
        margin: 0 !important;
    }
    .suggestion-container .stButton > button:hover {
        background-color: #35363a !important;
        border-color: #52525b !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.2) !important;
    }

    /* Plan details Card */
    .plan-header {
        font-size: 1.05rem; 
        font-weight: 600;
        color: #ffffff; 
        margin-bottom: 0.5rem;
    }
    .plan-meta {
        font-size: 0.8rem; 
        color: #b4b4b4;
        display: flex; 
        gap: 8px; 
        flex-wrap: wrap;
        margin: 0.5rem 0;
    }
    .plan-meta span {
        background-color: #3e3e42;
        color: #ececec;
        padding: 0.2rem 0.6rem; 
        border-radius: 6px;
    }

    /* Image Render Card */
    .render-card {
        border-radius: 12px; 
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin: 1rem 0;
        box-shadow: 0 8px 30px rgba(0,0,0,0.3);
        transition: border-color 0.2s;
    }
    .render-card:hover {
        border-color: #5f5f66;
    }

    /* Loading Status Cards & SVG Spinner */
    .status-card {
        background-color: #2f2f2f;
        border: 1px solid #3f3f46;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    .status-card.pulse {
        animation: pulse 2s ease-in-out infinite;
        display: flex;
        flex-direction: row;
        align-items: center;
        gap: 14px;
    }
    .status-card-text {
        display: flex;
        flex-direction: column;
    }
    .status-card-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #ffffff;
    }
    .status-card-desc {
        font-size: 0.8rem;
        color: #b4b4b4;
    }
    
    .spinner {
        animation: rotate 2s linear infinite;
        width: 24px;
        height: 24px;
        flex-shrink: 0;
    }
    .spinner .path {
        stroke: #10a37f;
        stroke-linecap: round;
        animation: dash 1.5s ease-in-out infinite;
    }

    /* Global scrollbars */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

    /* Animations */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    .pulse { animation: pulse 2s ease-in-out infinite; }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .fade-in { animation: fadeIn 0.4s ease-out; }

    @keyframes rotate {
        100% { transform: rotate(360deg); }
    }
    @keyframes dash {
        0% { stroke-dasharray: 1, 150; stroke-dashoffset: 0; }
        50% { stroke-dasharray: 90, 150; stroke-dashoffset: -35; }
        100% { stroke-dasharray: 90, 150; stroke-dashoffset: -124; }
    }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
    <div style="padding: 0.5rem 0.5rem 1rem; display: flex; align-items: center; gap: 10px;">
        <div style="width:30px;height:30px;border-radius:50%;background-color:#10a37f;display:flex;align-items:center;justify-content:center;">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#ffffff" stroke-width="2">
                <path d="M3 21h18M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/>
            </svg>
        </div>
        <span style="font-weight:600;color:#ffffff;font-size:0.95rem;letter-spacing:-0.2px;">Helio Architect</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-new-btn">', unsafe_allow_html=True)
    if st.button("＋ Nuevo Chat", use_container_width=True, key="new_chat"):
        st.session_state.messages = []
        st.session_state.current_plan = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-title">Historial Reciente</div>', unsafe_allow_html=True)
    projects = load_saved_projects()
    st.markdown('<div class="sidebar-history-container">', unsafe_allow_html=True)
    if projects:
        for i, p in enumerate(projects[:8]):
            btn_label = f"✦ {p['name']}"
            if st.button(btn_label, key=f"hist_{p['ts']}_{i}", use_container_width=True):
                st.session_state.current_plan = p["plan"]
                st.session_state.messages = [
                    {"role": "assistant", "content": f"He cargado el proyecto **{p['name']}**. Aquí tienes el diseño actual:", "render_path": p["img_path"]}
                ]
                st.rerun()
    else:
        st.markdown('<div style="padding:0.25rem 0.75rem;font-size:0.75rem;color:#9b9b9b;">No hay diseños guardados</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    alive = agent_alive()
    model_name = OPENAI_MODEL
    short_model = model_name.split("/")[-1] if "/" in model_name else model_name

    st.markdown(f"""
    <div class="sidebar-footer">
        <div class="status-item">
            <span class="status-dot {'alive' if alive else 'dead'}"></span>
            <span style="font-weight:500;">Blender: {'Conectado' if alive else 'Desconectado'}</span>
        </div>
        <div class="model-item">
            <svg class="model-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
            </svg>
            <span>{short_model}</span>
        </div>
        {"" if alive else '<div style="font-size:0.7rem;color:#ef4444;line-height:1.3;padding-top:4px;">⚠️ Activa el addon "AI Architect Agent" en Blender para construir.</div>'}
    </div>
    """, unsafe_allow_html=True)

if len(st.session_state.messages) == 0:
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-logo">
            <svg viewBox="0 0 24 24" width="44" height="44" fill="none">
                <path d="M12 2C12 7.5 16.5 12 22 12C16.5 12 12 16.5 12 22C12 16.5 7.5 12 2 12C7.5 12 12 7.5 12 2Z" fill="#10a37f"/>
                <path d="M2 22V2h20v20" stroke="rgba(255,255,255,0.15)" stroke-width="1" stroke-dasharray="2 2"/>
                <path d="M6 6h12v12H6Z" stroke="rgba(255,255,255,0.2)" stroke-width="1.5"/>
            </svg>
        </div>
        <div class="welcome-title">¿Qué vamos a diseñar hoy?</div>
        <div class="welcome-sub">Describe tu idea arquitectónica y la modelaré en Blender en tiempo real.</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="suggestion-container">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    sug_prompt = None
    with col1:
        if st.button("✦ Villa Moderna\nCon piscina y grandes ventanales", key="sug_1", use_container_width=True):
            sug_prompt = "Genera una villa moderna de dos pisos con piscina, terraza y grandes ventanales"
        if st.button("✦ Castillo Medieval\nCon murallas, torreones y patio", key="sug_2", use_container_width=True):
            sug_prompt = "Construye un castillo medieval con torres de vigilancia, murallas y un gran patio"
    with col2:
        if st.button("✦ Cabaña Rústica\nEstilo cabaña de troncos de madera", key="sug_3", use_container_width=True):
            sug_prompt = "Diseña una cabaña rústica de madera en el bosque con chimenea y techo a dos aguas"
        if st.button("✦ Rascacielos Futurista\nEdificio de oficinas moderno y alto", key="sug_4", use_container_width=True):
            sug_prompt = "Crea un rascacielos futurista de 5 pisos de vidrio y acero con helipuerto"
    st.markdown('</div>', unsafe_allow_html=True)

    prompt = st.chat_input("Escribe tu idea aquí...")
    if sug_prompt:
        prompt = sug_prompt
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🏛️" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"] + f'\n\n<span class="msg-indicator-{msg["role"]}" style="display:none;"></span>', unsafe_allow_html=True)
            if msg.get("render_path") and Path(msg["render_path"]).exists():
                st.markdown(f'<div class="render-card fade-in">', unsafe_allow_html=True)
                st.image(msg["render_path"], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
    prompt = st.chat_input("Modifica o detalla el diseño actual...")

if prompt:
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt + '\n\n<span class="msg-indicator-user" style="display:none;"></span>', unsafe_allow_html=True)

    with st.chat_message("assistant", avatar="🏛️"):
        msg_ph = st.empty()

        alive = agent_alive()
        msg_ph.markdown("""
        <div class="status-card pulse">
            <svg class="spinner" viewBox="0 0 50 50">
                <circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
            </svg>
            <div class="status-card-text">
                <div class="status-card-title">Paso 1 de 2</div>
                <div class="status-card-desc">Generando diseño con IA...</div>
            </div>
        </div>
        <span class="msg-indicator-assistant" style="display:none;"></span>
        """, unsafe_allow_html=True)
        st.session_state.messages.append({"role":"assistant","content":"Generando..."})

        is_refine = st.session_state.current_plan is not None
        plan = None
        try:
            if is_refine:
                msg_ph.markdown("""
                <div class="status-card pulse">
                    <svg class="spinner" viewBox="0 0 50 50">
                        <circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
                    </svg>
                    <div class="status-card-text">
                        <div class="status-card-title">Paso 1 de 2</div>
                        <div class="status-card-desc">Mejorando diseño existente con IA...</div>
                    </div>
                </div>
                <span class="msg-indicator-assistant" style="display:none;"></span>
                """, unsafe_allow_html=True)
                plan = refine_plan(st.session_state.current_plan, prompt)
            else:
                msg_ph.markdown("""
                <div class="status-card pulse">
                    <svg class="spinner" viewBox="0 0 50 50">
                        <circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
                    </svg>
                    <div class="status-card-text">
                        <div class="status-card-title">Paso 1 de 2</div>
                        <div class="status-card-desc">Generando nuevo diseño con IA...</div>
                    </div>
                </div>
                <span class="msg-indicator-assistant" style="display:none;"></span>
                """, unsafe_allow_html=True)
                plan = generate_plan(prompt)
        except Exception as e:
            msg_ph.markdown(f"❌ AI error: {e}")
            st.session_state.messages[-1]["content"] = f"AI error: {e}"

        if not plan or not plan.get("house"):
            msg_ph.markdown("❌ No se pudo generar el diseño. Inténtalo de nuevo.")
            st.session_state.messages[-1]["content"] = "Error al generar el diseño."
        else:
            st.session_state.current_plan = plan
            desc = plan.get("desc") or plan.get("project") or "Sin título"
            rooms_n = len(plan.get("rooms", []))
            win = plan.get("windows", 0)
            floors = plan.get("floors", 1)
            has_pool = "Sí" if plan.get("pool") else "No"
            trees = plan.get("trees", 0)
            renders_dir = Path(__file__).parent / "renders"
            renders_dir.mkdir(exist_ok=True)
            ts = int(time.time())
            
            # Save the plan to plan_{ts}.json
            plan_path = renders_dir / f"plan_{ts}.json"
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
                
            output_path = str(renders_dir / f"design_{ts}.png")

            if not alive:
                msg_ph.markdown(f"""
                <div class="status-card fade-in">
                    <div class="plan-header">{desc}</div>
                    <div class="plan-meta">
                        <span>{rooms_n} hab</span>
                        <span>{win} vent</span>
                        <span>{floors} piso(s)</span>
                        <span>Piscina: {has_pool}</span>
                        <span>{trees} árb</span>
                    </div>
                    <div style="font-size:0.8rem;color:#ef4444;margin-top:0.5rem;font-weight:500;">
                        ⚠️ Servidor Blender fuera de línea. Abre Blender y activa el addon para construir.
                    </div>
                </div>
                <span class="msg-indicator-assistant" style="display:none;"></span>
                """, unsafe_allow_html=True)
                st.session_state.messages[-1]["content"] = f"Diseño: **{desc}**\n\n* Habitaciones: {rooms_n}\n* Ventanas: {win}\n* Pisos: {floors}\n* Piscina: {has_pool}\n* Árboles: {trees}\n\n*(Blender offline — no se pudo modelar)*"
            else:
                msg_ph.markdown(f"""
                <div class="status-card">
                    <div class="plan-header">{desc}</div>
                    <div class="plan-meta">
                        <span>{rooms_n} hab</span>
                        <span>{win} vent</span>
                        <span>{floors} piso(s)</span>
                        <span>Piscina: {has_pool}</span>
                        <span>{trees} árb</span>
                    </div>
                    <div class="status-card pulse" style="margin-top: 1rem; border: none; padding: 0;">
                        <svg class="spinner" viewBox="0 0 50 50">
                            <circle class="path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle>
                        </svg>
                        <div class="status-card-text">
                            <div class="status-card-title">Paso 2 de 2</div>
                            <div class="status-card-desc">Construyendo y renderizando en Blender...</div>
                        </div>
                    </div>
                </div>
                <span class="msg-indicator-assistant" style="display:none;"></span>
                """, unsafe_allow_html=True)

                try:
                    result = agent_send({
                        "action": "build_and_render",
                        "plan": plan,
                        "output_path": output_path
                    })
                    if result.get("status") == "ok" and os.path.exists(output_path):
                        msg_ph.markdown(f"""
                        <div class="status-card fade-in">
                            <div class="plan-header">{desc}</div>
                            <div class="plan-meta">
                                <span>{rooms_n} hab</span>
                                <span>{win} vent</span>
                                <span>{floors} piso(s)</span>
                                <span>Piscina: {has_pool}</span>
                                <span>{trees} árb</span>
                            </div>
                        </div>
                        <span class="msg-indicator-assistant" style="display:none;"></span>
                        """, unsafe_allow_html=True)
                        st.image(output_path, use_container_width=True)
                        
                        st.session_state.messages[-1]["content"] = f"Diseño: **{desc}**\n\n* Habitaciones: {rooms_n}\n* Ventanas: {win}\n* Pisos: {floors}\n* Piscina: {has_pool}\n* Árboles: {trees}"
                        st.session_state.messages[-1]["render_path"] = output_path
                    else:
                        msg = result.get("msg", "Error desconocido")
                        msg_ph.markdown(f"❌ **Blender error:** {msg}")
                        st.session_state.messages[-1]["content"] = f"Error de Blender: {msg}"
                except socket.timeout:
                    msg_ph.markdown("❌ **Timeout:** Blender no responde (180s).")
                    st.session_state.messages[-1]["content"] = "Timeout esperando a Blender."
                except Exception as e:
                    msg_ph.markdown(f"❌ **Error de conexión:** {e}")
                    st.session_state.messages[-1]["content"] = f"Error de conexión: {e}"
        st.rerun()
