import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import time
from datetime import datetime
import streamlit.components.v1 as components

# 嘗試引入 Github (若無配置則忽略)
try:
    from github import Github
    has_github = True
except ImportError:
    has_github = False

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="Rap Trainer Pro", page_icon="🎤", layout="centered")

# --- 2. 2025 Apple Design System (CSS 修復版) ---
st.markdown("""
    <style>
    /* 全局字體與背景重置 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        background-color: #000000 !important; /* 純黑背景 */
        color: #FFFFFF !important;
    }

    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 6rem;
        max_width: 500px; /* 手機寬度優化 */
        margin: 0 auto;
    }

    /* === iOS Glass Cards (玻璃擬態) === */
    .glass-card {
        background: #1C1C1E; /* iOS 深色模式卡片底色 */
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 16px;
    }
    
    /* 文字層級 */
    .ios-headline {
        font-size: 34px;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: #FFFFFF;
        margin-bottom: 12px;
    }
    .ios-subhead {
        font-size: 13px;
        font-weight: 600;
        color: #8E8E93; /* Apple Gray */
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
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
        margin-bottom: 8px;
        overflow: hidden;
    }
    .progress-bar {
        background: #32D74B; /* iOS System Green */
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s ease;
    }

    /* === 節拍器介面 === */
    .bpm-big {
        font-size: 96px;
        font-weight: 800;
        text-align: center;
        color: #FFFFFF;
        line-height: 1;
        font-variant-numeric: tabular-nums;
        text-shadow: 0 0 20px rgba(50, 215, 75, 0.3); /* 綠色微光 */
    }
    .bpm-label {
        font-size: 17px;
        font-weight: 600;
        text-align: center;
        color: #32D74B;
        margin-bottom: 30px;
    }

    /* 輸入框與滑桿優化 */
    div.stSlider > div[data-baseweb="slider"] > div > div {
        background-color: #32D74B !important;
    }
    div.stSlider > div[data-baseweb="slider"] > div > div > div {
        background-color: #32D74B !important;
    }
    
    /* 數字輸入框 */
    .stNumberInput input {
        text-align: center;
        background-color: #1C1C1E !important;
        color: white !important;
        border: 1px solid #333;
        border-radius: 12px;
        font-weight: bold;
        font-size: 20px;
    }

    /* 按鈕樣式 */
    div.stButton > button {
        background-color: #1C1C1E;
        color: #FFFFFF;
        border: none;
        border-radius: 14px;
        font-weight: 600;
        font-size: 17px;
        padding: 12px 0;
        height: auto;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #2C2C2E;
        border: 1px solid #444;
    }
    /* 主要按鈕 (綠色) */
    button[kind="primary"] {
        background-color: #32D74B !important;
        color: #000000 !important;
    }
    button[kind="primary"]:hover {
        opacity: 0.9;
    }

    /* 導航列 */
    .nav-wrapper {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-bottom: 20px;
        padding-bottom: 20px;
        border-bottom: 1px solid #333;
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
        # 1. 嘗試從 GitHub 讀取
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
        
        # 2. 嘗試從本地讀取
        if not data_loaded:
            if os.path.exists(self.data_file):
                try:
                    self.history = pd.read_csv(self.data_file)
                except:
                    self.init_empty_db()
            else:
                self.init_empty_db()

        # 3. 資料清洗 (修復 AttributeError)
        if not self.history.empty:
            # 強制轉換日期格式，錯誤變成 NaT
            if 'Date' in self.history.columns:
                self.history['Date'] = pd.to_datetime(self.history['Date'], errors='coerce')
                self.history = self.history.dropna(subset=['Date']) # 移除壞掉的日期
            
            # 確保數字欄位正確
            for col in ['Duration', 'BPM', 'SPS']:
                if col in self.history.columns:
                    self.history[col] = pd.to_numeric(self.history[col], errors='coerce').fillna(0)
        
        if 'history' not in st.session_state:
            st.session_state.history = self.history

    def init_empty_db(self):
        self.history = pd.DataFrame(columns=['Date', 'BPM', 'Note_Type', 'SPS', 'Duration', 'Focus'])

    def save_data(self, df):
        # 存本地
        df.to_csv(self.data_file, index=False)
        st.session_state.history = df
        
        # 存 GitHub
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
if 'start_time' not in st.session_state: st.session_state.start_time = None 

def update_bpm_from_slider(): st.session_state.bpm = st.session_state.bpm_slider
def update_bpm_from_number(): st.session_state.bpm = st.session_state.bpm_number

def toggle_play():
    st.session_state.playing = not st.session_state.playing
    if st.session_state.playing:
        st.session_state.start_time = time.time() # 開始計時
    else:
        # 停止時不自動存，交給 UI 處理
        pass

def nav_to(page_name):
    st.session_state.page = page_name

# --- 5. 介面導航 ---
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("🏠 主頁", use_container_width=True): nav_to("home")
with nav2:
    if st.button("⏱️ 節拍", use_container_width=True): nav_to("metronome")
with nav3:
    if st.button("📊 數據", use_container_width=True): nav_to("stats")

st.markdown("---")

# ================= 🏠 主頁 (Dashboard) =================
if st.session_state.page == "home":
    st.markdown('<div class="ios-headline">總覽</div>', unsafe_allow_html=True)
    
    df = st.session_state.history
    total_mins = app.get_total_minutes()
    
    # 計算等級
    level = int(total_mins // 120)
    mins_in_level = total_mins % 120
    mins_needed = 120 - mins_in_level
    progress_pct = (mins_in_level / 120) * 100
    
    titles = ["Novice", "Apprentice", "Chopper", "Master", "Legend"]
    current_title = titles[min(level, len(titles)-1)]

    # === Level Card (HTML 縮排已修復) ===
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

    # === 數據卡片 ===
    c1, c2 = st.columns(2)
    days_streak = df['Date'].dt.date.nunique() if not df.empty else 0
    last_bpm = df.iloc[-1]['BPM'] if not df.empty else 85
    
    with c1:
        st.markdown(f"""
        <div class="glass-card" style="text-align:center; padding:16px;">
            <div class="ios-subhead">連續打卡</div>
            <div style="font-size: 32px; font-weight: 700; color: white;">{days_streak}</div>
            <div class="ios-caption">天</div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown(f"""
        <div class="glass-card" style="text-align:center; padding:16px;">
            <div class="ios-subhead">建議速度</div>
            <div style="font-size: 32px; font-weight: 700; color: #32D74B;">{int(last_bpm + 5)}</div>
            <div class="ios-caption">BPM</div>
        </div>
        """, unsafe_allow_html=True)

# ================= ⏱️ 節拍器 (Metronome) =================
elif st.session_state.page == "metronome":
    
    # 頂部設置
    col_note, col_ghost = st.columns([2, 1])
    with col_note:
        note_display = {"1/4": "♩ Quarter", "1/8": "♫ Eighth", "1/3": "3 Triplet", "1/16": ":::: Sixteenth"}
        selected_note_key = st.selectbox("Note", list(app.note_multipliers.keys()), 
                                       index=3, label_visibility="collapsed", 
                                       format_func=lambda x: note_display.get(x, x))
    with col_ghost:
        ghost_mode = st.toggle("Ghost")

    st.markdown("<br>", unsafe_allow_html=True)

    # 大數字顯示
    current_bpm = st.session_state.bpm
    sps = app.calculate_sps(current_bpm, selected_note_key)
    
    st.markdown(f'<div class="bpm-big">{current_bpm}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bpm-label">{sps:.1f} 音節 / 秒</div>', unsafe_allow_html=True)

    # 簡單的滑桿 (無多餘方格)
    st.slider("BPM Slider", 50, 200, key="bpm_slider", value=st.session_state.bpm, on_change=update_bpm_from_slider, label_visibility="collapsed")
    
    # 數字輸入框
    c_spacer1, c_input, c_spacer2 = st.columns([1, 2, 1])
    with c_input:
        st.number_input("BPM Input", 50, 200, key="bpm_number", value=st.session_state.bpm, on_change=update_bpm_from_number, label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)

    # 播放按鈕
    btn_label = "⏹ 停止訓練" if st.session_state.playing else "▶ 開始訓練"
    if st.button(btn_label, type="primary", use_container_width=True):
        toggle_play()
        st.rerun()

    # 自動保存邏輯 (停止播放後觸發)
    if not st.session_state.playing and st.session_state.start_time:
        elapsed = time.time() - st.session_state.start_time
        elapsed_mins = elapsed / 60
        
        # 防止誤觸 (小於 10 秒不存)
        if elapsed < 10:
            st.info("練習時間太短，未記錄。")
            st.session_state.start_time = None
        else:
            st.markdown(f"""
            <div class="glass-card" style="border-color:#32D74B; margin-top:20px;">
                <div class="ios-subhead" style="color:#32D74B">訓練完成</div>
                <div class="ios-body">本次練習時長：<b>{int(elapsed)} 秒</b> ({elapsed_mins:.1f} 分)</div>
            </div>
            """, unsafe_allow_html=True)
            
            col_save, col_discard = st.columns(2)
            with col_save:
                if st.button("✅ 存檔", use_container_width=True, type="primary"):
                    new_entry = pd.DataFrame([{
                        'Date': datetime.now(),
                        'BPM': current_bpm,
                        'Note_Type': selected_note_key,
                        'SPS': sps,
                        'Duration': round(elapsed_mins, 2),
                        'Focus': "Auto-log"
                    }])
                    st.session_state.history = pd.concat([st.session_state.history, new_entry], ignore_index=True)
                    app.save_data(st.session_state.history)
                    st.session_state.start_time = None # 重置
                    st.toast("記錄已保存！")
                    st.rerun()
            with col_discard:
                if st.button("🗑️ 放棄", use_container_width=True):
                    st.session_state.start_time = None
                    st.rerun()

    # --- 鼓聲版 JS 音頻引擎 ---
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

        // 合成鼓聲函數 (Kick, Snare, Hihat)
        function playSound(type) {{
            if (window.audioCtx.state === 'suspended') window.audioCtx.resume();
            var osc = window.audioCtx.createOscillator();
            var gainNode = window.audioCtx.createGain();
            osc.connect(gainNode);
            gainNode.connect(window.audioCtx.destination);
            var now = window.audioCtx.currentTime;

            if (type === 'kick') {{
                // 大鼓
                osc.frequency.setValueAtTime(150, now);
                osc.frequency.exponentialRampToValueAtTime(0.01, now + 0.5);
                gainNode.gain.setValueAtTime(1, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.5);
                osc.start(now); osc.stop(now + 0.5);
            }} else if (type === 'hihat') {{
                // 腳踏鈸
                osc.type = 'square';
                osc.frequency.setValueAtTime(800, now);
                gainNode.gain.setValueAtTime(0.2, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.05);
                osc.start(now); osc.stop(now + 0.05);
            }} else {{
                // 小鼓 (Snare-ish)
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(300, now);
                gainNode.gain.setValueAtTime(0.4, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.1);
                osc.start(now); osc.stop(now + 0.1);
            }}
        }}

        if (isPlaying) {{
            window.metronomeTimer = setInterval(() => {{
                var totalSubPerBar = 4 * subdivisions;
                var currentPos = window.beatCount % totalSubPerBar;
                var barNum = Math.floor(window.beatCount / totalSubPerBar) + 1;
                var isGhostBar = isGhost && (barNum % 4 === 0);

                if (!isGhostBar) {{
                    if (currentPos === 0) {{ playSound('kick'); }} 
                    else if (currentPos % subdivisions === 0) {{ playSound('snare'); }} 
                    else {{ playSound('hihat'); }}
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
        
        # 輸出按鈕
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📤 輸出 CSV 記錄", csv, "rap_log.csv", "text/csv", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 圖表
        st.markdown('<div class="ios-subhead">SPS 趨勢</div>', unsafe_allow_html=True)
        # 確保日期排序正確
        chart_df = df.sort_values('Date')
        st.line_chart(chart_df.set_index('Date')['SPS'], color="#32D74B")
        
        # 表格
        st.markdown('<div class="ios-subhead">詳細日誌</div>', unsafe_allow_html=True)
        display_df = df.sort_values('Date', ascending=False)
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(
            display_df[['Date', 'BPM', 'Duration', 'SPS']], 
            use_container_width=True, 
            hide_index=True
        )
