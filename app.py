import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.io.wavfile import write
from datetime import datetime, timedelta
import io
import os

# --- 1. 頁面全域設定 ---
st.set_page_config(page_title="Rap Trainer Pro", page_icon="🎤", layout="centered")

# CSS 優化：加入進度條樣式與大字體
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding-top: 1rem;
        padding-bottom: 5rem;
        max_width: 600px;
    }
    /* BPM 大數字 */
    [data-testid="stMetricValue"] {
        font-size: 60px !important;
        font-weight: 800 !important;
        color: #00E676 !important;
        text-align: center !important;
        text-shadow: 0px 0px 10px rgba(0, 230, 118, 0.3);
    }
    [data-testid="stMetricLabel"] {
        text-align: center !important;
        font-size: 16px !important;
        color: #888;
    }
    /* 自訂進度條文字 */
    .progress-text {
        text-align: center;
        color: #29B6F6;
        font-weight: bold;
        margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 核心邏輯層 ---
class RapTrainerApp:
    def __init__(self):
        self.data_file = "rap_log_v3.csv" # 升級檔案名稱以區隔舊版
        self.load_data()
        
        # 音符對應的倍率 (一個拍子有幾個音)
        self.note_multipliers = {
            "1/4 (四分音符)": 1,
            "1/8 (八分音符)": 2,
            "1/3 (三連音 Triplets)": 3,
            "1/16 (十六分音符 - 快嘴)": 4
        }

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                self.history = pd.read_csv(self.data_file)
                self.history['Date'] = pd.to_datetime(self.history['Date'])
            except:
                self.init_empty_db()
        else:
            self.init_empty_db()
        st.session_state.history = self.history

    def init_empty_db(self):
        # 新增 Note_Type 欄位
        self.history = pd.DataFrame(columns=['Date', 'BPM', 'Note_Type', 'SPS', 'Duration', 'Focus'])

    def save_data(self):
        self.history.to_csv(self.data_file, index=False)

    def calculate_sps(self, bpm, note_label):
        multiplier = self.note_multipliers.get(note_label, 1)
        return (bpm * multiplier) / 60

    def get_total_minutes(self):
        if self.history.empty:
            return 0
        return self.history['Duration'].sum()

    def generate_metronome(self, bpm, duration_sec, note_label, ghost_mode=False):
        sample_rate = 44100
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
        audio_track = np.zeros_like(t)
        
        # 根據選擇的音符決定每拍打幾下
        subdivisions = self.note_multipliers.get(note_label, 1)
        
        # 計算間隔
        beat_interval = 60.0 / bpm # 一拍的時間
        sub_interval = beat_interval / subdivisions # 細分音符的時間
        
        samples_per_sub = int(sample_rate * sub_interval)
        
        # 製作不同音色
        def make_click(freq, dur=0.03, vol=0.5):
            return vol * np.sin(2 * np.pi * freq * np.linspace(0, dur, int(sample_rate * dur)))

        high_click = make_click(1200, vol=0.8) # 強拍 (Bar頭)
        mid_click = make_click(800, vol=0.6)   # 正拍 (1, 2, 3, 4)
        low_click = make_click(600, vol=0.3)   # 弱拍 (細分音符 e.g. "and", "a")
        
        total_samples = len(audio_track)
        current_sample = 0
        
        # 計數器
        sub_count = 0 
        
        while current_sample < total_samples:
            # 計算現在是第幾拍 (用於 Ghost Mode 和 強拍)
            # 一個 Bar 通常 4 拍，一拍有 subdivisions 個音
            total_subs_per_bar = 4 * subdivisions
            bar_num = (sub_count // total_subs_per_bar) + 1
            pos_in_bar = sub_count % total_subs_per_bar
            
            # Ghost Mode: 每 4 小節，第 4 小節靜音
            is_ghost = ghost_mode and (bar_num % 4 == 0)
            
            if not is_ghost:
                click_sound = None
                
                if pos_in_bar == 0:
                    click_sound = high_click # Bar 的第一下
                elif pos_in_bar % subdivisions == 0:
                    click_sound = mid_click  # 每一拍的正拍
                else:
                    click_sound = low_click  # 細分音符
                
                if click_sound is not None and current_sample + len(click_sound) < total_samples:
                    audio_track[current_sample:current_sample+len(click_sound)] += click_sound
            
            current_sample += samples_per_sub
            sub_count += 1
                
        audio_track = np.int16(audio_track * 32767)
        virtual_file = io.BytesIO()
        write(virtual_file, sample_rate, audio_track)
        return virtual_file

    def add_log(self, bpm, note_type, focus, duration):
        new_entry = pd.DataFrame([{
            'Date': datetime.now(),
            'BPM': bpm,
            'Note_Type': note_type,
            'SPS': self.calculate_sps(bpm, note_type),
            'Focus': focus,
            'Duration': duration / 60 # 轉成分鐘存檔
        }])
        self.history = pd.concat([self.history, new_entry], ignore_index=True)
        self.save_data()
        st.session_state.history = self.history

app = RapTrainerApp()

# --- 3. UI 介面層 ---

# === 頂部：等級進度條 (Gamification) ===
total_mins = app.get_total_minutes()
level_cycle_mins = 120 # 每 2 小時 (120分鐘) 升級一次
current_cycle_mins = total_mins % level_cycle_mins
progress_percent = min(current_cycle_mins / level_cycle_mins, 1.0)
remaining_mins = int(level_cycle_mins - current_cycle_mins)

st.markdown(f"<div class='progress-text'>🚀 距離下一次 +5 BPM 挑戰還剩: {remaining_mins} 分鐘</div>", unsafe_allow_html=True)
st.progress(progress_percent)
if total_mins > 0 and remaining_mins == 120: # 剛好滿的時候
    st.toast("🎉 恭喜！你已累積滿 2 小時訓練！建議現在將 BPM +5 挑戰新極限！", icon="🔥")

# === Tab 分頁 ===
tab1, tab2 = st.tabs(["🔥 訓練台 (Trainer)", "📊 數據庫 (Analytics)"])

# === Tab 1: 訓練 ===
with tab1:
    # Session State 初始化
    if 'bpm' not in st.session_state: st.session_state.bpm = 85
    if 'note_type' not in st.session_state: st.session_state.note_type = "1/16 (十六分音符 - 快嘴)"

    # 1. 核心指標 (連動顯示)
    current_bpm = st.session_state.bpm
    current_note = st.session_state.note_type
    sps = app.calculate_sps(current_bpm, current_note)
    
    st.metric(label="目前設定 BPM", value=current_bpm, delta=f"{sps:.2f} SPS (音節/秒)")
    
    # 2. 控制面板 (Soundbrenner 風格)
    col_ctrl1, col_ctrl2 = st.columns([1, 1])
    
    with col_ctrl1:
        st.markdown("**1️⃣ 設定節拍類型**")
        note_selection = st.selectbox(
            "音符細分", 
            list(app.note_multipliers.keys()), 
            index=3, # 預設選 1/16
            label_visibility="collapsed",
            key="note_selector"
        )
        # 更新 session state
        st.session_state.note_type = note_selection

    with col_ctrl2:
        st.markdown("**2️⃣ 調整速度**")
        new_bpm = st.number_input("BPM", 50, 200, current_bpm, label_visibility="collapsed")
        if new_bpm != st.session_state.bpm:
            st.session_state.bpm = new_bpm
            st.rerun()
            
    # Slider 作為快速調整
    slider_bpm = st.slider("", 50, 180, st.session_state.bpm, key="bpm_slider", label_visibility="collapsed")
    if slider_bpm != st.session_state.bpm:
        st.session_state.bpm = slider_bpm
        st.rerun()

    # 3. 播放與 Ghost Mode
    with st.expander("⚙️ 進階設定 (Ghost Mode / 試聽時長)"):
        play_duration = st.slider("試聽生成時長 (秒)", 10, 60, 20)
        ghost_mode = st.toggle("👻 Ghost Mode (每 4 小節靜音 1 小節)")
    
    if st.button("▶️ 生成節拍音頻 (含細分音符)", type="primary"):
        audio_file = app.generate_metronome(st.session_state.bpm, play_duration, st.session_state.note_type, ghost_mode)
        st.audio(audio_file, format='audio/wav')
        if "1/16" in st.session_state.note_type:
            st.caption("💡 提示：你選擇了 16 分音符，請確保每個『滴』聲之間塞滿 4 個字！")

    st.markdown("---")

    # 4. 記錄打卡 (最重要的一步)
    st.markdown("<h4 style='text-align: center;'>📝 訓練打卡</h4>", unsafe_allow_html=True)
    
    with st.form("log_form"):
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            train_duration = st.number_input("本次訓練時長 (分鐘)", min_value=1, value=30, step=5)
        with f_col2:
            focus_text = st.text_input("訓練備註", placeholder="例：Eminem Godzilla 段落")
        
        submitted = st.form_submit_button("✅ 確認存檔")
        if submitted:
            app.add_log(st.session_state.bpm, st.session_state.note_type, focus_text, train_duration * 60)
            st.success(f"已記錄！累積時數更新中...")
            st.rerun()

# === Tab 2: 分析 ===
with tab2:
    if app.history.empty:
        st.info("尚無數據，請開始第一次訓練！")
    else:
        df = app.history.copy()
        
        # 數據總覽
        total_h = df['Duration'].sum() / 60
        avg_sps = df['SPS'].mean()
        max_bpm_rec = df['BPM'].max()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("累積時數", f"{total_h:.1f} 小時")
        m2.metric("平均語速", f"{avg_sps:.1f} SPS")
        m3.metric("最高 BPM", f"{max_bpm_rec}")
        
        st.markdown("---")
        
        # 詳細日誌表格
        st.markdown("#### 📋 詳細訓練日誌")
        display_df = df.sort_values(by='Date', ascending=False)
        display_df['Date'] = display_df['Date'].dt.strftime('%Y-%m-%d %H:%M')
        # 重新命名欄位以顯示好看一點
        display_df = display_df.rename(columns={
            'Note_Type': '音符', 
            'Duration': '時長(分)',
            'Focus': '備註'
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # 簡單圖表
        st.markdown("#### 📈 SPS (語速) 成長趨勢")
        st.line_chart(df.set_index('Date')['SPS'])