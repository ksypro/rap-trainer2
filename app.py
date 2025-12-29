import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import io
import os
import streamlit.components.v1 as components

# 嘗試引入 Github
try:
    from github import Github
    has_github = True
except ImportError:
    has_github = False

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="Rap Trainer Ultra", page_icon="🎤", layout="centered")

# --- 2. 2025 Apple Design System (CSS) ---
st.markdown("""
    <style>
    /* 全局重置與字體 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        background-color: #000000 !important; /* 純黑背景 */
        color: #FFFFFF !important;
    }

    /* 隱藏 Streamlit 預設元件 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 容器優化 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 6rem;
        max_width: 500px; /* 手機最佳化寬度 */
    }

    /* === 2025 Glassmorphism Cards (毛玻璃卡片) === */
    .glass-card {
        background: rgba(28, 28, 30, 0.6);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 24px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.2s ease;
    }
    
    /* 等級標題 */
    .level-title {
        color: #00E676; /* 快嘴綠 */
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 700;
        margin-bottom: 4px;
    }
    
    .level-big-num {
        font-size: 42px;
        font-weight: 800;
        color: white;
        margin: 8px 0;
        letter-spacing: -1px;
    }
    
    /* 進度條背景 */
    .progress-bg {
        background: rgba(255, 255, 255, 0.1);
        height: 8px;
        border-radius: 4px;
        width: 100%;
        margin-top: 16px;
        overflow: hidden;
    }
    
    /* 進度條填充 (漸層) */
    .progress-fill {
        background: linear-gradient(90deg, #00E676, #00C853);
        height: 100%;
        border-radius: 4px;
        box-shadow: 0 0 10px rgba(0, 230, 118, 0.5);
    }

    /* === 節拍器介面 === */
    .bpm-display {
        font-size: 96px !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
        text-align: center;
        line-height: 1;
        margin-top: 10px;
        text-shadow: 0 0 20px rgba(0, 230, 118, 0.2);
    }
    
    .bpm-label {
        color: #8E8E93 !important;
        text-align: center;
        font-size: 18px;
        font-weight: 500;
        margin-bottom: 20px;
    }

    /* 強制輸入框文字顏色 (修復文字丟失) */
    input[type="number"], .stSelectbox div[data-baseweb="select"] div {
        color: white !important;
        background-color: rgba(44, 44, 46, 0.8) !important;
        border-radius: 12px !important;
        border: none !important;
    }
    
    /* 按鈕樣式 (iOS 風格) */
    div.stButton > button {
        background: #1C1C1E;
        color: #00E676;
        border: 1px solid rgba(0, 230, 118, 0.3);
        border-radius: 18px;
        font-weight: 600;
        height: 50px;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background: #00E676;
        color: black;
        border-color: #00E676;
        transform: scale(1.02);
    }
    
    /* 主要動作按鈕 (Primary) */
    button[kind="primary"] {
        background: linear-gradient(135deg, #00E676 0%, #00C853 100%) !important;
        color: black !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(0, 230, 118, 0.4);
    }

    /* Tab 樣式優化 */
    .stRadio > div {
        background: rgba(28, 28, 30, 0.8);
        padding: 5px;
        border-radius: 16px;
        display: flex;
        justify-content: space-around;
        backdrop-filter: blur(10px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心邏輯層 (Python) ---
class RapTrainerApp:
    def __init__(self):
        self.data_file = "rap_log_v5.csv"
        self.note_multipliers = {
            "1/4": 1,
            "1/8": 2,
            "1/3": 3, 
            "1/16": 4
        }
        # GitHub 初始化
        self.gh_client = None
        if has_github:
            try:
                if "github" in st.secrets:
                    self.gh_client = Github(st.secrets["github"]["token"])
                    self.repo_name = st.secrets["github"]["repo_name"]
                    self.branch = st.secrets["github"]["branch"]
            except:
                pass
        self.load_data()

    def load_data(self):
        # 優先嘗試從 GitHub 讀取
        data_loaded = False
        if self.gh_client:
            try:
                repo = self.gh_client.get_repo(self.repo_name)
                contents = repo.get_contents(self.data_file, ref=self.branch)
                decoded = contents.decoded_content.decode("utf-8")
                self.history = pd.read_csv(io.StringIO(decoded))
                self.history['Date'] = pd.to_datetime(self.history['Date'])
                data_loaded = True
            except:
                pass
        if not data_loaded:
            if os.path.exists(self.data_file):
                try:
                    self.history = pd.read_csv(self.data_file)
                    self.history['Date'] = pd.to_datetime(self.history['Date'])
                except:
                    self.init_empty_db()
            else:
                self.init_empty_db()
        if 'history' not in st.session_state:
            st.session_state.history = self.history

    def init_empty_db(self):
        self.history = pd.DataFrame(columns=['Date', 'BPM', 'Note_Type', 'SPS', 'Duration', 'Focus'])

    def save_data(self, df):
        df.to_csv(self.data_file, index=False)
        st.session_state.history = df
        if self.gh_client:
            try:
                repo = self.gh_client.get_repo(self.repo_name)
                csv_content = df.to_csv(index=False)
                try:
                    contents = repo.get_contents(self.data_file, ref=self.branch)
                    repo.update_file(contents.path, f"Update {datetime.now()}", csv_content, contents.sha, branch=self.branch)
                except:
                    repo.create_file(self.data_file, "Init data", csv_content, branch=self.branch)
                return True
            except:
                pass
        return False

    def calculate_sps(self, bpm, note_label):
        for k, v in self.note_multipliers.items():
            if k in note_label: return (bpm * v) / 60
        return bpm / 60

    def get_total_minutes(self):
        if st.session_state.history.empty: return 0
        return st.session_state.history['Duration'].sum()

app = RapTrainerApp()

# --- 4. 狀態同步 Callback ---
if 'bpm' not in st.session_state: st.session_state.bpm = 85
if 'playing' not in st.session_state: st.session_state.playing = False

def update_bpm_from_slider():
    st.session_state.bpm = st.session_state.bpm_slider
def update_bpm_from_number():
    st.session_state.bpm = st.session_state.bpm_number
def toggle_play():
    st.session_state.playing = not st.session_state.playing

# --- 5. 導航 (仿 App 底部 Tab, 但 Streamlit 限制放頂部或側邊) ---
# 使用 Columns 模擬頂部導航
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("🏠 主頁", use_container_width=True): st.session_state.page = "home"
with nav2:
    if st.button("⏱️ 節拍", use_container_width=True): st.session_state.page = "metronome"
with nav3:
    if st.button("📊 數據", use_container_width=True): st.session_state.page = "stats"

if 'page' not in st.session_state: st.session_state.page = "home"

# ================= 🏠 主頁 =================
if st.session_state.page == "home":
    st.markdown("<br>", unsafe_allow_html=True)
    
    df = st.session_state.history
    total_mins = app.get_total_minutes()
    
    # 邏輯：120分鐘升級
    level = int(total_mins // 120)
    mins_in_level = total_mins % 120
    mins_needed = 120 - mins_in_level
    progress_pct = (mins_in_level / 120) * 100
    
    # 快嘴稱號邏輯
    titles = ["新手 (Novice)", "學徒 (Apprentice)", "快嘴 (Chopper)", "神之舌 (God Speed)", "光速 (Light Speed)"]
    current_title = titles[min(level, len(titles)-1)]

    # Glass Card
    st.markdown(f"""
    <div class="glass-card">
        <div class="level-title">{current_title} • Lv.{level}</div>
        <div class="level-big-num">
            {int(total_mins // 60)}<span style="font-size:18px; color:#888; font-weight:500;"> 小時 </span>
            {int(total_mins % 60)}<span style="font-size:18px; color:#888; font-weight:500;"> 分鐘</span>
        </div>
        <div style="color: #8E8E93; font-size: 13px; text-align:right;">累積訓練總時長</div>
        
        <div class="progress-bg">
            <div class="progress-fill" style="width: {progress_pct}%;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:10px;">
            <span style="color:#666; font-size:12px;">0%</span>
            <span style="color:#00E676; font-size:12px; font-weight:bold;">再練 {int(mins_needed)} 分鐘升級</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 快捷狀態
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"🔥 連續打卡: {df['Date'].dt.date.nunique()} 天")
    with c2:
        last_bpm = df.iloc[-1]['BPM'] if not df.empty else 85
        st.success(f"💡 建議 BPM: {last_bpm + 5}")

# ================= ⏱️ 節拍器 (Web Audio API 版) =================
elif st.session_state.page == "metronome":
    
    # 1. 頂部設定
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        st.button("4/4", disabled=True, use_container_width=True)
    with c2:
        # 音符圖標
        note_display = {"1/4": "♩", "1/8": "♫", "1/3": "3", "1/16": "::::"}
        selected_note_key = st.selectbox("Note", list(app.note_multipliers.keys()), 
                                       index=3, label_visibility="collapsed", 
                                       format_func=lambda x: f"{note_display.get(x, '')}")
    with c3:
        ghost_mode = st.toggle("👻 Ghost")

    # 2. 中間 BPM 顯示
    current_bpm = st.session_state.bpm
    sps = app.calculate_sps(current_bpm, selected_note_key)
    
    st.markdown(f'<div class="bpm-display">{current_bpm}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bpm-label">BPM • {sps:.1f} SPS</div>', unsafe_allow_html=True)

    # 3. 控制區 (Slider & Buttons)
    st.slider("BPM", 50, 200, key="bpm_slider", value=st.session_state.bpm, on_change=update_bpm_from_slider, label_visibility="collapsed")
    
    cb1, cb2, cb3 = st.columns([1, 2, 1])
    with cb1:
        if st.button("−", use_container_width=True):
            st.session_state.bpm -= 1
            st.rerun()
    with cb2:
        st.number_input("Input", 50, 200, key="bpm_number", value=st.session_state.bpm, on_change=update_bpm_from_number, label_visibility="collapsed")
    with cb3:
        if st.button("+", use_container_width=True):
            st.session_state.bpm += 1
            st.rerun()

    st.markdown("---")

    # 4. 播放控制 (JS Engine)
    # 這是最核心的修改：不再用 st.audio，而是用 JS 播放
    
    play_col, log_col = st.columns([2, 1])
    
    with play_col:
        # 切換按鈕狀態
        btn_label = "⏹️ 停止" if st.session_state.playing else "▶️ 播放 (無延遲)"
        if st.button(btn_label, type="primary", use_container_width=True):
            toggle_play()
            st.rerun()
            
    # 決定 JavaScript 參數
    js_bpm = st.session_state.bpm
    js_playing = "true" if st.session_state.playing else "false"
    # 計算間隔 (ms)
    note_mult = app.note_multipliers.get(selected_note_key, 1)
    js_interval = (60 / js_bpm) / note_mult * 1000 
    js_ghost = "true" if ghost_mode else "false"

    # --- 嵌入 JavaScript 音頻引擎 ---
    # 這段代碼會在瀏覽器端執行，不會受 Streamlit Python 後端影響
    html_code = f"""
    <script>
        // 1. 初始化 AudioContext (單例模式)
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!window.audioCtx) {{
            window.audioCtx = new window.AudioContext();
        }}

        // 2. 獲取 Python 傳來的參數
        var isPlaying = {js_playing};
        var interval = {js_interval};
        var isGhost = {js_ghost};
        var subdivisions = {note_mult}; // 1/4=1, 1/16=4

        // 3. 停止之前的 Loop
        if (window.metronomeTimer) {{
            clearInterval(window.metronomeTimer);
            window.metronomeTimer = null;
        }}
        
        // 變數重置
        if (!window.beatCount) window.beatCount = 0;

        // 4. 播放邏輯
        if (isPlaying) {{
            // 必須由用戶觸發 Resume (瀏覽器政策)
            if (window.audioCtx.state === 'suspended') {{
                window.audioCtx.resume();
            }}

            window.metronomeTimer = setInterval(() => {{
                var osc = window.audioCtx.createOscillator();
                var gainNode = window.audioCtx.createGain();
                
                osc.connect(gainNode);
                gainNode.connect(window.audioCtx.destination);
                
                // 計算節拍位置 (4/4拍)
                // 一個 Bar 有 4 拍，一拍有 subdivisions 個音
                var totalSubPerBar = 4 * subdivisions;
                var currentPos = window.beatCount % totalSubPerBar;
                var barNum = Math.floor(window.beatCount / totalSubPerBar) + 1;

                // Ghost Mode: 每 4 個小節，第 4 小節靜音
                var isGhostBar = isGhost && (barNum % 4 === 0);

                if (!isGhostBar) {{
                    // 設定頻率 (高低音)
                    if (currentPos === 0) {{
                        osc.frequency.value = 1200; // 強拍 (Bar頭)
                        gainNode.gain.value = 0.8;
                    }} else if (currentPos % subdivisions === 0) {{
                        osc.frequency.value = 800; // 正拍
                        gainNode.gain.value = 0.6;
                    }} else {{
                        osc.frequency.value = 600; // 細分音
                        gainNode.gain.value = 0.3;
                    }}

                    osc.start();
                    osc.stop(window.audioCtx.currentTime + 0.05); // 短促的聲音
                }}

                window.beatCount++;

            }}, interval);
        }} else {{
            window.beatCount = 0; // 重置計數
        }}
    </script>
    <div style="display:none">Audio Engine Running</div>
    """
    # 將隱形播放器注入頁面
    components.html(html_code, height=0)

    # 5. 打卡區
    with log_col:
        with st.popover("📝 打卡"):
            with st.form("quick_log"):
                t_min = st.number_input("時長(分)", 1, 120, 30)
                focus = st.text_input("備註")
                if st.form_submit_button("存檔"):
                    new_entry = pd.DataFrame([{
                        'Date': datetime.now(),
                        'BPM': st.session_state.bpm,
                        'Note_Type': selected_note_key,
                        'SPS': sps,
                        'Duration': t_min,
                        'Focus': focus
                    }])
                    st.session_state.history = pd.concat([st.session_state.history, new_entry], ignore_index=True)
                    app.save_data(st.session_state.history)
                    st.toast("✅ 已記錄")

# ================= 📊 數據庫 =================
elif st.session_state.page == "stats":
    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state.history.empty:
        st.info("尚無數據")
    else:
        df = st.session_state.history.copy()
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("#### 📈 速度成長")
        st.line_chart(df.set_index('Date')['BPM'], color="#00E676")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("#### 📋 歷史記錄")
        disp = df.sort_values('Date', ascending=False)
        disp['Date'] = disp['Date'].dt.strftime('%m-%d %H:%M')
        st.dataframe(disp[['Date', 'BPM', 'Note_Type', 'Duration', 'Focus']], use_container_width=True, hide_index=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 下載備份 CSV", csv, "rap_log.csv", "text/csv")
        st.markdown("</div>", unsafe_allow_html=True)
