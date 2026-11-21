# -*- coding: utf-8 -*-
"""剪辑表：从转写自动出 edl.json（原片里要保留的时间段），同时找重说和改口，只留最后一遍。

用法：
  python3 scripts/edl.py --transcript transcript.json --src 原片.mp4 --work 工作目录 [--fix fix.json]
  python3 scripts/edl.py --scan 音频或视频        只查还有没有重说（交付前查剪好的人声），有就退出码 1
产物：工作目录/edl.json（给 prep.py cut）、edl_joins.json（每个接点是停顿还是重说）、
      transcript_edl.json（给 prep.py captions）、edl_report.json（剪了什么、待听清单、接点检查）。约 20 秒。

为什么不按整段转写找重说：转写模型会把「说一半停住、再从头说」合成一句，只写最后那遍，文字上看不出来。
所以按停顿把声音切成一个个发声段，每段单独转写（要 whisper-cli），再比相邻两段的文字：
  改口      后一段和前一段开头相同（≥3 字；前一段不到 1 秒时 2 字也算），前一段只多出 1–2 个字，
            后一段比前一段长 → 前一段是没说完的那遍。例：「这笔钱放在房」→「这笔钱放在存款里」
            前一段整段（≥6 字）在后一段开头又说了一遍、只差一两个转写错字，也算。
  尾头重复  前一段结尾 n 字和后一段开头 n 字相同（n≥3；n≥6 时允许 1–2 个转写错字）→ 前一段结尾这 n 字是第一遍。
            例：「先看利率，再看期限」→「再看期限和条件」
  中间夹着不到 0.5 秒的杂音段，跳过它再比。
  命中就剪，只留最后一遍；只靠 2 个字或 3 个字判定的，剪了也列进待听清单。
  另外查整句重说：和后面 3 句里的某一句文字很像（>0.70）就删前一句。
  比的是读音（逐字换成不带声调的拼音，data/pinyin.txt）：转写常把同一个音写成不同的字（他／它、堵／赌），比字形会漏。
  比文字一律用转写原文，不用 fix.json 改过的字：改过字幕再比，重复就看不见了。
  没装 whisper-cli 时退回声音信号（语速明显偏慢＋同一段声音出现两次），准确率低，交付时要人听。
怎么剪：
  从开口剪到开口：剪点一头落在放弃那遍开口前的停顿里，另一头落在最后一遍开口前的停顿里，不碰任何一个字。
  句尾按声音找真正说完的地方（转写给的句尾常早 0.1–0.4 秒），说完后至少留 0.10 秒，不往回收。
  句间停顿 ≤0.42 秒不动，更长的压到约 0.26 秒（说完留 0.14，下一句开口前留 0.12）。剪完短于 0.3 秒的碎段丢掉。
人听出来、自动没找到的：在 fix.json 里写 "cut": [[原片起, 原片止]]（recut.py --where 成片秒数 能换算），重跑也保留。
复核：每处重说剪完，把接起来的那几秒拼出来再转写一次，确认重复的话只剩一遍。
接点检查：每个接点两头都要落在停顿里（没切到字），停顿 0.12–0.5 秒。
原则（借 ChatCut 口播指南）：只留一遍完整的，不把几遍的碎片拼成一句；第一遍里后面没再说的铺垫要留。
"""
import argparse, difflib, json, os, re, shutil, subprocess, sys, tempfile, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAP_MAX = 0.42               # 句间停顿超过它才压
TAIL, HEAD = 0.14, 0.12      # 压停顿：说完后留多久、下一句开口前留多久
FIRST_HEAD, LAST_TAIL = 0.12, 0.40
MIN_PIECE = 0.30             # 剪完短于它的碎段丢掉
HALLU = re.compile(r"字幕|订阅|訂閱|谢谢观看|謝謝觀看|点赞|點贊|明镜|明鏡|Amara|by ", re.I)
PROMPT = "以下是普通话的句子，使用简体中文。"

_T2S = {}


def t2s(s):
    """繁体转简体（逐字）：转写常出繁体，比文字前统一转掉。字表 data/t2s.txt 由系统的 Hant-Hans 转换生成。"""
    if not _T2S:
        try:
            for p in open(os.path.join(ROOT, "data", "t2s.txt"), encoding="utf-8").read().split():
                if len(p) == 2:
                    _T2S[p[0]] = p[1]
        except OSError:
            _T2S["\0"] = "\0"
    return "".join(_T2S.get(c, c) for c in s)


def norm(s):
    return re.sub(r"[\W_]", "", t2s(s)).lower()


_PY = {}


def key(s):
    """逐字换成不带声调的拼音，比文字用：转写的同音错字（他／它、堵／赌）算同一个字。字表 data/pinyin.txt 由系统的汉字转拼音生成。"""
    if not _PY:
        try:
            for p in open(os.path.join(ROOT, "data", "pinyin.txt"), encoding="utf-8").read().split():
                _PY[p[0]] = p[1:]
        except OSError:
            _PY["\0"] = "\0"
    return tuple(_PY.get(c, c) for c in norm(s))


