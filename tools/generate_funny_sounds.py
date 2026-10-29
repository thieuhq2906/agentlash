import os
import math
import struct
import wave
import numpy as np

SAMPLE_RATE = 44100

def write_wav(filename, samples, sample_rate=SAMPLE_RATE):
    """Ghi mảng numpy float (-1.0 đến 1.0) ra file WAV 16-bit stereo"""
    samples = np.clip(samples, -1.0, 1.0)
    int_samples = (samples * 32767).astype(np.int16)
    
    # Chuyển mono thành stereo nếu cần
    if int_samples.ndim == 1:
        int_samples = np.column_stack((int_samples, int_samples))
        
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_samples.tobytes())
    print(f"-> Created audio file: {filename}")

def generate_comic_sound():
    """1. Comic: Boinggg lò xo hoạt hình + CỘC gõ mỏ hoạt hình"""
    dur = 0.65
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    
    # Tiếng CỘC gõ mỏ lúc đầu (0 - 0.2s)
    wood_t = t[:int(SAMPLE_RATE * 0.22)]
    wood = (np.sin(2 * np.pi * 750 * wood_t) * 0.6 + 
            np.sin(2 * np.pi * 1480 * wood_t) * 0.3 + 
            np.sin(2 * np.pi * 2200 * wood_t) * 0.1) * np.exp(-wood_t * 28.0)
    
    # Tiếng Boinggg lò xo bật nảy (0.05 - 0.65s)
    spring_t = t - 0.05
    spring_mask = spring_t > 0
    st = spring_t[spring_mask]
    
    # Tần số quét từ 220Hz vọt lên 520Hz rồi rung dao động
    f_sweep = 220 + 300 * (1 - np.exp(-st * 12.0)) + np.sin(2 * np.pi * 18 * st) * 35
    phase = 2 * np.pi * np.cumsum(f_sweep) / SAMPLE_RATE
    spring = np.sin(phase) * np.exp(-st * 4.5) * 0.75
    
    out = np.zeros_like(t)
    out[:len(wood)] += wood * 0.8
    out[spring_mask] += spring
    
    # Thêm tiếng pop bụp lúc đầu
    pop = np.sin(2 * np.pi * 120 * t[:int(SAMPLE_RATE * 0.04)]) * np.exp(-t[:int(SAMPLE_RATE * 0.04)] * 60)
    out[:len(pop)] += pop * 0.5
    
    return out

def generate_cyber_sound():
    """2. Cyberpunk: Tiếng tạch tạch USB Windows cắm rút + glitch modem + laser"""
    dur = 0.70
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    out = np.zeros_like(t)
    
    # Âm báo USB Windows chime (2 nốt: nốt 1 vút lên nốt 2)
    # Nốt 1 (0.00 - 0.09s): E5 (659Hz)
    t1 = t[:int(SAMPLE_RATE * 0.09)]
    chime1 = np.sin(2 * np.pi * 659.25 * t1) * np.exp(-t1 * 15) * 0.6
    out[:len(t1)] += chime1
    
    # Nốt 2 (0.09 - 0.25s): B5 (987Hz)
    t2_idx = int(SAMPLE_RATE * 0.09)
    t2 = t[t2_idx:int(SAMPLE_RATE * 0.28)] - 0.09
    chime2 = np.sin(2 * np.pi * 987.77 * t2) * np.exp(-t2 * 14) * 0.65
    out[t2_idx:t2_idx + len(t2)] += chime2
    
    # Digital glitch laser sweep (0.15 - 0.55s)
    glitch_idx = int(SAMPLE_RATE * 0.14)
    gt = t[glitch_idx:] - 0.14
    f_laser = 2400 * np.exp(-gt * 10) + 180 * np.sin(2 * np.pi * 60 * gt)
    phase = 2 * np.pi * np.cumsum(f_laser) / SAMPLE_RATE
    # Bitcrushed wave
    laser = np.sin(phase)
    laser = np.round(laser * 4.0) / 4.0 * np.exp(-gt * 6.0) * 0.5
    
    # White noise glitch bursts
    noise = np.random.uniform(-1, 1, len(gt)) * np.exp(-gt * 15.0) * 0.25
    out[glitch_idx:] += (laser + noise)
    
    return out

def generate_classic_sound():
    """3. Classic Western: Huýt sáo viễn tây + quất da bò + Yee-Haw"""
    dur = 0.85
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    out = np.zeros_like(t)
    
    # Tiếng quất roi da đanh thép mở màn (0 - 0.15s)
    crack_len = int(SAMPLE_RATE * 0.12)
    ct = t[:crack_len]
    crack = np.random.uniform(-1, 1, crack_len) * np.exp(-ct * 50) * 0.9
    out[:crack_len] += crack
    
    # Tiếng huýt sáo miền viễn Tây trượt cao độ (0.08 - 0.80s)
    wt_idx = int(SAMPLE_RATE * 0.08)
    wt = t[wt_idx:int(SAMPLE_RATE * 0.80)] - 0.08
    # Cao độ huýt sáo: 1300Hz trượt lên 1750Hz rồi xuống 1400Hz (vibrato nhẹ)
    f_whistle = 1300 + 450 * np.sin(np.pi * wt / wt[-1]) + np.sin(2 * np.pi * 6.5 * wt) * 35
    phase = 2 * np.pi * np.cumsum(f_whistle) / SAMPLE_RATE
    whistle_env = np.maximum(0, np.sin(np.pi * wt / wt[-1])) ** 1.5
    whistle = np.sin(phase) * whistle_env * 0.7
    out[wt_idx:wt_idx + len(wt)] += whistle
    
    return out

