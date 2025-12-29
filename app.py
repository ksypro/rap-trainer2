import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import time
from datetime import datetime
import streamlit.components.v1 as components

# 嘗試引入 Github
try:
    from github import Github
    has_github = True
except ImportError:
    has_github = False

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="Rap Trainer", page_icon="🎤", layout="centered")

# --- 2. 2025 Apple Design System (CSS 修復版) ---
st.markdown("""
    <style>
    /* 全局重置 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        background-color: #000000 !important;
        color: #FFFFFF !important;
    }

    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 6rem;
        max_width: 480px; /* iPhone 寬度優化 */
        margin: 0 auto;
    }

    /* === iOS Glass Cards === */
    .glass-card {
        background: rgba(28, 28, 30, 1); /* 加深背景，避免過透導致文字不清 */
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 16px;
    }
    
    /* 文字層級 (Apple Style) */
    .ios-headline {
        font-size: 34px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #FFFFFF;
        margin-bottom: 8px;
    }
    .ios-subhead {
        font-size: 15px;
        font-weight: 600;
        color: #8E8E93; /* Apple Gray */
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .ios-body {
        font-size: 17px;
        color: #FFFFFF;
        line-height: 1.4;
    }
    .ios-caption {
        font-size: 13px;
        color: #8E8E93;
    }

    /* 進度條容器 */
    .progress-container {
        background: #2C2C2E;
        height: 8px;
        border-radius: 4px;
        width: 100%;
        margin-top: 16px;
        overflow: hidden;
    }
    .progress-bar {
        background: #32D74B; /* iOS System Green */
        height: 100%;
        border-radius: 4px;
    }

    /* === 節拍器介面 === */
    .bpm-big {
        font-size: 96px;
        font-weight: 800;
        text-align: center;
        color: #FFFFFF;
        line-height: 1;
        font-variant-numeric: tabular-nums; /* 數字等寬，避免跳動 */
    }
    .bpm-label {
        font-size: 17px;
        font-weight: 600;
        text-align: center;
        color: #32D74B; /* Green Accent */
        margin-bottom: 24px;
    }

    /* 輸入框與滑桿優化 */
    .stSlider > div > div > div {
        background-color: #32D74B !important; /* Green slider */
    }
    .stNumberInput input {
        text-align: center;
        background-color: #1C1C1E !important;
        color: white !important;
        border-radius: 12px;
        font-weight: bold;
        font-size: 20px;
    }

    /* 按鈕樣式 (iOS Filled Button) */
    div.stButton > button {
        background-color: #1C1C1E;
        color: #FFFFFF;
        border: none;
        border-radius: 14px;
        font-weight: 600;
        font-size: 17px;
        padding: 12px 0;
        height: auto;
    }
    div.stButton > button:hover {
        background-color: #2C2C2E;
    }
    /* Primary Button (Play/Action) */
    button[kind="primary"] {
        background-color: #32D74B !important;
        color: #000000 !important;
    }

    /* Tab 導航列 (Sticky Bottom) */
    .nav-container {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(44, 44, 46, 0.8);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        padding: 8px;
        border-radius: 32px;
        display: flex;
        gap: 8px;
        z-index: 999;
        border: 1px solid rgba(255,255,255,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心邏輯層 ---
class RapTrainerApp:
    def __init__(self):
        self.data_file = "rap_log_v6.csv"
        self.note_multipliers = {"1/4": 1, "1/8": 2, "1/3": 3, "1/16": 4}
        
        # GitHub 初始化
        self.gh_client = None
        if has_github and "github" in st.secrets:
            try:
                self.gh_client = Github(st.secrets["github"]["token"])
                self.repo_name = st.secrets["github"]["repo_name"]
                self.branch = st.secrets["github"]["branch"]
            except:
                pass
        self.load_data()

    def load_data(self):
        # 1. 嘗試從 GitHub
        data_loaded = False
        if self.gh_client:
            try:
                repo = self.gh_client.get_repo(self.repo_name)
                contents = repo.get_contents(self.data_file, ref=self.branch)
                decoded = contents.decoded_content.decode("utf-8")
                self.history = pd.read_csv(io.StringIO(decoded))
                data_loaded = True
            except:
                pass
        
        # 2. 嘗試從本地
        if not data_loaded:
            if os.path.exists(self.data_file):
                try:
                    self.history = pd.read_csv(self.data_file)
                except:
                    self.init_empty_db()
            else:
                self.init_empty_db()

        # 3. 關鍵修復：確保 Date 是 datetime 格式，否則會報 AttributeError
        if not self.history.empty and 'Date' in self.history.columns:
            self.history['Date'] = pd.to_datetime(self.history['Date'], errors='coerce')
            self.history = self.history.dropna(subset=['Date']) # 刪除壞掉的日期資料
        
        if 'history' not in st.session_state:
            st.session_state.history = self.history

    def init_empty_db(self):
        self.history = pd.DataFrame(columns=['Date', 'BPM', 'Note_Type', 'SPS', 'Duration', 'Focus'])

    def save_data(self, df):
        df.to_csv(self.data_file, index=False)
        st.session_state.history = df
        
        # GitHub Sync
        if self.gh_client:
            try:
                repo = self.gh_client.get_repo(self.repo_name)
                csv_content = df.to_csv(index=False)
                try:
                    contents = repo.get_contents(self.data_file, ref=self.branch)
                    repo.update_file(contents.path, f"Auto-save {datetime.now()}", csv_content, contents.sha, branch=self.branch)
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

# --- 4. 狀態管理 ---
if 'bpm' not in st.session_state: st.session_state.bpm = 85
if 'playing' not in st.session_state: st.session_state.playing = False
if 'page' not in st.session_state: st.session_state.page = "home"
if 'start_time' not in st.session_state: st.session_state.start_time = None # 用於自動計時

# Callback 函數
def update_bpm_from_slider(): st.session_state.bpm = st.session_state.bpm_slider
def update_bpm_from_number(): st.session_state.bpm = st.session_state.bpm_number

def toggle_play():
    st.session_state.playing = not st.session_state.playing
    if st.session_state.playing:
        # 開始播放：記錄開始時間
        st.session_state.start_time = time.time()
    else:
        # 停止播放：不需要馬上存，待用戶確認
        pass

def nav_to(page_name):
    st.session_state.page = page_name

# --- 5. 導航列 (模擬 App 底部 Tab) ---
# 使用 container 置底
st.markdown("""
<div class="nav-container">
    </div>
""", unsafe_allow_html=True)

# 由於 Streamlit 按鈕無法直接嵌入自定義 HTML div，我們使用頂部 Columns 作為替代，但樣式優化
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("🏠 主頁", use_container_width=True, type="secondary"): nav_to("home")
with nav2:
    if st.button("⏱️ 節拍", use_container_width=True, type="secondary"): nav_to("metronome")
with nav3:
    if st.button("📊 數據", use_container_width=True, type="secondary"): nav_to("stats")

st.markdown("<br>", unsafe_allow_html=True)

# ================= 🏠 主頁 (Dashboard) =================
if st.session_state.page == "home":
    st.markdown('<div class="ios-headline">總覽</div>', unsafe_allow_html=True)
    
    df = st.session_state.history
    total_mins = app.get_total_minutes()
    
    # 等級邏輯
    level = int(total_mins // 120)
    mins_in_level = total_mins % 120
    mins_needed = 120 - mins_in_level
    progress_pct = (mins_in_level / 120) * 100
    
    # 稱號
    titles = ["Novice", "Apprentice", "Chopper", "Master", "Legend"]
    current_title = titles[min(level, len(titles)-1)]

    # === Level Card ===
    st.markdown(f"""
    <div class="glass-card">
        <div class="ios-subhead">MY LEVEL</div>
        <div style="font-size: 28px; font-weight: 700; color: #FFFFFF;">{current_title} <span style="color:#32D74B">Lv.{level}</span></div>
        <div style="font-size: 15px; color: #8E8E93; margin-top:4px;">累積訓練 {int(total_mins)} 分鐘</div>
        
        <div class="progress-container">
            <div class="progress-bar" style="width: {progress_pct}%;"></div>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:8px;">
            <span class="ios-caption">0%</span>
            <span class="ios-caption" style="color:#FFFFFF">再練 {int(mins_needed)} 分鐘升級</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # === Stats Summary ===
    c1, c2 = st.columns(2)
    days_streak = df['Date'].dt.date.nunique() if not df.empty else 0
    
    with c1:
        st.markdown(f"""
        <div class="glass-card" style="text-align:center; padding:16px;">
            <div class="ios-subhead">連續打卡</div>
            <div style="font-size: 32px; font-weight: 700; color: white;">{days_streak}</div>
            <div class="ios-caption">天</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        last_bpm = df.iloc[-1]['BPM'] if not df.empty else 85
        st.markdown(f"""
        <div class="glass-card" style="text-align:center; padding:16px;">
            <div class="ios-subhead">建議速度</div>
            <div style="font-size: 32px; font-weight: 700; color: #32D74B;">{last_bpm + 5}</div>
            <div class="ios-caption">BPM</div>
        </div>
        """, unsafe_allow_html=True)

# ================= ⏱️ 節拍器 (Metronome) =================
elif st.session_state.page == "metronome":
    
    # 頂部：音符選擇 (簡化)
    col_note, col_ghost = st.columns([2, 1])
    with col_note:
        note_display = {"1/4": "♩ Quarter", "1/8": "♫ Eighth", "1/3": "3 Triplet", "1/16": ":::: Sixteenth"}
        selected_note_key = st.selectbox("Note", list(app.note_multipliers.keys()), 
                                       index=3, label_visibility="collapsed", 
                                       format_func=lambda x: note_display.get(x, x))
    with col_ghost:
        ghost_mode = st.toggle("Ghost Mode")

    st.markdown("<br>", unsafe_allow_html=True)

    # 中間：BPM 大數字
    current_bpm = st.session_state.bpm
    sps = app.calculate_sps(current_bpm, selected_note_key)
    
    st.markdown(f'<div class="bpm-big">{current_bpm}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bpm-label">{sps:.1f} 音節 / 秒</div>', unsafe_allow_html=True)

    # 控制區：只保留 Slider 和 Input (刪除左右多餘的按鈕)
    st.slider("BPM Slider", 50, 200, key="bpm_slider", value=st.session_state.bpm, on_change=update_bpm_from_slider, label_visibility="collapsed")
    
    # 數字輸入框 (置中)
    c_spacer1, c_input, c_spacer2 = st.columns([1, 2, 1])
    with c_input:
        st.number_input("BPM Input", 50, 200, key="bpm_number", value=st.session_state.bpm, on_change=update_bpm_from_number, label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)

    # 播放按鈕 (JS Engine)
    btn_label = "⏹ 停止訓練" if st.session_state.playing else "▶ 開始訓練"
    if st.button(btn_label, type="primary", use_container_width=True):
        toggle_play()
        st.rerun()

    # 自動保存提示區
    if not st.session_state.playing and st.session_state.start_time:
        # 剛停止，計算時間
        elapsed = time.time() - st.session_state.start_time
        elapsed_mins = int(elapsed / 60)
        if elapsed < 60:
            st.info(f"本次練習：{int(elapsed)} 秒 (未滿 1 分鐘，不記錄)")
            st.session_state.start_time = None # 重置
        else:
            # 顯示自動保存卡片
            st.markdown(f"""
            <div class="glass-card" style="border-color:#32D74B;">
                <div class="ios-subhead" style="color:#32D74B">訓練完成</div>
                <div class="ios-body">檢測到你練習了 <b>{elapsed_mins} 分鐘</b>。</div>
            </div>
            """, unsafe_allow_html=True)
            
            col_save, col_discard = st.columns(2)
            with col_save:
                if st.button("✅ 確認存檔", use_container_width=True, type="primary"):
                    new_entry = pd.DataFrame([{
                        'Date': datetime.now(),
                        'BPM': current_bpm,
                        'Note_Type': selected_note_key,
                        'SPS': sps,
                        'Duration': elapsed_mins,
                        'Focus': "Auto-log"
                    }])
                    st.session_state.history = pd.concat([st.session_state.history, new_entry], ignore_index=True)
                    app.save_data(st.session_state.history)
                    st.session_state.start_time = None # 存檔後重置
                    st.toast("已自動保存記錄！")
                    st.rerun()
            with col_discard:
                if st.button("🗑️ 放棄", use_container_width=True):
                    st.session_state.start_time = None
                    st.rerun()

    # --- JS 音頻引擎 (保持不變) ---
    js_bpm = st.session_state.bpm
    js_playing = "true" if st.session_state.playing else "false"
    note_mult = app.note_multipliers.get(selected_note_key, 1)
    js_interval = (60 / js_bpm) / note_mult * 1000 
    js_ghost = "true" if ghost_mode else "false"
    
    components.html(f"""
    <script>
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!window.audioCtx) window.audioCtx = new window.AudioContext();
        
        var isPlaying = {js_playing};
        var interval = {js_interval};
        var isGhost = {js_ghost};
        var subdivisions = {note_mult};
        
        if (window.metronomeTimer) {{ clearInterval(window.metronomeTimer); window.metronomeTimer = null; }}
        if (!window.beatCount) window.beatCount = 0;

        if (isPlaying) {{
            if (window.audioCtx.state === 'suspended') window.audioCtx.resume();
            window.metronomeTimer = setInterval(() => {{
                var osc = window.audioCtx.createOscillator();
                var gainNode = window.audioCtx.createGain();
                osc.connect(gainNode);
                gainNode.connect(window.audioCtx.destination);
                
                var totalSubPerBar = 4 * subdivisions;
                var currentPos = window.beatCount % totalSubPerBar;
                var barNum = Math.floor(window.beatCount / totalSubPerBar) + 1;
                var isGhostBar = isGhost && (barNum % 4 === 0);

                if (!isGhostBar) {{
                    if (currentPos === 0) {{ osc.frequency.value = 1200; gainNode.gain.value = 0.8; }} 
                    else if (currentPos % subdivisions === 0) {{ osc.frequency.value = 800; gainNode.gain.value = 0.6; }} 
                    else {{ osc.frequency.value = 600; gainNode.gain.value = 0.3; }}
                    osc.start(); osc.stop(window.audioCtx.currentTime + 0.05);
                }}
                window.beatCount++;
            }}, interval);
        }} else {{ window.beatCount = 0; }}
    </script>
    """, height=0)

# ================= 📊 數據 (Stats) =================
elif st.session_state.page == "stats":
    st.markdown('<div class="ios-headline">數據中心</div>', unsafe_allow_html=True)
    
    if st.session_state.history.empty:
        st.info("尚無數據，請先開始訓練")
    else:
        df = st.session_state.history
        
        # CSV Export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📤 輸出 CSV 記錄", csv, "rap_log.csv", "text/csv", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Charts
        st.markdown('<div class="ios-subhead">SPS 趨勢</div>', unsafe_allow_html=True)
        st.line_chart(df.set_index('Date')['SPS'], color="#32D74B")
        
        st.markdown('<div class="ios-subhead">詳細日誌</div>', unsafe_allow_html=True)
        # 顯示表格，隱藏不需要的欄位
        display_df = df.sort_values('Date', ascending=False)
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(
            display_df[['Date', 'BPM', 'Duration', 'SPS']], 
            use_container_width=True, 
            hide_index=True
        )
