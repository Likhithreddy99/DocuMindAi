# app.py — DocuMind Ai (Full Featured)

import streamlit as st
import time
import uuid
import json
import pymongo
import base64
from datetime import datetime
from vectors import EmbeddingsManager
from chatbot import ChatbotManager

# ───────────────── MONGODB ─────────────────
@st.cache_resource
def init_mongo():
    try:
        client = pymongo.MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        client.admin.command('ismaster')
        db = client["documind_db"]
        return db["conversations"]
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return None

conversations_collection = init_mongo()

def create_new_session():
    st.session_state['session_id'] = str(uuid.uuid4())
    st.session_state['messages'] = []
    st.session_state['session_title'] = "New Conversation"
    st.session_state['chatbot_manager'] = None

def load_session(session_id):
    if conversations_collection is not None:
        doc = conversations_collection.find_one({"session_id": session_id})
        if doc:
            st.session_state['session_id'] = doc['session_id']
            st.session_state['messages'] = doc.get('messages', [])
            st.session_state['session_title'] = doc.get('title', "Conversation")

def save_message_to_db(role, content):
    if conversations_collection is None:
        return
    title = st.session_state.get('session_title', "New Conversation")
    if role == 'user' and title == "New Conversation":
        title = content[:40] + "..." if len(content) > 40 else content
        st.session_state['session_title'] = title
    conversations_collection.update_one(
        {"session_id": st.session_state['session_id']},
        {
            "$set": {"title": title, "updated_at": time.time()},
            "$push": {"messages": {"role": role, "content": content, "ts": time.time()}}
        },
        upsert=True
    )

def delete_session(session_id):
    if conversations_collection is not None:
        conversations_collection.delete_one({"session_id": session_id})

def export_chat():
    """Export current chat as text."""
    lines = []
    lines.append(f"DocuMind Ai — Chat Export")
    lines.append(f"Session: {st.session_state.get('session_title', 'Untitled')}")
    lines.append(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)
    for msg in st.session_state['messages']:
        role = "You" if msg['role'] == 'user' else "DocuMind"
        lines.append(f"\n[{role}]")
        lines.append(msg['content'])
    return "\n".join(lines)

def format_time_ago(ts):
    """Format a timestamp as relative time."""
    if not ts:
        return ""
    diff = time.time() - ts
    if diff < 60:
        return "just now"
    elif diff < 3600:
        return f"{int(diff/60)}m ago"
    elif diff < 86400:
        return f"{int(diff/3600)}h ago"
    else:
        return f"{int(diff/86400)}d ago"

# ───────────────── SESSION STATE ─────────────────
if 'session_id' not in st.session_state:
    create_new_session()
if 'temp_pdf_path' not in st.session_state:
    st.session_state['temp_pdf_path'] = None
if 'chatbot_manager' not in st.session_state:
    st.session_state['chatbot_manager'] = None
if 'messages' not in st.session_state:
    st.session_state['messages'] = []
if 'uploaded_docs' not in st.session_state:
    st.session_state['uploaded_docs'] = []

