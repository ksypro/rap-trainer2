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
st.set_page_config(page_title="Rap Trainer Pro", page_icon="🎤", layout="centered")

# --- 2. 2025 Apple Design System (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        background-color: #000000 !important;
        color: #FFFFFF !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 6rem;
        max_width: 500px;
        margin: 0 auto;
    }

    /* iOS Glass Cards */
    .glass-card {
        background: #1C1C1E;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 16px;
    }
    
    /* Typography */
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
        color: #8E8E93;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .ios-body { font-size: 17px; color: #FFFFFF; line-height: 1.4; }
    .ios-caption { font-size: 13px; color: #8E8E93; }

    /* Progress Bar */
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
        background: #32D74B;
        height: 100%;
        border-radius: 4px;
        transition: width 0.5s ease;
    }

    /* Metronome UI */
    .bpm-big {
        font-size: 96px;
        font-weight: 800;
        text-align: center;
        color: #FFFFFF;
        line-height: 1;
        font-variant-numeric: tabular-nums;
        text-shadow: 0 0 20px rgba(50, 215, 75, 0.3);
    }
    .bpm-label {
        font-size: 17px;
        font-weight: 600;
        text-align: center;
        color: #32D74B;
        margin-bottom: 30px;
    }

    /* Input & Slider Styling */
    div.stSlider > div[data-baseweb="slider"] > div > div { background-color: #32D74B !important; }
    div.stSlider > div[data-baseweb="slider"] > div > div > div { background-color: #32D74B !important; }
    
    .stNumberInput input {
        text-align: center;
        background-color: #1C1C1E !important;
        color: white !important;
        border: 1px solid #333;
        border-radius: 12px;
        font-weight: bold;
        font-size: 20px;
    }

    /* Buttons */
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
    div.stButton > button:hover { background-color: #2C2C2E; border: 1px solid #444; }
    button[kind="primary"] { background-color: #32D74B !important; color: #000000 !important; }
    button[kind="primary"]:hover { opacity: 0.9; }

    /* Tags for Stats */
    .stat-tag {
        background: #333;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        margin-right: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 核心邏輯層 ---
class RapTrainerApp:
    def __init__(self):
        self.data_file = "rap_log_v7.csv" # 更新版本號
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

        # 3. 資料清洗
        if not self.history.empty:
            if 'Date' in self.history.columns:
                self.history['Date'] = pd.to_datetime(self.history['Date'], errors='coerce')
                self.history = self.history.dropna(subset=['Date'])
            for col in ['Duration', 'BPM', 'SPS']:
                if col in self.history.columns:
                    self.history[col] = pd.to_numeric(self.history[col], errors='coerce').fillna(0)
        
        if 'history' not in st.session_state:
            st.session_state.history = self.history
        
        # === 關鍵修改：啟動時讀取上次的 BPM ===
        if 'bpm_initialized' not in st.session_state:
            if not self.history.empty:
                try:
                    last_bpm = int(self.history.iloc[-1]['BPM'])
                    st.session_state.bpm = last_bpm
                except:
                    st.session_state.bpm = 85
            else:
                st.session_state.bpm = 85
            st.session_state.bpm_initialized = True

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

    def get_chopper_minutes(self):
        """只計算 1/16 音符的訓練時間"""
        if st.session_state.history.empty: return 0
        df = st.session_state.history
        # 篩選 Note_Type 包含 "1/16" 的資料
        chopper_df = df[df['Note_Type'].str.contains("1/16", na=False)]
        return chopper_df['Duration'].sum()

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
        st.session_state.start_time = time.time()
    else:
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
    
    # === 關鍵修改：只使用快嘴時間 (Chopper Mins) 計算等級 ===
    chopper_mins = app.get_chopper_minutes()
    
    level = int(chopper_mins // 120)
    mins_in_level = chopper_mins % 120
    mins_needed = 120 - mins_in_level
    progress_pct = (mins_in_level / 120) * 100
    
    titles = ["Novice", "Apprentice", "Chopper", "Master", "God Speed"]
    current_title = titles[min(level, len(titles)-1)]

    # === Level Card ===
    st.markdown(f"""
<div class="glass-card">
<div class="ios-subhead">CHOPPER LEVEL (1/16 Only)</div>
<div style="font-size: 28px; font-weight: 700; color: #FFFFFF;">{current_title} <span style="color:#32D74B">Lv.{level}</span></div>
<div style="font-size: 15px; color: #8E8E93; margin-top:4px;">快嘴累積 {int(chopper_mins)} 分鐘</div>
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
    # 這裡顯示目前快嘴 (1/16) 的最高 BPM 紀錄
    max_chopper_bpm = 0
    if not df.empty:
        chopper_df = df[df['Note_Type'].str.contains("1/16", na=False)]
        if not chopper_df.empty:
            max_chopper_bpm = chopper_df['BPM'].max()
    
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
            <div class="ios-subhead">快嘴紀錄</div>
            <div style="font-size: 32px; font-weight: 700; color: #32D74B;">{int(max_chopper_bpm)}</div>
            <div class="ios-caption">Max BPM</div>
        </div>
        """, unsafe_allow_html=True)

# ================= ⏱️ 節拍器 (Metronome) =================
elif st.session_state.page == "metronome":
    
    col_note, col_ghost = st.columns([2, 1])
    with col_note:
        note_display = {"1/4": "♩ Quarter", "1/8": "♫ Eighth", "1/3": "3 Triplet", "1/16": ":::: Sixteenth"}
        selected_note_key = st.selectbox("Note", list(app.note_multipliers.keys()), 
                                       index=3, label_visibility="collapsed", 
                                       format_func=lambda x: note_display.get(x, x))
    with col_ghost:
        ghost_mode = st.toggle("Ghost")

    st.markdown("<br>", unsafe_allow_html=True)

    current_bpm = st.session_state.bpm
    sps = app.calculate_sps(current_bpm, selected_note_key)
    
    st.markdown(f'<div class="bpm-big">{current_bpm}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bpm-label">{sps:.1f} 音節 / 秒</div>', unsafe_allow_html=True)

    st.slider("BPM Slider", 50, 200, key="bpm_slider", value=st.session_state.bpm, on_change=update_bpm_from_slider, label_visibility="collapsed")
    
    c_spacer1, c_input, c_spacer2 = st.columns([1, 2, 1])
    with c_input:
        st.number_input("BPM Input", 50, 200, key="bpm_number", value=st.session_state.bpm, on_change=update_bpm_from_number, label_visibility="collapsed")

    st.markdown("<br>", unsafe_allow_html=True)

    btn_label = "⏹ 停止訓練" if st.session_state.playing else "▶ 開始訓練"
    if st.button(btn_label, type="primary", use_container_width=True):
        toggle_play()
        st.rerun()

    # 自動保存
    if not st.session_state.playing and st.session_state.start_time:
        elapsed = time.time() - st.session_state.start_time
        elapsed_mins = elapsed / 60
        
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
                    st.session_state.start_time = None 
                    st.toast("記錄已保存！")
                    st.rerun()
            with col_discard:
                if st.button("🗑️ 放棄", use_container_width=True):
                    st.session_state.start_time = None
                    st.rerun()

    # JS 引擎 (含鼓聲)
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

        function playSound(type) {{
            if (window.audioCtx.state === 'suspended') window.audioCtx.resume();
            var osc = window.audioCtx.createOscillator();
            var gainNode = window.audioCtx.createGain();
            osc.connect(gainNode);
            gainNode.connect(window.audioCtx.destination);
            var now = window.audioCtx.currentTime;

            if (type === 'kick') {{
                osc.frequency.setValueAtTime(150, now);
                osc.frequency.exponentialRampToValueAtTime(0.01, now + 0.5);
                gainNode.gain.setValueAtTime(1, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.5);
                osc.start(now); osc.stop(now + 0.5);
            }} else if (type === 'hihat') {{
                osc.type = 'square';
                osc.frequency.setValueAtTime(800, now);
                gainNode.gain.setValueAtTime(0.2, now);
                gainNode.gain.exponentialRampToValueAtTime(0.01, now + 0.05);
                osc.start(now); osc.stop(now + 0.05);
            }} else {{
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
        
        # 1. 輸出按鈕
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📤 輸出 CSV 記錄", csv, "rap_log.csv", "text/csv", use_container_width=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        # 2. 分類檢視 (Tabs)
        tab_list = ["全部", "1/16 快嘴", "1/8 基礎", "1/3 三連音"]
        selected_tab = st.selectbox("選擇分析模式", tab_list)
        
        # 根據選擇過濾數據
        filtered_df = df.copy()
        if selected_tab == "1/16 快嘴":
            filtered_df = df[df['Note_Type'].str.contains("1/16", na=False)]
        elif selected_tab == "1/8 基礎":
            filtered_df = df[df['Note_Type'].str.contains("1/8", na=False)]
        elif selected_tab == "1/3 三連音":
            filtered_df = df[df['Note_Type'].str.contains("1/3", na=False)]
        
        # 3. 顯示最高 BPM 紀錄
        if not filtered_df.empty:
            max_val = filtered_df['BPM'].max()
            avg_val = filtered_df['BPM'].mean()
            st.markdown(f"""
            <div class="glass-card">
                <div class="ios-subhead">{selected_tab} 表現</div>
                <div style="display:flex; justify-content:space-around; margin-top:10px;">
                    <div style="text-align:center;">
                        <div style="font-size:24px; font-weight:700; color:#32D74B;">{int(max_val)}</div>
                        <div class="ios-caption">最高 BPM</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:24px; font-weight:700; color:white;">{int(avg_val)}</div>
                        <div class="ios-caption">平均 BPM</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 4. 趨勢圖 (只畫選中的音符類型)
            st.markdown('<div class="ios-subhead">BPM 成長趨勢</div>', unsafe_allow_html=True)
            chart_data = filtered_df.sort_values('Date')
            st.line_chart(chart_data.set_index('Date')['BPM'], color="#32D74B")
        else:
            st.info(f"尚無 {selected_tab} 的訓練記錄。")

        # 5. 各音符排行榜 (Summary)
        st.markdown('<div class="ios-subhead">各音符最高 BPM 紀錄</div>', unsafe_allow_html=True)
        if not df.empty:
            best_scores = df.groupby('Note_Type')['BPM'].max().reset_index()
            # 簡單美化表格
            st.dataframe(
                best_scores.rename(columns={'Note_Type': '音符類型', 'BPM': '最高紀錄'}),
                use_container_width=True,
                hide_index=True
            )
