import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.io.wavfile import write
from datetime import datetime
import io
import os
from github import Github # 引入 GitHub 機器人

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Rap Trainer Pro", page_icon="🎤", layout="centered")

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
    .progress-text {
        text-align: center;
        color: #29B6F6;
        font-weight: bold;
        margin-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. GitHub 雲端存取邏輯 (核心修改) ---
class GitHubManager:
    def __init__(self):
        # 從 Secrets 讀取設定
        try:
            self.token = st.secrets["github"]["token"]
            self.repo_name = st.secrets["github"]["repo_name"]
            self.branch = st.secrets["github"]["branch"]
            self.g = Github(self.token)
            self.repo = self.g.get_repo(self.repo_name)
            self.file_path = "rap_log_v3.csv"
            self.connected = True
        except Exception as e:
            st.error(f"GitHub 連線失敗: 請檢查 Secrets 設定。錯誤: {e}")
            self.connected = False

    def load_data(self):
        """從 GitHub 下載最新的 CSV"""
        if not self.connected: return self.init_empty_df()
        
        try:
            contents = self.repo.get_contents(self.file_path, ref=self.branch)
            decoded = contents.decoded_content.decode("utf-8")
            df = pd.read_csv(io.StringIO(decoded))
            df['Date'] = pd.to_datetime(df['Date'])
            return df
        except:
            # 如果檔案不存在，回傳空的
            return self.init_empty_df()

    def save_data(self, df):
        """將 CSV 上傳回 GitHub"""
        if not self.connected: return False
        
        csv_content = df.to_csv(index=False)
        
        try:
            # 嘗試取得現有檔案
            contents = self.repo.get_contents(self.file_path, ref=self.branch)
            # 更新檔案 (Update)
            self.repo.update_file(
                path=contents.path,
                message=f"Update rap stats: {datetime.now().strftime('%Y-%m-%d')}",
                content=csv_content,
                sha=contents.sha,
                branch=self.branch
            )
        except:
            # 如果檔案不存在，建立新檔案 (Create)
            self.repo.create_file(
                path=self.file_path,
                message="Init rap stats",
                content=csv_content,
                branch=self.branch
            )
        return True

    def init_empty_df(self):
        return pd.DataFrame(columns=['Date', 'BPM', 'Note_Type', 'SPS', 'Duration', 'Focus'])

# --- 3. App 邏輯層 ---
class RapTrainerApp:
    def __init__(self):
        self.gh = GitHubManager()
        # 初始化時從 GitHub 讀取
        if 'history' not in st.session_state:
            st.session_state.history = self.gh.load_data()
            
        self.note_multipliers = {
            "1/4 (四分音符)": 1,
            "1/8 (八分音符)": 2,
            "1/3 (三連音 Triplets)": 3,
            "1/16 (十六分音符 - 快嘴)": 4
        }

    def calculate_sps(self, bpm, note_label):
        multiplier = self.note_multipliers.get(note_label, 1)
        return (bpm * multiplier) / 60

    def get_total_minutes(self):
        if st.session_state.history.empty: return 0
        return st.session_state.history['Duration'].sum()

    def generate_metronome(self, bpm, duration_sec, note_label, ghost_mode=False):
        # (音頻生成代碼保持不變，為了節省篇幅省略細節，功能相同)
        sample_rate = 44100
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
        audio_track = np.zeros_like(t)
        subdivisions = self.note_multipliers.get(note_label, 1)
        beat_interval = 60.0 / bpm
        sub_interval = beat_interval / subdivisions
        samples_per_sub = int(sample_rate * sub_interval)
        
        def make_click(freq, dur=0.03, vol=0.5):
            return vol * np.sin(2 * np.pi * freq * np.linspace(0, dur, int(sample_rate * dur)))

        high_click = make_click(1200, vol=0.8)
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

    def add_log_and_save(self, bpm, note_type, focus, duration):
        new_entry = pd.DataFrame([{
            'Date': datetime.now(),
            'BPM': bpm,
            'Note_Type': note_type,
            'SPS': self.calculate_sps(bpm, note_type),
            'Focus': focus,
            'Duration': duration / 60
        }])
        
        # 1. 更新 session state (為了讓 UI 瞬間反應)
        st.session_state.history = pd.concat([st.session_state.history, new_entry], ignore_index=True)
        
        # 2. 上傳到 GitHub (永久存檔)
        with st.spinner("正在雲端同步數據..."):
            success = self.gh.save_data(st.session_state.history)
            if success:
                st.toast("✅ 數據已安全備份至 GitHub！", icon="☁️")
            else:
                st.error("❌ 雲端備份失敗，請檢查 Secrets 設定。")

app = RapTrainerApp()

# --- 4. UI 介面層 ---
total_mins = app.get_total_minutes()
level_cycle_mins = 120
current_cycle_mins = total_mins % level_cycle_mins
progress_percent = min(current_cycle_mins / level_cycle_mins, 1.0)
remaining_mins = int(level_cycle_mins - current_cycle_mins)

st.markdown(f"<div class='progress-text'>🚀 距離下一次 +5 BPM 挑戰還剩: {remaining_mins} 分鐘</div>", unsafe_allow_html=True)
st.progress(progress_percent)

tab1, tab2 = st.tabs(["🔥 訓練台", "📊 數據庫"])

# === Tab 1: 訓練 ===
with tab1:
    if 'bpm' not in st.session_state: st.session_state.bpm = 85
    if 'note_type' not in st.session_state: st.session_state.note_type = "1/16 (十六分音符 - 快嘴)"

    current_bpm = st.session_state.bpm
    current_note = st.session_state.note_type
    sps = app.calculate_sps(current_bpm, current_note)
    
    st.metric(label="目前設定 BPM", value=current_bpm, delta=f"{sps:.2f} SPS")
    
    c1, c2 = st.columns(2)
    with c1: 
        st.session_state.note_type = st.selectbox("音符", list(app.note_multipliers.keys()), index=3, label_visibility="collapsed")
    with c2:
        new_bpm = st.number_input("BPM", 50, 200, current_bpm, label_visibility="collapsed")
        if new_bpm != st.session_state.bpm:
            st.session_state.bpm = new_bpm
            st.rerun()

    slider_bpm = st.slider("", 50, 180, st.session_state.bpm, key="bpm_slider", label_visibility="collapsed")
    if slider_bpm != st.session_state.bpm:
        st.session_state.bpm = slider_bpm
        st.rerun()

    with st.expander("⚙️ 進階設定"):
        play_duration = st.slider("試聽時長", 10, 60, 20)
        ghost_mode = st.toggle("👻 Ghost Mode")
    
    if st.button("▶️ 播放", type="primary"):
        audio = app.generate_metronome(st.session_state.bpm, play_duration, st.session_state.note_type, ghost_mode)
        st.audio(audio, format='audio/wav')

    st.markdown("---")
    st.markdown("<h4 style='text-align: center;'>📝 打卡</h4>", unsafe_allow_html=True)
    with st.form("log"):
        c1, c2 = st.columns(2)
        with c1: t_dur = st.number_input("時長(分)", 1, value=30, step=5)
        with c2: focus = st.text_input("備註", placeholder="例：Eminem")
        if st.form_submit_button("✅ 存檔 (同步至雲端)"):
            app.add_log_and_save(st.session_state.bpm, st.session_state.note_type, focus, t_dur * 60)
            st.rerun()

# === Tab 2: 分析 ===
with tab2:
    if st.session_state.history.empty:
        st.info("尚無雲端數據。")
    else:
        df = st.session_state.history.copy()
        
        total_h = df['Duration'].sum() / 60
        m1, m2, m3 = st.columns(3)
        m1.metric("總時數", f"{total_h:.1f} h")
        m2.metric("平均 SPS", f"{df['SPS'].mean():.1f}")
        m3.metric("最高 BPM", f"{df['BPM'].max()}")
        
        st.markdown("---")
        st.markdown("#### 📈 成長趨勢")
        st.line_chart(df.set_index('Date')['SPS'])
        
        st.markdown("#### 📋 歷史記錄")
        disp = df.sort_values('Date', ascending=False)
        disp['Date'] = disp['Date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(disp[['Date', 'BPM', 'Note_Type', 'Duration', 'Focus']], use_container_width=True, hide_index=True)