def generate_taser_sound():
    """4. Kìm điện Cam-pu-chia: Hồ quang điện cao thế BZZZT + Tom Scream"""
    # Nạp tom_scream nếu có
    tom_path = "assets/sounds/tom_scream.wav"
    tom_data = None
    if os.path.exists(tom_path):
        with wave.open(tom_path, 'rb') as wf:
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)
            tom_arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
            if wf.getnchannels() == 2:
                tom_arr = (tom_arr[0::2] + tom_arr[1::2]) * 0.5
            # Lấy 1.1 giây tiếng hét đỉnh cao nhất
            tom_data = tom_arr[:int(SAMPLE_RATE * 1.1)]

    dur = 1.35
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    out = np.zeros_like(t)
    
    # Tiếng giật điện taser 100Hz + tia lửa nổ bôm bốp (0.00 - 0.90s)
    t_zap = t[:int(SAMPLE_RATE * 0.90)]
    buzz = (np.sin(2 * np.pi * 120 * t_zap) * 0.4 +
            np.sin(2 * np.pi * 240 * t_zap) * 0.3 +
            np.sin(2 * np.pi * 600 * t_zap) * 0.2)
    # Thêm xung hồ quang điện
    sparks = np.random.uniform(-1, 1, len(t_zap)) * (np.random.rand(len(t_zap)) > 0.92).astype(float) * 0.9
    zap = (buzz + sparks) * np.exp(-t_zap * 2.2) * 0.7
    out[:len(t_zap)] += zap
    
    # Ghép Tom Scream vào từ thời điểm 0.15s
    if tom_data is not None:
        idx_tom = int(SAMPLE_RATE * 0.12)
        end_tom = min(len(out), idx_tom + len(tom_data))
        out[idx_tom:end_tom] += tom_data[:end_tom - idx_tom] * 0.85

    return out

def generate_sword_sound():
    """5. Thanh kiếm TRẢM: Giọng nam trầm đục uy lực 'TRẢM!' + vung kiếm kim loại rợn người"""
    dur = 1.25
    t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False)
    out = np.zeros_like(t)
    
    # Tiếng vung kiếm xé gió (Metallic Whoosh: 0.00 - 0.35s)
    wt = t[:int(SAMPLE_RATE * 0.35)]
    f_whoosh = 3200 * np.exp(-wt * 9) + 400
    phase_w = 2 * np.pi * np.cumsum(f_whoosh) / SAMPLE_RATE
    whoosh = (np.sin(phase_w) * 0.4 + np.random.uniform(-1, 1, len(wt)) * 0.4) * np.sin(np.pi * wt / wt[-1])
    out[:len(wt)] += whoosh * 0.7
    
    # Tổng hợp thanh âm giọng nam trầm đục 'TRẢM!' (0.15 - 0.85s)
    # F0 cơ bản = 85Hz rơi xuống 70Hz (giọng nam trầm nghiêm nghị, dứt khoát)
    vt_idx = int(SAMPLE_RATE * 0.16)
    vt = t[vt_idx:int(SAMPLE_RATE * 0.82)] - 0.16
    f0 = 92 - 25 * (vt / vt[-1]) ** 1.2
    phase_v = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE
    
    # Formants cho âm 'A' và kết thúc mũi 'M':
    # F1 ~ 680Hz, F2 ~ 1150Hz, F3 ~ 2400Hz
    vocal_glottal = (np.sin(phase_v) + 0.6 * np.sin(2 * phase_v) + 0.4 * np.sin(3 * phase_v) + 
                     0.25 * np.sin(4 * phase_v) + 0.15 * np.sin(5 * phase_v))
    formant1 = np.sin(2 * np.pi * 680 * vt) * 0.5
    formant2 = np.sin(2 * np.pi * 1150 * vt) * 0.35
    formant3 = np.sin(2 * np.pi * 2400 * vt) * 0.2
    
    v_env = (np.sin(np.pi * (vt / vt[-1]) ** 0.6)) * np.exp(-vt * 1.8)
    tram_voice = vocal_glottal * (1.0 + formant1 + formant2 + formant3) * v_env * 0.85
    out[vt_idx:vt_idx + len(vt)] += tram_voice
    
    # Tiếng thép va chạm sắc lạnh (Steel Clang: 0.22 - 0.70s)
    st_idx = int(SAMPLE_RATE * 0.22)
    st = t[st_idx:int(SAMPLE_RATE * 0.75)] - 0.22
    steel = (np.sin(2 * np.pi * 2850 * st) * 0.4 + 
             np.sin(2 * np.pi * 4200 * st) * 0.3 + 
             np.sin(2 * np.pi * 6100 * st) * 0.2) * np.exp(-st * 9)
    out[st_idx:st_idx + len(st)] += steel * 0.75
    
    return out

if __name__ == "__main__":
    sounds_dir = os.path.join("assets", "sounds")
    os.makedirs(sounds_dir, exist_ok=True)
    
    write_wav(os.path.join(sounds_dir, "whip_comic.wav"), generate_comic_sound())
    write_wav(os.path.join(sounds_dir, "whip_cyber.wav"), generate_cyber_sound())
    write_wav(os.path.join(sounds_dir, "whip_classic.wav"), generate_classic_sound())
    write_wav(os.path.join(sounds_dir, "whip_taser.wav"), generate_taser_sound())
    write_wav(os.path.join(sounds_dir, "whip_sword.wav"), generate_sword_sound())
    print("Completed generating audio files!")
