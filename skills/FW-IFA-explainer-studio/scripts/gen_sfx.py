# -*- coding: utf-8 -*-
"""五套风格各自的音效（程序合成，没有版权问题，可以随技能分发）。一般不用重跑，assets/sfx 里已经有成品。
用法：python3 gen_sfx.py [输出目录]      依赖 numpy 和 ffmpeg（转 mp3）
每套 6 个：soft 段落过渡、snap 点亮／轻点、swoosh 短滑入、whoosh 长滑入、impact 重音、click 卡片／更新卡
  炭金：暖色电影感——气流、低频闷击
  档案：纸张滑动、橡皮章、打字机
  矿石：金属撞击、石头摩擦、低频轰鸣
  瓷蓝：瓷器轻鸣、柔和的气流和弹出
  霓虹：合成器上扬、数字提示音、激光下滑
"""
import os, subprocess, sys, tempfile, wave
import numpy as np

SR = 48000
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sfx")
rng = np.random.default_rng(20261121)
TARGET_RMS = {"snap": -19, "click": -20, "swoosh": -21, "whoosh": -19, "soft": -25, "impact": -15}


def t_(dur):
    return np.arange(int(SR * dur)) / SR


def adsr(n, a=0.005, d=0.3, curve=4.0):
    """起音 a 秒线性上升，之后按指数衰减。"""
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4))
    return e * np.exp(-np.maximum(0, t - a) * curve / max(d, 1e-4))


def swell(n, peak=0.5, power=2.0):
    """先升后降的包络，peak 是峰值位置（0–1）。"""
    x = np.linspace(0, 1, n)
    up = (x / peak) ** power
    down = ((1 - x) / (1 - peak)) ** power
    return np.where(x < peak, up, down)


def sine(f, dur, phase=0.0):
    t = t_(dur)
    f = np.broadcast_to(np.asarray(f, dtype=float), t.shape) if np.ndim(f) else np.full(t.shape, float(f))
    return np.sin(2 * np.pi * np.cumsum(f) / SR + phase)


def noise(dur):
    return rng.standard_normal(int(SR * dur))


def band(x, lo, hi, soft=0.15):
    """频域带通（软边）。"""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + np.exp(-(f - lo) / (lo * soft + 1))) * 1 / (1 + np.exp((f - hi) / (hi * soft + 1)))
    return np.fft.irfft(X * m, len(x))


def sweep(dur, f0, f1, bw_oct=1.0, curve=1.0, src=None):
    """随时间移动的带通噪声（气流、滑动声）：短时傅里叶逐帧换中心频率。"""
    x = noise(dur) if src is None else src
    n, win, hop = len(x), 1024, 256
    w = np.hanning(win)
    out = np.zeros(n + win)
    norm = np.zeros(n + win)
    freqs = np.fft.rfftfreq(win, 1 / SR)
    lf = np.log2(np.maximum(freqs, 1))
    for i in range(0, n, hop):
        seg = np.zeros(win)
        chunk = x[i:i + win]
        seg[:len(chunk)] = chunk
        p = min(1.0, i / max(1, n - 1)) ** curve
        fc = f0 * (f1 / f0) ** p
        m = np.exp(-0.5 * ((lf - np.log2(fc)) / (bw_oct / 2)) ** 2)
        y = np.fft.irfft(np.fft.rfft(seg * w) * m, win)
        out[i:i + win] += y * w
        norm[i:i + win] += w ** 2
    return (out / np.maximum(norm, 1e-6))[:n]


def bell(f, dur, ratio=3.5, index=2.0, decay=4.0):
    """调频钟声（瓷器、金属）。"""
    t = t_(dur)
    env = np.exp(-t * decay)
    mod = index * env * np.sin(2 * np.pi * f * ratio * t)
    return np.sin(2 * np.pi * f * t + mod) * env


def partials(fs, dur, decays, amps=None):
    t = t_(dur)
    amps = amps or [1.0] * len(fs)
    return sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) * np.exp(-t * d) for f, d, a in zip(fs, decays, amps))


def saw(f, dur, harm=24):
    t = t_(dur)
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(np.asarray(f, float), t.shape)) / SR
    return sum(np.sin(k * ph) / k for k in range(1, harm + 1))