def tol(n):
    """n 个字里允许几个转写错字（拼音也不同的那种，比如「份」和「反」）。"""
    return 0 if n <= 5 else (1 if n <= 7 else 2)


def load_audio(src):
    tmp = tempfile.mkdtemp(prefix="edl_")
    wav = os.path.join(tmp, "a16.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return x, 16000, tmp, wav


def features(x, sr):
    """每 10 毫秒一帧：L 频谱形状（比声音像不像用），en 人声频段能量（dB）。"""
    hop, n = sr // 100, 512
    fr = np.lib.stride_tricks.sliding_window_view(np.pad(x, (n // 2, n // 2)), n)[::hop] * np.hanning(n)
    sp = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / sr)
    edges = np.geomspace(150, 5000, 25)
    B = np.stack([sp[:, (f >= edges[i]) & (f < edges[i + 1])].sum(1) for i in range(24)], 1)
    L = np.log(B + 1e-8)
    L -= L.mean(1, keepdims=True)
    L /= np.linalg.norm(L, axis=1, keepdims=True) + 1e-9
    en = 10 * np.log10(sp[:, (f > 250) & (f < 3500)].sum(1) + 1e-9)
    en = np.convolve(en, np.ones(5) / 5, "same")
    return L, en


# ---------------------------------------------------------------- 发声段
def levels(en):
    """两条门限：hi 切发声段用（稳），lo 找真正开口和说完用（轻声收尾、擦音也算有声）。"""
    floor, peak = float(np.percentile(en, 10)), float(np.percentile(en, 95))
    return floor + 0.45 * (peak - floor), floor + 0.2 * (peak - floor)


def islands(en, hi, lo):
    """发声段：高于 hi 的帧，缝 <0.2 秒并起来，短于 0.12 秒的丢掉；再用 lo 往外扩到真正开口和说完
    （往前最多 0.6 秒、往后最多 0.5 秒，不越过相邻段）。"""
    v = np.concatenate([[0], (en > hi).astype(int), [0]])
    d = np.diff(v)
    m = []
    for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
        if m and a - m[-1][1] < 20:
            m[-1][1] = int(b)
        else:
            m.append([int(a), int(b)])
    m = [[a, b] for a, b in m if b - a >= 12]
    def grow(i, step, stop):
        """从 i 往 step 方向扩：高于 lo 的帧都算；遇到不到 0.12 秒的低谷，后面还有 ≥0.1 秒高于 lo 的，就跨过去（轻声的字）。"""
        edge = i
        while 0 <= i + step < len(en) and (i + step - stop) * step <= 0:
            if en[i + step] > lo:
                i += step; edge = i
                continue
            k, dip = i + step, 0
            while 0 <= k < len(en) and (k - stop) * step <= 0 and en[k] <= lo and dip < 12:
                k += step; dip += 1
            r, run = k, 0
            while 0 <= r < len(en) and (r - stop) * step <= 0 and en[r] > lo:
                r += step; run += 1
            if dip < 12 and run >= 10:
                i = r - step; edge = i
                continue
            break
        return edge

    out = []
    for k, (a, b) in enumerate(m):
        lo_a = max(m[k - 1][1] + 2 if k else 0, a - 60)
        hi_b = min(m[k + 1][0] - 2 if k + 1 < len(m) else len(en) - 1, b + 50)
        a2 = grow(a, -1, lo_a)
        b2 = grow(b - 1, 1, hi_b) + 1
        out.append({"a": a2 / 100, "b": b2 / 100})
    return out


def quiet(en, t0, t1):
    """[t0, t1] 里能量最低的那一帧。"""
    a = max(0, int(round(t0 * 100)))
    b = max(a + 1, int(round(t1 * 100)))
    seg = en[a:b]
    return (a + int(seg.argmin())) / 100 if len(seg) else t0


def speech_bounds(en, lo, isl, a, b):
    """[a, b] 里第一帧和最后一帧在说话的位置（在发声段里、且高于 lo；底噪和换气不算），再加说话的总时长。"""
    first, last, tot = None, None, 0
    for s in isl:
        i0, i1 = int(round(max(a, s["a"]) * 100)), int(round(min(b, s["b"]) * 100))
        if i1 <= i0:
            continue
        w = np.where(en[i0:i1] > lo)[0]
        if len(w):
            first = i0 + int(w[0]) if first is None else first
            last = i0 + int(w[-1]) + 1
            tot += len(w)
    return None if first is None else (first / 100, last / 100, tot / 100)


def in_speech(en, lo, isl, t):
    """t 这一刻是不是在说话：落在发声段里，且前后 20 毫秒有声。"""
    i = int(round(t * 100))
    return any(s["a"] + 0.02 < t < s["b"] - 0.02 for s in isl) and float(en[max(0, i - 2):i + 2].max()) > lo


# ---------------------------------------------------------------- 转写
def whisper_bin():
    for n in ("whisper-cli", "whisper-cli.exe"):
        p = shutil.which(n)
        if p:
            return p
    for n in ("whisper-cli", "whisper-cli.exe"):  # IFA口播成片 的 setup.py 在 Windows 上把工具放这里
        p = os.path.join(os.path.expanduser("~"), ".cache", "ifa-koubo", "bin", n)
        if os.path.exists(p):
            return p
    return None


def whisper_model():
    env = os.environ.get("WHISPER_MODEL")
    if env:
        p = os.path.expanduser(env)
        return p if os.path.exists(p) else None
    d = os.path.join(os.path.expanduser("~"), ".cache", "whisper-cpp")
    for n in ("ggml-small.bin", "ggml-small-q5_1.bin"):
        if os.path.exists(os.path.join(d, n)):
            return os.path.join(d, n)
    if os.path.isdir(d):
        c = sorted(f for f in os.listdir(d) if f.startswith("ggml-") and f.endswith(".bin") and "vad" not in f and "silero" not in f)
        if c:
            return os.path.join(d, c[0])
    return None


def asr(x, sr, items, tmp, wbin, model):
    """items：每项是一串原片时间段，拼起来转写一次（前后垫静音）。返回 [(文字, [(字, 原片秒), ...])]。
    字的秒数只对单段的项有意义（发声段转写用）。"""
    files = []
    for k, spans in enumerate(items):
        parts = [np.zeros(int(0.2 * sr), np.float32)]
        for a, b in spans:
            parts.append(x[max(0, int(a * sr)):min(len(x), int(b * sr))])
        parts.append(np.zeros(int(0.3 * sr), np.float32))
        y = (np.concatenate(parts) * 32767).clip(-32768, 32767).astype(np.int16)
        f = os.path.join(tmp, f"asr{k:04d}.wav")
        w = wave.open(f, "wb")
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(y.tobytes()); w.close()
        files.append(f)
    th = str(max(1, min(8, os.cpu_count() or 4)))
    for i in range(0, len(files), 60):
        cmd = [wbin, "-m", model, "-l", "zh", "-mc", "0", "-ojf", "-np", "-sns", "-t", th, "--prompt", PROMPT]
        for f in files[i:i + 60]:
            cmd += ["-f", f]
        subprocess.run(cmd, capture_output=True)
    out = []
    for k, f in enumerate(files):
        try:
            d = json.load(open(f + ".json", encoding="utf-8", errors="replace"))
        except (OSError, ValueError):
            d = {}
        text, chars = "", []
        t0 = items[k][0][0]
        for seg in d.get("transcription", []):
            text += seg.get("text", "")
            for tk in seg.get("tokens", []):
                tt = tk.get("text", "")
                if tt.startswith("[_"):
                    continue
                cs = norm(tt)
                f0 = tk["offsets"]["from"] / 1000 - 0.2
                f1 = max(f0, tk["offsets"]["to"] / 1000 - 0.2)
                for j, c in enumerate(cs):
                    chars.append((c, round(t0 + f0 + (f1 - f0) * j / max(1, len(cs)), 3)))
        out.append((text.strip(), chars))
    return out


def transcribe_islands(x, sr, isl, tmp, wbin, model):
    res = asr(x, sr, [[(max(0.0, s["a"] - 0.12), s["b"] + 0.15)] for s in isl], tmp, wbin, model)
    for s, (text, chars) in zip(isl, res):
        n = norm(text)
        d = s["b"] - s["a"]
        if HALLU.search(text) or (n and len(n) / max(d, 0.2) > 12) or (n in ("谢谢", "谢谢谢谢") and d < 1.0):
            n, chars = "", []  # 转写模型在很短的段上会编话（「谢谢观看」之类），这种段不拿来比
        s["text"], s["n"], s["k"], s["chars"] = text, n, key(n), chars
    return isl


# ---------------------------------------------------------------- 找重说
def near(a, b):
    """等长两串有几个字不同。"""
    return sum(x != y for x, y in zip(a, b))


def count_near(text, pat):
    """text 里有几处（不重叠）和 pat 读音一样的字串（按 tol 允许转写错字）。"""
    text, pat = key(text), key(pat)
    t_ = tol(len(pat))
    n, i = 0, 0
    while pat and i + len(pat) <= len(text):
        if near(text[i:i + len(pat)], pat) <= t_:
            n += 1
            i += len(pat)
        else:
            i += 1
    return n


def find_retakes(isl):
    """比相邻发声段的文字。返回命中：kind、k（放弃那遍所在段）、j（最后一遍所在段）、i0（放弃部分从第几个字起）、
    same（两遍相同的字）、cut（自动剪）、listen（剪了也要人听）。"""
    hits = []
    for k, A in enumerate(isl):
        a = A.get("k") or ()
        if not a:
            continue
        for j in (k + 1, k + 2):
            if j >= len(isl):
                break
            B = isl[j]
            if B["a"] - A["b"] > 1.6:
                break
            if j == k + 2:
                M = isl[k + 1]
                if not (M["b"] - M["a"] <= 0.5 and len(M.get("n") or "") <= 2):
                    break
            b = B.get("k") or ()
            if not b:
                continue
            L = 0
            while L < min(len(a), len(b)) and a[L] == b[L]:
                L += 1
            extra = len(a) - L
            if len(a) >= 6 and len(b) > len(a) and a[:2] == b[:2] and 0 < near(a, b[:len(a)]) <= tol(len(a)):
                # 整段都重说了一遍，只是转写错了一两个字
                hits.append({"kind": "改口", "k": k, "j": j, "i0": 0, "same": A["n"], "cut": True, "listen": False})
                break
            if L >= 2 and (L >= 3 or A["b"] - A["a"] <= 1.0) and extra <= 3:
                if extra == 0 or (extra <= 2 and len(b) >= len(a) + 2):
                    hits.append({"kind": "改口", "k": k, "j": j, "i0": 0, "same": A["n"][:L], "cut": True,
                                 "listen": L < 3 or len(b) == len(a)})
                else:  # 前一段多出好几个字、两段一样长：可能是排比（「比如说房子，比如说黄金」），不剪，请人听
                    hits.append({"kind": "改口", "k": k, "j": j, "i0": 0, "same": A["n"][:L], "cut": False, "listen": True})
                break
            best = 0
            for n in range(min(len(a) - 1, len(b)), 2, -1):
                miss = near(a[-n:], b[:n])
                if miss == 0 or (n >= 6 and a[-n:][:2] == b[:2] and miss <= tol(n)):
                    best = n
                    break
            if best:
                hits.append({"kind": "尾头重复", "k": k, "j": j, "i0": len(a) - best, "same": A["n"][-best:], "cut": True,
                             "listen": best == 3})
                break
    return hits


def retake_cut(en, isl, h):
    """一处重说的剪点：从放弃那遍开口前的停顿，剪到最后一遍开口前的停顿。"""
    A, B = isl[h["k"]], isl[h["j"]]
    prev_end = isl[h["k"] - 1]["b"] if h["k"] > 0 else 0.0
    if h["i0"] == 0:
        c0 = quiet(en, max(prev_end + 0.02, A["a"] - 0.12), A["a"] - 0.02)
    else:
        ch = A.get("chars") or []
        if len(ch) == len(A["n"]):
            t = ch[h["i0"]][1]
        else:  # 字的时间对不上就按字数比例估
            t = A["a"] + (A["b"] - A["a"]) * h["i0"] / max(1, len(A["n"]))
        c0 = quiet(en, max(A["a"] + 0.05, t - 0.20), t + 0.03)
    c1 = quiet(en, max(A["b"] + 0.02, B["a"] - 0.18), max(A["b"] + 0.03, B["a"] - 0.08))
    return round(c0, 3), round(c1, 3)


# ---------------------------------------------------------------- 退路：声音信号
def selfsim(L, en, a, b, live_db):
    """一句里找「同一段声音出现两次」：返回 (相似度, 第一遍那段的起点, 第二遍对应起点, 间隔)。"""
    i0, i1 = int(a * 100), int(b * 100)
    M = L[i0:i1]
    if len(M) < 120:
        return 0.0, 0.0, 0.0, 0.0
    E = en[i0:i1] > live_db
    best = (0.0, 0.0, 0.0, 0.0)
    for lag in range(45, len(M) - 50):
        d = np.einsum("ij,ij->i", M[:-lag], M[lag:])
        live = E[:-lag] & E[lag:]
        m = np.convolve(np.where(live, d, 0), np.ones(50) / 50, "valid") / np.maximum(np.convolve(live.astype(float), np.ones(50) / 50, "valid"), 0.6)
        j = int(m.argmax())
        if m[j] > best[0]:
            best = (float(m[j]), a + j / 100, a + (j + lag) / 100, lag / 100)
    return best


def take_start(L, en, a, ta, lag, live_db):
    """沿着同一条错位往前走，找第一遍从哪开始说（相似度掉下去或到句首为止）。"""
    i, k = int(ta * 100), int(lag * 100)
    lo = int(a * 100)
    while i - 1 >= lo:
        w = slice(max(lo, i - 25), i)
        d = np.einsum("ij,ij->i", L[w], L[w.start + k:w.stop + k])
        live = en[w] > live_db
        if live.any() and float(d[live].mean()) < 0.55:
            break
        i -= 5
    return max(a, i / 100)


# ---------------------------------------------------------------- 主流程
def scan(path):
    """只查不剪：剪好的人声里还有没有重说。"""
    wbin, model = whisper_bin(), whisper_model()
    if not (wbin and model):
        print("✗ 要 whisper-cli 和模型（~/.cache/whisper-cpp/ggml-small.bin，或设环境变量 WHISPER_MODEL）")
        return 2
    x, sr, tmp, _ = load_audio(path)
    _, en = features(x, sr)
    hi, lo = levels(en)
    isl = transcribe_islands(x, sr, islands(en, hi, lo), tmp, wbin, model)
    hits = find_retakes(isl)
    shutil.rmtree(tmp, ignore_errors=True)
    for h in hits:
        A, B = isl[h["k"]], isl[h["j"]]
        tag = "要剪" if h["cut"] and not h["listen"] else "待听"
        print(f"  {tag} {A['a']:.2f}s {h['kind']}：「{A['text']}」→「{B['text']}」（重复「{h['same']}」）")
    bad = [h for h in hits if h["cut"] and not h["listen"]]
    print(("✗ 还有 %d 处重说" % len(bad)) if bad else f"✓ 没有重说（查了 {len(isl)} 个发声段" + (f"，{len(hits)} 处待听）" if hits else "）"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcript")
    ap.add_argument("--src", help="原片（视频或音频）")
    ap.add_argument("--work")
    ap.add_argument("--fix", help="fix.json：drop 里的句子不进剪辑表；改字只影响字幕，不影响找重说；剪掉的字会从改字里删掉")
    ap.add_argument("--scan", help="只查这个音频或视频里还有没有重说")
    ap.add_argument("--verify", action="store_true", help="旧参数，现在默认复核，留着兼容")
    a = ap.parse_args()
    if a.scan:
        sys.exit(scan(a.scan))
    if not (a.transcript and a.src and a.work):
        ap.error("要 --transcript、--src、--work（或只用 --scan）")
    tr = json.load(open(a.transcript, encoding="utf-8"))
    S = tr["sentences"] if isinstance(tr, dict) else tr
    fix = json.load(open(a.fix, encoding="utf-8")) if a.fix else {}
    drop = {int(x) for x in fix.get("drop", [])} | {i for i, s in enumerate(S) if s.get("drop")}
    x, sr, tmp, wav = load_audio(a.src)
    dur = len(x) / sr
    L, en = features(x, sr)
    hi, lo = levels(en)
    raw = lambda i: str(S[i].get("raw_text") or S[i]["text"])  # 找重说用转写原文
    live = [i for i in range(len(S)) if i not in drop]
    rates = [len(raw(i)) / (S[i]["end"] - S[i]["start"]) for i in live if S[i]["end"] - S[i]["start"] > 1]
    med = float(np.median(rates)) if rates else 5.0
    auto, listen, cuts = [], [], []
    # 1 发声段逐段转写，比相邻两段
    wbin, model = whisper_bin(), whisper_model()
    isl = islands(en, hi, lo)
    mode = "逐段转写" if wbin and model else "声音信号（没找到 whisper-cli 或模型，准确率低，交付前要人听）"
    covered = []
    if wbin and model:
        isl = transcribe_islands(x, sr, isl, tmp, wbin, model)
        for h in find_retakes(isl):
            A, B = isl[h["k"]], isl[h["j"]]
            item = {"类型": h["kind"], "时间": [A["a"], B["b"]], "放弃那遍": A["text"], "最后一遍": B["text"], "重复": h["same"]}
            if h["cut"]:
                c0, c1 = retake_cut(en, isl, h)
                item["剪掉"] = [c0, c1]
                item["处理"] = "剪掉放弃那遍，留最后一遍" + ("（判定只靠两三个字，请听一下）" if h["listen"] else "")
                cuts.append({"c0": c0, "c1": c1, "drop_text": A["n"][h["i0"]:], "b_on": B["a"], "b_head": B["n"][:4],
                             "same": h["same"], "item": item})
                auto.append(item)
                if h["listen"]:
                    listen.append(item)
            else:
                item["处理"] = "待听：两段开头一样，可能是排比，没剪"
                listen.append(item)
            covered.append((A["a"], B["b"]))
    else:
        live_db = float(np.median(en)) - 3
        for i in live:
            s = S[i]
            if i in drop or s["end"] - s["start"] < 1.5:
                continue
            rate = len(raw(i)) / (s["end"] - s["start"])
            sim, ta, tb, lag = selfsim(L, en, s["start"], s["end"], live_db)
            if rate < med * 0.6 and sim >= 0.80:
                c0 = take_start(L, en, s["start"], ta, lag, live_db)
                c0 = quiet(en, c0 - 0.25, c0 + 0.03)
                c1 = quiet(en, c0 + lag - 0.30, c0 + lag + 0.03)
                item = {"类型": "声音重复", "句": i, "原话": raw(i), "时间": [s["start"], s["end"]], "剪掉": [c0, c1],
                        "处理": "剪掉第一遍，留后面那遍（没有逐段转写，请听一下）"}
                cuts.append({"c0": c0, "c1": c1, "drop_text": "", "b_on": c1, "b_head": "", "same": "", "item": item})
                auto.append(item); listen.append(item)
                covered.append((s["start"], s["end"]))
    # 整句重说：和后面 3 句比（逐段转写已经解释过的不再算）
    for n_, i in enumerate(live):
        t = key(raw(i))
        if i in drop or any(c0 < S[i]["end"] and S[i]["start"] < c1 for c0, c1 in covered):
            continue
        for j in live[n_ + 1:n_ + 4]:
            r = difflib.SequenceMatcher(None, t, key(raw(j))).ratio()
            if len(t) >= 4 and r > 0.55:
                item = {"类型": "整句重说", "句": i, "原话": raw(i), "像": j, "相似度": round(r, 2), "时间": [S[i]["start"], S[i]["end"]]}
                if r > 0.70:
                    drop.add(i); item["处理"] = f"删这句，留第 {j} 句"; auto.append(item)
                else:
                    item["处理"] = "待听：像整句重说"; listen.append(item)
                break
    # 语速明显偏慢、又没被上面解释的句子：列进待听（多半是有意放慢，也可能是卡顿）
    for i in live:
        s = S[i]
        d = s["end"] - s["start"]
        if i in drop or d <= 1.5 or any(c0 < s["end"] and s["start"] < c1 for c0, c1 in covered):
            continue
        if len(raw(i)) / d < med * 0.6:
            listen.append({"类型": "语速慢", "句": i, "原话": raw(i), "时间": [s["start"], s["end"]],
                           "处理": f"待听：语速 {len(raw(i)) / d:.1f} 字/秒（本人中位 {med:.1f}），可能卡顿或有意放慢"})
    # fix.json 里手写的「cut」：[[原片起, 原片止], …]，自动没找到、人听出来的重说（recut.py --where 可以把成片时间换成原片时间）
    for c0, c1 in fix.get("cut", []):
        c0, c1 = quiet(en, c0 - 0.08, c0 + 0.08), quiet(en, c1 - 0.08, c1 + 0.08)
        item = {"类型": "手动剪", "时间": [c0, c1], "剪掉": [c0, c1], "处理": "按 fix.json 的 cut 剪掉"}
        cuts.append({"c0": c0, "c1": c1, "drop_text": "", "b_on": c1, "b_head": "", "same": "", "item": item, "manual": True})
        auto.append(item)
    cuts.sort(key=lambda c: c["c0"])

    # 3 逐字时间和文字：按文字找放弃那遍（整段转写给的逐字时间不准，不能按时间删字）。
    #   句子里找到放弃那遍的字，且最后一遍的开头出现在它后面（同一句或后面一句）→ 删掉这几个字；
    #   找不到、或最后一遍的开头就在这里（转写把两遍合成一句，只写了最后一遍）→ 不删字，挤进剪掉那段的字挪到最后一遍上。
    S2 = json.loads(json.dumps(S))
    fix_tips = {}
    mid = lambda q: (q["s"] + q["e"]) / 2
    ck = lambda q: key(q["c"])

    def find_all(seq, pat):
        t_ = tol(len(pat))
        return [i for i in range(len(seq) - len(pat) + 1) if near(seq[i:i + len(pat)], pat) <= t_]

    for c in cuts:
        c0, c1 = c["c0"], c["c1"]
        dk, bk = key(c["drop_text"]), key(c["b_head"])
        near_s = [i for i, s in enumerate(S2) if i not in drop and s.get("chars") and s["end"] > c0 - 1.5 and s["start"] < c1 + 1.0]
        for i in near_s:
            s = S2[i]
            ch = s["chars"]
            seq = tuple(k_[0] if k_ else "" for k_ in map(ck, ch))
            hit = None
            for p0 in (find_all(seq, dk) if dk else []):
                p1 = p0 + len(dk)
                later = seq[p1:] + tuple(x for j in near_s if j > i for x in (k_[0] if k_ else "" for k_ in map(ck, S2[j]["chars"])))
                if bk and later[:len(bk)] and near(later[:len(bk)], bk) <= max(1, tol(len(bk))) and abs(ch[p0]["s"] - c0) <= 2.0:
                    hit = (p0, p1)
            if hit:
                gone = "".join(q["c"] for q in ch[hit[0]:hit[1]])
                s["chars"] = ch[:hit[0]] + ch[hit[1]:]
                s.setdefault("retake_removed", []).append(gone)
                s["text"] = "".join(q["c"] for q in s["chars"])
                if str(i) in fix:
                    fx = str(fix[str(i)])
                    pos = [j for j, ch_ in enumerate(fx) if norm(ch_)]  # 改字里每个有效字的位置
                    fk = tuple(key(fx[j])[0] for j in pos)
                    occ = find_all(fk, key(gone))
                    if occ:  # 改字里有两处时，前面那处是放弃的
                        a_, b_ = pos[occ[0]], pos[occ[0] + len(key(gone)) - 1] + 1
                        fix_tips[i] = (fx, re.sub(r"^[，、。；：|\s]+|[，、；：|\s]+$", "", (fx[:a_] + fx[b_:]).replace("，，", "，")))
            if c.get("manual"):  # 手动剪：区间是人按逐字时间挑的，区间里的字直接删
                gone = [q for q in s["chars"] if c0 <= mid(q) < c1]
                if gone:
                    s["chars"] = [q for q in s["chars"] if not (c0 <= mid(q) < c1)]
                    s.setdefault("retake_removed", []).append("".join(q["c"] for q in gone))
                    s["text"] = "".join(q["c"] for q in s["chars"])
                    hit = True
            # 剩下挤在剪掉那段里的字（最后一遍的字被转写记早了）：挪到最后一遍开口以后
            ch = s["chars"]
            move = [q for q in ch if mid(q) >= c0] if any(c0 <= mid(q) < c1 for q in ch) and not c.get("manual") else []
            if move:
                keep = [q for q in ch if mid(q) < c0]
                span0, span1 = move[0]["s"], move[-1]["e"]
                n0 = max(c1, c["b_on"] - 0.02)
                n1 = max(span1, n0 + 0.15 * len(move))
                k_ = (n1 - n0) / max(0.05, span1 - span0)
                for q in move:
                    q["s"], q["e"] = round(n0 + (q["s"] - span0) * k_, 3), round(n0 + (q["e"] - span0) * k_, 3)
                s["chars"] = keep + move
            if hit or move:
                s["retake_cut"] = s.get("retake_cut", []) + [[c0, c1]]
            if s["chars"]:
                s["start"], s["end"] = s["chars"][0]["s"], s["chars"][-1]["e"]
            else:
                drop.add(i)
    for i in drop:
        S2[i]["drop"] = True

    # 4 保留段：句子按发声段校正起止 → 句间停顿 ≤0.42 并起来 → 挖掉重说 → 丢碎段 → 加头尾
    def fix_start(t):  # 句首落在发声段开头 0.6 秒里（换气、轻声开口）：从这段开头算；落在停顿里（片头常见）：挪到后面最近的发声段开头
        for s in isl:
            if s["a"] <= t < s["b"]:
                return s["a"] if t - s["a"] <= 0.6 else t
            if s["a"] > t:
                return s["a"] if s["a"] - t <= 1.2 else t
        return t

    def fix_end(t):  # 句尾落在发声段里：延到这段说完（最多 0.5 秒）；落在停顿里：退回前面最近的发声段结尾
        for s in isl:
            if s["a"] < t <= s["b"]:
                return s["b"] if s["b"] - t <= 0.5 else t
        prev = [s["b"] for s in isl if s["b"] < t]
        return prev[-1] if prev and t - prev[-1] <= 1.2 else t

    spans = sorted([fix_start(S[i]["start"]), fix_end(S[i]["end"])] for i in range(len(S)) if i not in drop)
    regions = []
    for a0, b0 in spans:
        if regions and a0 - regions[-1][1] <= GAP_MAX:
            regions[-1][1] = max(regions[-1][1], b0)
        else:
            regions.append([a0, b0])
    pieces = []  # [起, 止, 起点是重说剪点, 止点是重说剪点]
    for a0, b0 in regions:
        cur = [a0, b0, False, False]
        for c in cuts:
            if c["c1"] <= cur[0] or c["c0"] >= cur[1]:
                continue
            if c["c0"] > cur[0]:
                pieces.append([cur[0], c["c0"], cur[2], True])
            cur = [max(cur[0], c["c1"]), cur[1], True, cur[3]]
        if cur[1] > cur[0]:
            pieces.append(cur)
    kept = []
    for p in pieces:
        vb = speech_bounds(en, lo, isl, p[0], p[1])
        if p[1] - p[0] < MIN_PIECE or not vb or vb[2] < 0.15:
            continue  # 碎段：剪完剩下的零头，留着会在接点多出一次跳帧和咔哒
        kept.append(p + [vb[0], vb[1]])
    out = []
    for k, (p0, p1, cut_a, cut_b, v0, v1) in enumerate(kept):
        head = FIRST_HEAD if k == 0 else HEAD
        tail = LAST_TAIL if k == len(kept) - 1 else TAIL
        a1 = min(quiet(en, v0 - head - 0.03, v0 - head + 0.03), v0 - 0.06)
        b1 = max(quiet(en, v1 + tail - 0.03, v1 + tail + 0.03), v1 + 0.10)
        if cut_a:
            a1 = max(a1, p0)
        if cut_b:
            b1 = min(b1, p1)
        a1, b1 = max(0.0, a1), min(dur, b1)
        if out and a1 < out[-1][1]:
            a1 = out[-1][1]
        out.append([round(a1, 3), round(b1, 3)])
    # 接点类型：剪掉的那截里有重说（逐段转写剪的、整句重说删的）就是重说接点
    redo = [(c["c0"], c["c1"]) for c in cuts] + [(S[it["句"]]["start"], S[it["句"]]["end"]) for it in auto if it["类型"] == "整句重说"]
    kinds = ["retake" if any(r0 < out[k + 1][0] and r1 > out[k][1] for r0, r1 in redo) else "pause" for k in range(len(out) - 1)]

    # 5 接点检查：两头都在停顿里、停顿 0.12–0.5 秒
    joins = []
    for k in range(len(out) - 1):
        b1, a2 = out[k][1], out[k + 1][0]
        v1, v2 = kept[k][5], kept[k + 1][4]
        gap = round((b1 - v1) + (v2 - a2), 3)
        tail_hot, head_hot = in_speech(en, lo, isl, b1 - 0.02), in_speech(en, lo, isl, a2 + 0.02)  # 换气声、底噪不算
        ok = not tail_hot and not head_hot and 0.12 <= gap <= 0.5
        probs = [("前一段尾巴切到了字" if tail_hot else ""), ("后一段开头切到了字" if head_hot else ""),
                 (f"停顿只有 {gap:.2f} 秒，接得太紧" if gap < 0.12 else ""), (f"停顿 {gap:.2f} 秒，偏长" if gap > 0.5 else "")]
        joins.append({"原片": [b1, a2], "类型": "重说" if kinds[k] == "retake" else "停顿", "停顿": gap, "ok": ok,
                      "问题": "；".join(p for p in probs if p)})

    # 6 复核：重说接起来的那几秒拼出来再转写，重复的话只剩一遍
    if cuts and wbin and model:
        items, idx = [], []
        for c in cuts:
            w0, w1 = c["c0"] - 2.5, c["c1"] + 2.5
            spans_ = [(max(p, w0), min(q, w1)) for p, q in out if q > w0 and p < w1]
            if spans_:
                items.append(spans_); idx.append(c)
        for c, (text, _) in zip(idx, asr(x, sr, items, tmp, wbin, model)):
            n_same = count_near(text, c["same"]) if c["same"] else 1
            ok = n_same <= 1 and (not c["b_head"] or count_near(text, c["b_head"]) >= 1)
            c["item"]["复核转写"] = text
            c["item"]["复核"] = "通过" if ok else "没通过：接起来以后「%s」出现 %d 次或最后一遍开头缺字，听一下" % (c["same"], n_same)
            if not ok and c["item"] not in listen:
                listen.append(c["item"])

    os.makedirs(a.work, exist_ok=True)
    json.dump(out, open(os.path.join(a.work, "edl.json"), "w"), indent=0)
    json.dump(kinds, open(os.path.join(a.work, "edl_joins.json"), "w"))
    tr2 = dict(tr, sentences=S2) if isinstance(tr, dict) else S2
    json.dump(tr2, open(os.path.join(a.work, "transcript_edl.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep = {"输入": {"transcript": os.path.abspath(a.transcript), "src": os.path.abspath(a.src),
                   "fix": os.path.abspath(a.fix) if a.fix else None},
           "找重说的办法": mode, "本人中位语速": round(med, 1), "自动处理": auto, "待听清单": listen,
           "接点检查": [j for j in joins if not j["ok"]], "接点数": len(joins),
           "fix改字建议": {str(i): {"原来": fx, "改成": tip} for i, (fx, tip) in fix_tips.items()},
           "原片秒": round(dur, 2), "保留秒": round(sum(b - a for a, b in out), 2), "保留段数": len(out)}
    json.dump(rep, open(os.path.join(a.work, "edl_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"edl.json：{len(out)} 段，保留 {rep['保留秒']} 秒（原片 {rep['原片秒']} 秒）；找重说：{mode}")
    for it in auto:
        what = f"「{it.get('放弃那遍') or it.get('原话', '')}」" + (f"→「{it['最后一遍']}」" if it.get("最后一遍") else "")
        print(f"  ✂ {it['时间'][0]:.2f}s {it['类型']}{what}：{it['处理']}" + (f"；复核{it['复核']}" if it.get("复核") else ""))
    for it in listen:
        if it in auto:
            continue
        print(f"  ? {it['时间'][0]:.2f}s {it['类型']}「{it.get('放弃那遍') or it.get('原话', '')}」：{it['处理']}")
    bad = [j for j in joins if not j["ok"]]
    print(f"  接点 {len(joins)} 个" + ("，全部落在停顿里" if not bad else f"，{len(bad)} 个要看：" + "；".join(f"{j['原片'][0]:.2f}s {j['问题']}" for j in bad)))
    if fix_tips and a.fix:  # 字幕跟着声音走：剪掉的字从 fix.json 的改字里也删掉（原文件另存 .bak）
        shutil.copy(a.fix, a.fix + ".bak")
        for i, (fx, tip) in fix_tips.items():
            fix[str(i)] = tip
        json.dump(fix, open(a.fix, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for i, (fx, tip) in fix_tips.items():
        print(f"  ✎ 第 {i} 句剪掉了「{''.join(S2[i]['retake_removed'])}」，fix.json 这句的改字已跟着改：「{fx}」→「{tip}」（原文件存为 fix.json.bak）")
    print("transcript_edl.json 已写好：prep.py captions 用它（--transcript 工作目录/transcript_edl.json）")


if __name__ == "__main__":
    main()