# ───────────────── PAGE CONFIG ─────────────────
st.set_page_config(
    page_title="DocuMind Ai",
    page_icon="favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────── CSS ─────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600&family=Inter:wght@300;400;500;600&display=swap');

/* ── Base ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
    background-color: #f4f1ec !important;
    color: #2c2c2c !important;
}

/* ── Typography ── */
h1,h2,h3 { font-family:'Lora',serif !important; color:#2c2c2c !important; }
p, li, span { color: #2c2c2c !important; }

/* Hero */
.hero-title {
    font-family: 'Lora', serif;
    color: #6b3a2a;
    font-size: 3.2rem;
    text-align: center;
    margin-top: 10vh;
    margin-bottom: 0.3rem;
    font-weight: 500;
    letter-spacing: -0.02em;
}
.hero-sub {
    text-align: center;
    color: #8a7f74;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}

/* Suggestion Pills */
.suggestions {
    display: flex;
    justify-content: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 1rem;
    margin-bottom: 2rem;
}
.pill {
    background: #ffffff;
    border: 1px solid #d9d3cb;
    border-radius: 20px;
    padding: 0.5rem 1.2rem;
    color: #5a5249;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
}
.pill:hover {
    background: #ede8e1;
    color: #3b2a1f;
    border-color: #8b5e3c;
}

/* ── Left Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #322d29 !important;
    border-right: 1px solid #4a433c !important;
}
[data-testid="stSidebar"] * { color: #c4bab0 !important; }
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,[data-testid="stSidebar"] h4 {
    color: #f0ebe5 !important;
}

/* Sidebar Buttons */
[data-testid="stSidebar"] div.stButton > button {
    background: #3e3833 !important;
    color: #d4cdc5 !important;
    border: 1px solid #4a433c !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    padding: 0.4rem 0.7rem !important;
    text-align: left !important;
    width: 100% !important;
    transition: all 0.15s ease !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
[data-testid="stSidebar"] div.stButton > button:hover {
    background: #4a433c !important;
    border-color: #8b5e3c !important;
    color: #fff !important;
}

/* New Chat accent button */
.new-chat-btn button {
    background: linear-gradient(135deg, #8b5e3c, #a0714d) !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    padding: 0.55rem 1rem !important;
    font-size: 0.9rem !important;
}
.new-chat-btn button:hover {
    background: linear-gradient(135deg, #7a4f30, #8b5e3c) !important;
    color: #fff !important;
}

/* Main Buttons */
div.stButton > button {
    background: #ffffff !important;
    color: #3b2a1f !important;
    border: 1px solid #d9d3cb !important;
    border-radius: 8px !important;
}
div.stButton > button:hover {
    background: #ede8e1 !important;
    border-color: #8b5e3c !important;
}

/* File Uploader */
.stFileUploader > div, [data-testid="stFileUploadDropzone"] {
    background-color: #ffffff !important;
    border-radius: 10px !important;
    border: 1px dashed #c4bab0 !important;
}

/* Chat Messages */
.stChatMessage {
    background: transparent !important;
    border: none !important;
    padding: 0.8rem 1.2rem !important;
    margin-bottom: 0.2rem !important;
}
.stChatMessage:has([data-testid="chatAvatarIcon-user"]) {
    background: #ffffff !important;
    border: 1px solid #e6e0d8 !important;
    border-radius: 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
}

/* Chat Input */
.stChatInputContainer {
    background: #ffffff !important;
    border-radius: 14px !important;
    border: 1px solid #d9d3cb !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06) !important;
}
.stChatInputContainer textarea {
    color: #2c2c2c !important;
    font-size: 0.95rem !important;
}

/* Chrome hide */
#MainMenu {display:none;}
footer {display:none;}
header {background: #322d29 !important; visibility:visible !important;}
header button {
    color:#f0ebe5 !important; background:#4a433c !important;
    border-radius:6px !important; visibility:visible !important;
}

/* Container */
.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 820px !important;
}

/* Sidebar divider */
.sdiv { border:none; border-top:1px solid #4a433c; margin:0.7rem 0; }

/* History label */
.hlabel {
    font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em;
    color:#8a7f74 !important; margin-bottom:0.4rem; padding-left:0.2rem;
}

/* Timestamp under messages */
.msg-time {
    font-size: 0.7rem;
    color: #a09688;
    margin-top: -0.2rem;
    margin-bottom: 0.5rem;
    padding-left: 3.2rem;
}

/* Skeleton loader */
@keyframes shimmer {
    0% { background-position: -200px 0; }
    100% { background-position: calc(200px + 100%) 0; }
}
.skeleton {
    background: linear-gradient(90deg, #e6e0d8 25%, #d9d3cb 50%, #e6e0d8 75%);
    background-size: 200px 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 8px;
    height: 1rem;
    margin: 0.4rem 0;
}

/* Doc info card */
.doc-card {
    background: #3e3833;
    border: 1px solid #4a433c;
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    margin: 0.3rem 0;
    font-size: 0.8rem;
}
.doc-card .name { color: #f0ebe5; font-weight: 500; }
.doc-card .meta { color: #a09688; font-size: 0.72rem; }

/* Expander styling */
[data-testid="stExpander"] {
    border: 1px solid #d9d3cb !important;
    border-radius: 10px !important;
    background: #ffffff !important;
}

/* Download button */
.stDownloadButton > button {
    background: #3e3833 !important;
    color: #f0ebe5 !important;
    border: 1px solid #4a433c !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
}

/* ── Override ALL Streamlit blue accents ── */
.stChatInputContainer button,
.stChatInputContainer button svg {
    color: #8b5e3c !important;
    fill: #8b5e3c !important;
}
.stChatInputContainer button:hover,
.stChatInputContainer button:hover svg {
    color: #6b3a2a !important;
    fill: #6b3a2a !important;
}

/* Status widget */
[data-testid="stStatusWidget"] {
    background: #ffffff !important;
    border: 1px solid #d9d3cb !important;
}

/* File uploader remove button */
button[kind="icon"], [data-testid="baseButton-icon"] {
    color: #8b5e3c !important;
}

/* Streamlit primary color override everywhere */
:root {
    --primary-color: #8b5e3c !important;
}
.st-emotion-cache-1gulkj5, .st-emotion-cache-1v0mbdj {
    color: #8b5e3c !important;
}

/* Any remaining blue links/accents */
a { color: #8b5e3c !important; }
a:hover { color: #6b3a2a !important; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
# LEFT SIDEBAR
# ═══════════════════════════════════════════════
with st.sidebar:
    # ── Logo + Brand ──
    col_logo, col_name = st.columns([1, 3])
    with col_logo:
        st.image("logo.png", width=45)
    with col_name:
        st.markdown("#### DocuMind Ai")

    # ── New Chat ──
    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("✦  New Chat", use_container_width=True, key="new_chat_btn"):
        create_new_session()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<hr class="sdiv">', unsafe_allow_html=True)

    # ── Upload & Index (collapsible) ──
    with st.expander("📂 Upload & Index Documents", expanded=False):
        uploaded_files = st.file_uploader(
            "Upload PDFs", type=["pdf"],
            label_visibility="collapsed",
            accept_multiple_files=True
        )

        if uploaded_files:
            for uf in uploaded_files:
                size_kb = round(uf.size / 1024, 1)
                st.markdown(
                    f'<div class="doc-card"><span class="name">📄 {uf.name}</span>'
                    f'<br><span class="meta">{size_kb} KB</span></div>',
                    unsafe_allow_html=True
                )

            # Save the last uploaded file for indexing
            last_file = uploaded_files[-1]
            temp_pdf_path = "temp.pdf"
            with open(temp_pdf_path, "wb") as f:
                f.write(last_file.getbuffer())
            st.session_state['temp_pdf_path'] = temp_pdf_path
            st.session_state['uploaded_docs'] = [uf.name for uf in uploaded_files]

            if st.button("⚡ Index All"):
                try:
                    em = EmbeddingsManager(
                        model_name="BAAI/bge-small-en", device="cpu",
                        encode_kwargs={"normalize_embeddings": True},
                        qdrant_path="local_qdrant",
                        collection_name="vector_db"
                    )
                    with st.status("Indexing documents...", expanded=True) as status:
                        for uf in uploaded_files:
                            st.write(f"Processing {uf.name}...")
                            path = f"temp_{uf.name}"
                            with open(path, "wb") as f:
                                f.write(uf.getbuffer())
                            em.create_embeddings(path)
                        status.update(label="✅ All documents indexed!", state="complete", expanded=False)

                    st.session_state['chatbot_manager'] = ChatbotManager(
                        model_name="BAAI/bge-small-en", device="cpu",
                        encode_kwargs={"normalize_embeddings": True},
                        llm_model="llama3.2:latest", llm_temperature=0.7,
                        qdrant_path="local_qdrant",
                        collection_name="vector_db"
                    )
                except Exception as e:
                    st.error(f"Error: {e}")

    # ── Indexed Documents Preview ──
    if st.session_state.get('uploaded_docs'):
        st.markdown('<p class="hlabel">Indexed Documents</p>', unsafe_allow_html=True)
        for doc_name in st.session_state['uploaded_docs']:
            st.markdown(f'<div class="doc-card"><span class="name">✅ {doc_name}</span></div>', unsafe_allow_html=True)
        st.markdown('<hr class="sdiv">', unsafe_allow_html=True)

    # ── Export Chat ──
    if st.session_state['messages']:
        export_text = export_chat()
        st.download_button(
            "📥 Export Chat",
            data=export_text,
            file_name=f"documind_chat_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True
        )
        st.markdown('<hr class="sdiv">', unsafe_allow_html=True)

    # ── Conversation History ──
    st.markdown('<p class="hlabel">Recent Conversations</p>', unsafe_allow_html=True)

    if conversations_collection is not None:
        recent = list(conversations_collection.find().sort("updated_at", -1).limit(20))
        if not recent:
            st.caption("No conversations yet.")
        else:
            for chat in recent:
                title = chat.get('title', 'Untitled')
                s_id = chat['session_id']
                is_active = (s_id == st.session_state.get('session_id'))

                c1, c2 = st.columns([6, 1])
                with c1:
                    icon = "●" if is_active else "○"
                    display_title = f"{icon}  {title[:25]}"
                    if st.button(display_title, key=f"l_{s_id}", use_container_width=True):
                        load_session(s_id)
                        st.rerun()
                with c2:
                    if st.button("🗑", key=f"d_{s_id}"):
                        delete_session(s_id)
                        if s_id == st.session_state.get('session_id'):
                            create_new_session()
                        st.rerun()
    else:
        st.warning("MongoDB offline")

    # ── Footer ──
    st.markdown('<hr class="sdiv">', unsafe_allow_html=True)
    st.markdown(
        "<p style='font-size:0.7rem; color:#555; line-height:1.4;'>"
        "© 2026 DocuMind Ai<br>Built by Dodda Likhith reddy</p>",
        unsafe_allow_html=True
    )

# ═══════════════════════════════════════════════
# MAIN CHAT AREA
# ═══════════════════════════════════════════════

# Empty state with suggestions
if len(st.session_state['messages']) == 0:
    st.markdown('<div class="hero-title">DocuMind chat?</div>', unsafe_allow_html=True)

    if st.session_state['chatbot_manager'] is None:
        st.markdown('<p class="hero-sub">Upload & index a document to start chatting</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="hero-sub">Your documents are ready — ask me anything</p>', unsafe_allow_html=True)

    # Suggestion pills
    suggestions = [
        ("📝 Summarize", "Summarize the key points of this document"),
        ("🔍 Key Topics", "What are the main topics covered in this document?"),
        ("❓ Questions", "Generate 5 important questions from this document"),
        ("📊 Analysis", "Provide a detailed analysis of the document content"),
    ]

    pill_cols = st.columns(len(suggestions))
    for i, (label, prompt) in enumerate(suggestions):
        with pill_cols[i]:
            if st.button(label, key=f"sug_{i}", use_container_width=True):
                st.session_state['pending_prompt'] = prompt
                st.rerun()

# Display messages with timestamps
for msg in st.session_state['messages']:
    st.chat_message(msg['role']).markdown(msg['content'])
    # Timestamp
    ts = msg.get('ts')
    if ts:
        st.markdown(f'<div class="msg-time">{format_time_ago(ts)}</div>', unsafe_allow_html=True)

# Handle pending prompt from suggestion pills
pending = st.session_state.pop('pending_prompt', None)

# Chat input
user_input = st.chat_input("How can I help you today?")
if pending:
    user_input = pending

if user_input:
    # Show user message
    st.chat_message("user").markdown(user_input)
    now = time.time()
    st.session_state['messages'].append({"role": "user", "content": user_input, "ts": now})
    save_message_to_db("user", user_input)

    if st.session_state['chatbot_manager'] is None:
        answer = "⚠️ Please upload and index a document first."
        st.chat_message("assistant").markdown(answer)
        st.session_state['messages'].append({"role": "assistant", "content": answer, "ts": time.time()})
        save_message_to_db("assistant", answer)
    else:
        # Streaming response with typing animation
        with st.chat_message("assistant"):
            # Show skeleton loader briefly
            skeleton = st.empty()
            skeleton.markdown(
                '<div class="skeleton" style="width:80%"></div>'
                '<div class="skeleton" style="width:60%"></div>'
                '<div class="skeleton" style="width:70%"></div>',
                unsafe_allow_html=True
            )
            time.sleep(0.3)
            skeleton.empty()

            # Stream the response
            try:
                response_stream = st.session_state['chatbot_manager'].stream_response(user_input)
                full_response = st.write_stream(response_stream)
            except Exception as e:
                full_response = f"⚠️ Error: {e}"
                st.markdown(full_response)

        st.session_state['messages'].append({"role": "assistant", "content": full_response, "ts": time.time()})
        save_message_to_db("assistant", full_response)