def reverb(x, tail=0.8, mix=0.25, bright=6000):
    """指数衰减噪声当冲激响应，做一点空间感。干声结尾先淡出，免得硬切出「咔」声。"""
    x = np.array(x, dtype=float)
    f = max(8, min(len(x) // 4, int(SR * 0.015)))
    x[-f:] *= np.linspace(1, 0, f)
    ir = noise(tail) * np.exp(-t_(tail) * 6.0 / tail)
    ir = band(ir, 120, bright)
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    n = len(x) + len(ir)
    wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)
    dry = np.concatenate([x, np.zeros(len(ir))])
    return dry * (1 - mix) + wet * mix


def crush(x, bits=6):
    q = 2 ** bits
    return np.round(x * q) / q


def pad(x, pre=0.0):
    return np.concatenate([np.zeros(int(SR * pre)), x])


def mix(*parts):
    """叠加长短不一的声音，每段结尾先短淡出。"""
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        p = np.array(p, dtype=float)
        f = max(4, min(len(p) // 4, int(SR * 0.008)))
        p[-f:] *= np.linspace(1, 0, f)
        out[:len(p)] += p
    return out


# ---------------------------------------------------------------- 五套配方
def tanjin():
    return {
        "whoosh": reverb(sweep(0.75, 220, 2600, 1.2) * swell(int(SR * 0.75), 0.55), 0.7, 0.2),
        "swoosh": sweep(0.38, 600, 4200, 1.0) * swell(int(SR * 0.38), 0.45),
        "soft": reverb(band(noise(0.9), 1800, 7000) * swell(int(SR * 0.9), 0.6, 1.5) * 0.6 + sine(70, 0.9) * swell(int(SR * 0.9), 0.5) * 0.4, 0.9, 0.3),
        "snap": reverb(mix(band(noise(0.01), 2000, 6000) * 0.8, sine(2200, 0.12) * adsr(int(SR * 0.12), 0.001, 0.05)), 0.4, 0.15),
        "impact": reverb(mix(sine(np.linspace(72, 44, int(SR * 0.9)), 0.9) * adsr(int(SR * 0.9), 0.003, 0.6, 3.5),
                             band(noise(0.08), 30, 500) * adsr(int(SR * 0.08), 0.001, 0.05)), 1.2, 0.25, 4000),
        "click": mix(band(noise(0.006), 1500, 7000), pad(band(noise(0.006), 1500, 7000) * 0.7, 0.045)),
    }


def dangan():
    flutter = lambda d: 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * rng.uniform(28, 44) * t_(d) + rng.uniform(0, 3)))
    return {
        "swoosh": band(noise(0.42), 1500, 6500) * swell(int(SR * 0.42), 0.4) * flutter(0.42),
        "whoosh": reverb(sweep(0.62, 700, 5200, 1.4) * swell(int(SR * 0.62), 0.5) * flutter(0.62)
                         + band(noise(0.62), 3000, 9000) * (rng.random(int(SR * 0.62)) > 0.995) * 3, 0.5, 0.15),
        "soft": band(noise(0.55), 200, 2200) * swell(int(SR * 0.55), 0.35, 1.5) * 0.7,
        "snap": mix(band(noise(0.012), 600, 9000), band(noise(0.04), 2000, 4500) * adsr(int(SR * 0.04), 0.001, 0.02)),
        "impact": reverb(mix(sine(92, 0.16) * adsr(int(SR * 0.16), 0.002, 0.08),
                             partials([182, 412, 690], 0.12, [40, 60, 90], [0.7, 0.5, 0.3]),
                             band(noise(0.025), 300, 5000) * 0.8), 0.35, 0.18, 3500),
        "click": mix(band(noise(0.003), 2000, 12000), bell(3500, 0.06, 1.4, 0.6, 50) * 0.35,
                     sine(140, 0.05) * adsr(int(SR * 0.05), 0.001, 0.02) * 0.6),
    }


def kuangshi():
    return {
        "impact": reverb(mix(partials([110, 287, 451, 733, 1180, 1710], 1.6, [2.0, 2.6, 3.2, 4.5, 6, 8], [0.9, 0.7, 0.55, 0.4, 0.3, 0.2]),
                             sine(np.linspace(60, 38, int(SR * 1.0)), 1.0) * adsr(int(SR * 1.0), 0.003, 0.7, 3.0) * 0.9,
                             band(noise(0.05), 200, 5000) * 0.7), 1.6, 0.25, 5000),
        "snap": reverb(mix(partials([2400, 3920, 6100], 0.18, [28, 36, 50], [0.8, 0.6, 0.4]), band(noise(0.004), 3000, 9000) * 0.5), 0.4, 0.15),
        "whoosh": reverb(sweep(0.82, 80, 1300, 1.5) * swell(int(SR * 0.82), 0.6)
                         + band(noise(0.82), 900, 3500) * (rng.random(int(SR * 0.82)) > 0.993) * 2.5 * swell(int(SR * 0.82), 0.6), 0.8, 0.22, 3000),
        "swoosh": band(noise(0.42), 400, 2600) * swell(int(SR * 0.42), 0.45) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 55 * t_(0.42)))),
        "soft": reverb(mix(sine(55, 1.0) * 0.6, sine(110, 1.0) * 0.3, band(noise(1.0), 100, 900) * 0.3) * swell(int(SR * 1.0), 0.55, 1.6), 1.0, 0.3, 2500),
        "click": mix(band(noise(0.008), 1400, 3200), pad(band(noise(0.006), 1600, 3400) * 0.6, 0.03)),
    }


