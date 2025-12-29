import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.io.wavfile import write
from datetime import datetime, timedelta
import io
import os
import time
# 嘗試引入 Github，如果沒有設定 secrets 也不會崩潰
try:
    from github import Github
    has_github = True
except ImportError:
    has_github = False

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="Rap Trainer Pro", page_icon="🎤", layout="centered")

# --- CSS 樣式優化 (仿 Soundbrenner & iOS) ---
st.markdown("""
    <style>
    /* 隱藏預設元件 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 容器優化 */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
        max_width: 600px;
    }
    
    /* 1. 節拍器頁面樣式 */
    .metric-bpm {
        font-size: 80px !important;
        font-weight: 900 !important;
        color: white !important;
        text-align: center;
        margin-bottom: 0px;
        line-height: 1;
    }
    .metric-sub {
        font-size: 18px !important;
        color: #888 !important;
        text-align: center;
        margin-top: 0px;
    }
    
    /* 2. 主頁等級卡片樣式 (仿 iOS 薄荷綠) */
    .level-card {
        background-color: #1c1c1e;
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #333;
    }
    .level-title {
        color: #98fb98; /* 薄荷綠 */
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .level-big-num {
        font-size: 48px;
        font-weight: bold;
        color: white;
        margin: 10px 0;
    }
    .level-progress-bg {
        background-color: #333;
        height: 6px;
        border-radius: 3px;
        width: 100%;
        margin-top: 10px;
    }
    .level-progress-fill {
        background-color: #98fb98;
        height: 6px;
        border-radius: 3px;
    }
    .level-desc {
        color: #888;
        font-size: 12px;
        margin-top: 8px;
        text-align: right;
    }

    /* 按鈕樣式優化 */
    div.stButton > button {
        border-radius: 20px;
        font-weight: bold;
        border: none;
    }
    div.stButton > button:hover {
        opacity: 0.8;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心邏輯層 ---
class RapTrainerApp:
    def __init__(self):
        self.data_file = "rap_log_v3.csv"
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
        
        # 如果 GitHub 失敗，讀取本地 (Streamlit Cloud session persistence)
        if not data_loaded:
            if os.path.exists(self.data_file):
                try:
                    self.history = pd.read_csv(self.data_file)
                    self.history['Date'] = pd.to_datetime(self.history['Date'])
                except:
                    self.init_empty_db()
            else:
                self.init_empty_db()
        
        # 同步到 session state
        if 'history' not in st.session_state:
            st.session_state.history = self.history

    def init_empty_db(self):
        self.history = pd.DataFrame(columns=['Date', 'BPM', 'Note_Type', 'SPS', 'Duration', 'Focus'])

    def save_data(self, df):
        # 1. 存本地
        df.to_csv(self.data_file, index=False)
        st.session_state.history = df
        
        # 2. 存 GitHub (如果有的話)
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
            except Exception as e:
                print(e)
        return False

    def calculate_sps(self, bpm, note_label):
        # 處理 key matching
        for k, v in self.note_multipliers.items():
            if k in note_label:
                return (bpm * v) / 60
        return bpm / 60

    def get_total_minutes(self):
        if st.session_state.history.empty: return 0
        return st.session_state.history['Duration'].sum()

    def generate_metronome(self, bpm, duration_sec, note_label, ghost_mode=False):
        sample_rate = 44100
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
        audio_track = np.zeros_like(t)
        
        # 解析倍率
        subdivisions = 1
        for k, v in self.note_multipliers.items():
            if k in note_label:
                subdivisions = v
                break
        
        beat_interval = 60.0 / bpm
        sub_interval = beat_interval / subdivisions
        samples_per_sub = int(sample_rate * sub_interval)
        
        def make_click(freq, dur=0.03, vol=0.5):
            return vol * np.sin(2 * np.pi * freq * np.linspace(0, dur, int(sample_rate * dur)))

        high_click = make_click(1200, vol=0.9)
        mid_click = make_click(800, vol=0.6)
        low_click = make_click(600, vol=0.3)
        
        total_samples = len(audio_track)
        current_sample = 0
        sub_count = 0 
        
        while current_sample < total_samples:
            total_subs_per_bar = 4 * subdivisions
            bar_num = (sub_count // total_subs_per_bar) + 1
            pos_in_bar = sub_count % total_subs_per_bar
            is_ghost = ghost_mode and (bar_num % 4 == 0)
            
            if not is_ghost:
                click_sound = None
                if pos_in_bar == 0: click_sound = high_click
                elif pos_in_bar % subdivisions == 0: click_sound = mid_click
                else: click_sound = low_click
                
                if click_sound is not None and current_sample + len(click_sound) < total_samples:
                    audio_track[current_sample:current_sample+len(click_sound)] += click_sound
            current_sample += samples_per_sub
            sub_count += 1
            
        audio_track = np.int16(audio_track * 32767)
        virtual_file = io.BytesIO()
        write(virtual_file, sample_rate, audio_track)
        return virtual_file

app = RapTrainerApp()

# --- 3. 狀態同步 Callback (修復 BPM 跳轉 Bug) ---
if 'bpm' not in st.session_state: st.session_state.bpm = 85

def update_bpm_from_slider():
    st.session_state.bpm = st.session_state.bpm_slider

def update_bpm_from_number():
    st.session_state.bpm = st.session_state.bpm_number

# --- 4. 導航與頁面結構 ---
# 側邊欄隱藏式導航 (模擬 App 底部 Tab，這裡用 Sidebar 替代)
page = st.sidebar.radio("導航", ["🏠 主頁", "⏱️ 節拍器", "📊 數據庫"], label_visibility="collapsed")

# ================= 🏠 主頁 (仿 iOS 訓練記錄) =================
if page == "🏠 主頁":
    st.markdown("<h2 style='text-align: center;'>主頁</h2>", unsafe_allow_html=True)
    
    # 讀取數據
    df = st.session_state.history
    total_mins = app.get_total_minutes()
    
    # 計算等級邏輯: 每 2 小時 (120分) 升一級
    level = int(total_mins // 120)
    mins_in_level = total_mins % 120
    mins_needed = 120 - mins_in_level
    progress_pct = (mins_in_level / 120) * 100
    
    # 獲取上次練習的 BPM，用來建議
    last_bpm = 85
    if not df.empty:
        last_bpm = df.iloc[-1]['BPM']
    suggested_bpm = last_bpm + 5

    # 顯示薄荷綠卡片
    st.markdown(f"""
    <div class="level-card">
        <div class="level-title">薄荷綠 (等級 {level})</div>
        <div class="level-big-num">{int(total_mins // 60)} <span style="font-size:20px; color:#888;">小時</span> {int(total_mins % 60)} <span style="font-size:20px; color:#888;">分鐘</span></div>
        <div style="color: #aaa; font-size: 14px;">練習總時數</div>
        <div class="level-progress-bg">
            <div class="level-progress-fill" style="width: {progress_pct}%;"></div>
        </div>
        <div class="level-desc">{int(mins_needed)} 分鐘 到下一等級 (+5 BPM 挑戰)</div>
    </div>
    """, unsafe_allow_html=True)

    # 快捷入口
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"💡 下個目標: {suggested_bpm} BPM")
    with col2:
        st.success(f"🔥 連續打卡: {df['Date'].dt.date.nunique()} 天")
        
    if st.button("🚀 開始今日訓練", type="primary", use_container_width=True):
        # 這裡其實只需要提示用戶切換頁面，Streamlit 無法直接切換 Radio
        st.caption("請點擊左上角選單切換至『⏱️ 節拍器』頁面")

# ================= ⏱️ 節拍器 (仿 Soundbrenner) =================
elif page == "⏱️ 節拍器":
    # 頂部控制列 (Time Sig | Note | Settings)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.button("4/4", disabled=True, use_container_width=True) # 裝飾用，暫不支援變拍號
    with c2:
        # 音符選擇 (用 Selectbox 模擬圖標點擊)
        note_display = {"1/4": "♩", "1/8": "♫", "1/3": "3", "1/16": "::::"}
        selected_note_key = st.selectbox("音符", list(app.note_multipliers.keys()), 
                                       index=3, label_visibility="collapsed", 
                                       format_func=lambda x: f"{x} {note_display.get(x, '')}")
    with c3:
        with st.popover("設定"):
            ghost_mode = st.toggle("👻 Ghost Mode")
            duration_set = st.slider("生成時長(秒)", 10, 60, 30)

    st.markdown("<br>", unsafe_allow_html=True)

    # 中間大 BPM 顯示
    current_bpm = st.session_state.bpm
    sps = app.calculate_sps(current_bpm, selected_note_key)
    
    st.markdown(f'<div class="metric-bpm">{current_bpm}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-sub">BPM</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center; color:#29B6F6; margin-bottom:20px;">{sps:.1f} 音節/秒</div>', unsafe_allow_html=True)

    # 底部轉盤 (Slider)
    # 使用 callback 機制修復 bug
    st.slider("BPM Slider", 50, 200, 
              key="bpm_slider", 
              value=st.session_state.bpm, 
              on_change=update_bpm_from_slider, 
              label_visibility="collapsed")
    
    # 微調按鈕 (Optional)
    c_minus, c_input, c_plus = st.columns([1, 2, 1])
    with c_minus:
        if st.button("-", use_container_width=True):
            st.session_state.bpm -= 1
            st.rerun()
    with c_input:
        # 數字輸入框也同步
        st.number_input("Input", 50, 200, 
                        key="bpm_number", 
                        value=st.session_state.bpm, 
                        on_change=update_bpm_from_number, 
                        label_visibility="collapsed")
    with c_plus:
        if st.button("+", use_container_width=True):
            st.session_state.bpm += 1
            st.rerun()

    st.markdown("---")
    
    # 播放按鈕
    play_col, log_col = st.columns([2, 1])
    with play_col:
        if st.button("▶️ 生成並播放", type="primary", use_container_width=True):
            audio = app.generate_metronome(st.session_state.bpm, duration_set, selected_note_key, ghost_mode)
            st.audio(audio, format='audio/wav')
    
    with log_col:
        with st.popover("📝 打卡"):
            with st.form("quick_log"):
                t_min = st.number_input("分鐘", 1, 120, 30)
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
                    st.toast("已儲存！")

# ================= 📊 數據庫 (分析) =================
elif page == "📊 數據庫":
    st.markdown("<h2 style='text-align: center;'>數據分析</h2>", unsafe_allow_html=True)
    
    if st.session_state.history.empty:
        st.info("尚無數據，請先去訓練！")
    else:
        df = st.session_state.history.copy()
        
        # 趨勢圖
        st.markdown("#### 📈 速度成長")
        st.line_chart(df.set_index('Date')['BPM'], color="#00E676")
        
        # 詳細表格
        st.markdown("#### 📋 歷史記錄")
        disp = df.sort_values('Date', ascending=False)
        disp['Date'] = disp['Date'].dt.strftime('%m-%d %H:%M')
        st.dataframe(disp[['Date', 'BPM', 'Note_Type', 'Duration', 'Focus']], use_container_width=True, hide_index=True)
        
        # 備份下載
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 下載備份 CSV", csv, "rap_log.csv", "text/csv")