def cilan():
    return {
        "snap": reverb(mix(bell(1760, 0.45, 3.5, 2.0, 7.0), band(noise(0.003), 4000, 12000) * 0.3), 0.6, 0.25, 9000),
        "impact": reverb(mix(sine(np.linspace(160, 90, int(SR * 0.12)), 0.12) * adsr(int(SR * 0.12), 0.002, 0.06),
                             bell(880, 1.2, 2.0, 1.4, 3.2) * 0.7, bell(1320, 1.0, 3.0, 1.0, 4.0) * 0.35), 1.0, 0.3, 9000),
        "whoosh": reverb(sweep(0.7, 1000, 8500, 0.9) * swell(int(SR * 0.7), 0.5), 0.6, 0.25, 10000),
        "swoosh": sweep(0.36, 1800, 9000, 0.8) * swell(int(SR * 0.36), 0.45),
        "soft": reverb(mix(*[pad(bell(f, 0.9, 2.0, 0.6, 3.0) * 0.4, d) for f, d in ((2637, 0), (3322, 0.08), (4186, 0.16))]) * 0.7, 1.2, 0.45, 10000),
        "click": mix(sine(1200, 0.018) * adsr(int(SR * 0.018), 0.001, 0.008), band(noise(0.002), 4000, 10000) * 0.3),
    }


def nihong():
    riser_f = 110 * (4 ** np.linspace(0, 1, int(SR * 0.72)) ** 1.5)
    return {
        "whoosh": reverb(sweep(0.72, 300, 6000, 0.7, 1.4, src=saw(riser_f, 0.72) + noise(0.72) * 0.2) * swell(int(SR * 0.72), 0.8, 1.4), 0.6, 0.2),
        "swoosh": sine(3000 * (200 / 3000) ** np.linspace(0, 1, int(SR * 0.26)), 0.26) * adsr(int(SR * 0.26), 0.003, 0.2, 2.5)
                  + crush(np.sign(sine(1500 * (200 / 1500) ** np.linspace(0, 1, int(SR * 0.26)), 0.26)), 3) * 0.15 * adsr(int(SR * 0.26), 0.003, 0.15),
        "snap": crush(np.sign(sine(np.linspace(1400, 900, int(SR * 0.05)), 0.05)) * adsr(int(SR * 0.05), 0.001, 0.03), 4) * 0.7,
        "impact": reverb(mix(sine(80 * (35 / 80) ** np.linspace(0, 1, int(SR * 0.7)), 0.7) * adsr(int(SR * 0.7), 0.003, 0.5, 2.5),
                             crush(band(noise(0.12), 200, 6000) * adsr(int(SR * 0.12), 0.001, 0.06), 4) * 0.6), 0.9, 0.2, 7000),
        "soft": band(mix(saw(220, 0.95, 12), saw(221.6, 0.95, 12), saw(330, 0.95, 10) * 0.6), 150, 2500) * swell(int(SR * 0.95), 0.6, 1.6) * 0.35,
        "click": mix(crush(band(noise(0.03), 800, 9000) * adsr(int(SR * 0.03), 0.001, 0.01), 3), sine(3000, 0.03) * adsr(int(SR * 0.03), 0.001, 0.01) * 0.4),
    }


def finish(x, kind):
    x = np.asarray(x, dtype=float)
    x = x - np.mean(x)
    n = len(x)
    fade = min(int(SR * 0.004), n // 4)
    x[:fade] *= np.linspace(0, 1, fade)
    tail = min(int(SR * 0.03), n // 3)
    x[-tail:] *= np.linspace(1, 0, tail)
    act = x[np.abs(x) > np.max(np.abs(x)) * 0.05]
    rms = np.sqrt(np.mean(act ** 2)) + 1e-9
    x *= 10 ** (TARGET_RMS[kind] / 20) / rms
    peak = np.max(np.abs(x))
    if peak > 0.89:
        x *= 0.89 / peak
    return x


def write_mp3(x, path):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-c:a", "libmp3lame", "-b:a", "160k", path], check=True)
    os.unlink(tmp)


if __name__ == "__main__":
    for name, fn in (("tanjin", tanjin), ("dangan", dangan), ("kuangshi", kuangshi), ("cilan", cilan), ("nihong", nihong)):
        d = os.path.join(OUT, name)
        os.makedirs(d, exist_ok=True)
        for kind, x in fn().items():
            write_mp3(finish(x, kind), os.path.join(d, f"{kind}.mp3"))
        print(name, "ok")
