# -*- coding: utf-8 -*-
"""剪辑表：从转写自动出 edl.json（原片里要保留的时间段），同时查重说和卡顿。

用法：python3 scripts/edl.py --transcript transcript.json --src 原片.mp4 --work 工作目录 [--fix fix.json] [--verify]
产物：工作目录/edl.json（给 prep.py cut）、工作目录/transcript_edl.json（给 prep.py captions）、工作目录/edl_report.json

为什么要看声音：转写模型常把「说到一半停住、又从头说一遍」合成一句，文字上看不出重复，只按文字剪就会漏。
所以每句同时看三个信号：
  慢        这句的语速低于本人中位语速的 6 成（长于 1.5 秒）
  声音重复  同一段 0.5 秒的声音在这句里出现两次（相似度 ≥0.80、间隔 ≥0.45 秒），能定出第一遍和第二遍各从哪开始
  文字重复  这句和后面 3 句里的某一句文字很像（整句重说）
处理：
  慢＋声音重复           自动剪掉第一遍，留最后完整的一遍；切点落在停顿最低处，前面卡住的停顿一起剪
  文字相似度 >0.70       自动删前一句（留后一句）
  只有一个信号           不剪，列进「待听清单」，交付时请人听
原则（借 ChatCut 口播指南）：只留一遍完整的，不把几遍的碎片拼成一句；第一遍里后面没再说的铺垫要留。
压停顿：句间停顿 ≤0.42 秒不动，更长的压到 0.26 秒；切点吸附到 ±60ms 内能量最低处。
剪掉第一遍的句子，逐字时间按保留的那一遍重排，写进 transcript_edl.json（不然「@关键词」和字幕会对不上）。
--verify：有 whisper-cli 时，把每处自动剪后留下的那一遍单独再转写一次，和原句比对。
"""
import argparse, difflib, json, os, shutil, subprocess, sys, tempfile, wave
import numpy as np

GAP_KEEP, GAP_MAX, HEAD, TAIL = 0.26, 0.42, 0.12, 0.40


def load_audio(src):
    tmp = tempfile.mkdtemp(prefix="edl_")
    wav = os.path.join(tmp, "a16.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return x, 16000, tmp, wav


def features(x, sr):
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


def snap(en, t, lo, hi):
    """切点吸附到 [t+lo, t+hi] 里能量最低处。"""
    a, b = max(0, int((t + lo) * 100)), max(int((t + lo) * 100) + 1, int((t + hi) * 100))
    seg = en[a:b]
    return (a + int(seg.argmin())) / 100 if len(seg) else t


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--src", required=True, help="原片（视频或音频）")
    ap.add_argument("--work", required=True)
    ap.add_argument("--fix", help="fix.json：drop 里的句子不进剪辑表")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    tr = json.load(open(a.transcript, encoding="utf-8"))
    S = tr["sentences"] if isinstance(tr, dict) else tr
    fix = json.load(open(a.fix, encoding="utf-8")) if a.fix else {}
    drop = {int(x) for x in fix.get("drop", [])} | {i for i, s in enumerate(S) if s.get("drop")}
    x, sr, tmp, wav = load_audio(a.src)
    L, en = features(x, sr)
    live_db = float(np.median(en)) - 3
    text = lambda i: str(fix.get(str(i), S[i]["text"])).replace("|", "")
    live = [i for i in range(len(S)) if i not in drop]
    rates = [len(text(i)) / (S[i]["end"] - S[i]["start"]) for i in live if S[i]["end"] - S[i]["start"] > 1]
    med = float(np.median(rates)) if rates else 5.0
    auto, listen, cuts = [], [], {}
    for n_, i in enumerate(live):
        s = S[i]
        d = s["end"] - s["start"]
        t = text(i)
        # 文字重复：和后面 3 句比
        for j in live[n_ + 1:n_ + 4]:
            r = difflib.SequenceMatcher(None, t, text(j)).ratio()
            if len(t) >= 4 and r > 0.55:
                item = {"句": i, "原话": t, "像": j, "相似度": round(r, 2), "时间": [s["start"], s["end"]]}
                if r > 0.70:
                    drop.add(i); item["处理"] = f"删这句，留第 {j} 句"; auto.append(item)
                else:
                    item["处理"] = "待听：像整句重说"; listen.append(item)
                break
        if i in drop or d < 1.0:
            continue
        rate = len(t) / d
        slow = d > 1.5 and rate < med * 0.6
        sim, ta, tb, lag = selfsim(L, en, s["start"], s["end"], live_db)
        rep = sim >= 0.80
        if slow and rep:
            c0 = take_start(L, en, s["start"], ta, lag, live_db)
            c0 = s["start"] if c0 - s["start"] < 0.35 else snap(en, c0, -0.25, 0.03)
            c1 = snap(en, c0 + lag, -0.30, 0.03)
            cuts[i] = (c0, c1)
            auto.append({"句": i, "原话": t, "时间": [s["start"], s["end"]], "语速": round(rate, 1), "本人中位语速": round(med, 1),
                         "声音重复": round(sim, 2), "剪掉": [round(c0, 2), round(c1, 2)], "处理": "剪掉第一遍，留后面完整的一遍"})
        elif slow or rep:
            listen.append({"句": i, "原话": t, "时间": [s["start"], s["end"]], "语速": round(rate, 1), "本人中位语速": round(med, 1),
                           "声音重复": round(sim, 2), "处理": "待听：" + ("语速慢，可能卡顿或有意放慢" if slow else f"{ta:.2f} 和 {tb:.2f} 声音很像，可能是重复的说法")})
    # 逐字时间：剪掉第一遍的句子，剩下的字按比例排进保留的那一遍
    S2 = json.loads(json.dumps(S))
    for i, (c0, c1) in cuts.items():
        s = S2[i]
        ch = s.get("chars") or []
        keep = [c for c in ch if c["e"] <= c0 + 0.01]
        move = [c for c in ch if c["e"] > c0 + 0.01]
        if move:
            span0, span1 = move[0]["s"], move[-1]["e"]
            k = (s["end"] - c1) / max(0.05, span1 - span0)
            for c in move:
                c["s"], c["e"] = round(c1 + (c["s"] - span0) * k, 3), round(c1 + (c["e"] - span0) * k, 3)
        s["chars"] = keep + move
        if c0 <= s["start"] + 0.01:
            s["start"] = round(c1, 3)
        s["retake_cut"] = [round(c0, 3), round(c1, 3)]
    for i in drop:
        S2[i]["drop"] = True
    # 保留段：逐句拼起来，句内剪掉的第一遍挖掉；句间停顿 ≤0.42 不动，更长的压到 0.26
    spans = []
    for i in range(len(S2)):
        if i in drop:
            continue
        s = S2[i]
        parts = [[s["start"], s["end"]]]
        if i in cuts and cuts[i][0] > S[i]["start"] + 0.01:
            parts = [[S[i]["start"], cuts[i][0]], [cuts[i][1], s["end"]]]
        spans += parts
    keep = []
    for a0, b0 in spans:
        if keep and a0 - keep[-1][1] <= GAP_MAX:
            keep[-1][1] = max(keep[-1][1], b0)
        else:
            keep.append([a0, b0])
    dur = len(x) / sr
    out = []
    for k, (a0, b0) in enumerate(keep):
        pa = HEAD if k == 0 else GAP_KEEP / 2
        pb = TAIL if k == len(keep) - 1 else GAP_KEEP / 2
        a1 = max(0.0, snap(en, a0 - pa, -0.06, 0.06))
        b1 = min(dur, snap(en, b0 + pb, -0.06, 0.06))
        if out and a1 < out[-1][1]:
            a1 = out[-1][1]
        out.append([round(a1, 3), round(b1, 3)])
    os.makedirs(a.work, exist_ok=True)
    json.dump(out, open(os.path.join(a.work, "edl.json"), "w"), indent=0)
    tr2 = dict(tr, sentences=S2) if isinstance(tr, dict) else S2
    json.dump(tr2, open(os.path.join(a.work, "transcript_edl.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.verify and auto and shutil.which("whisper-cli"):
        model = os.environ.get("WHISPER_MODEL") or os.path.expanduser("~/.cache/whisper-cpp/ggml-small.bin")
        for it in auto:
            if "剪掉" not in it or not os.path.exists(model):
                continue
            seg = os.path.join(tmp, "v.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(it["剪掉"][1]), "-to", str(it["时间"][1] + 0.6), "-i", wav, seg], check=True)
            r = subprocess.run(["whisper-cli", "-m", model, "-l", "zh", "-f", seg, "-nt", "-mc", "0"], capture_output=True, text=True)
            heard = "".join(r.stdout.split())
            it["复核转写"] = heard
            it["复核相似度"] = round(difflib.SequenceMatcher(None, it["原话"], heard).ratio(), 2)
    rep = {"本人中位语速": round(med, 1), "自动处理": auto, "待听清单": listen,
           "原片秒": round(dur, 2), "保留秒": round(sum(b - a for a, b in out), 2), "保留段数": len(out)}
    json.dump(rep, open(os.path.join(a.work, "edl_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"edl.json：{len(out)} 段，保留 {rep['保留秒']} 秒（原片 {rep['原片秒']} 秒）；本人中位语速 {med:.1f} 字/秒")
    for it in auto:
        print(f"  ✂ 第 {it['句']} 句 {it['时间'][0]:.2f}s「{it['原话'][:18]}」：{it['处理']}"
              + (f"，剪掉 {it['剪掉'][0]:.2f}–{it['剪掉'][1]:.2f}s" if "剪掉" in it else "")
              + (f"；复核转写「{it['复核转写']}」相似 {it['复核相似度']}" if "复核转写" in it else ""))
    for it in listen:
        print(f"  ? 第 {it['句']} 句 {it['时间'][0]:.2f}s「{it['原话'][:18]}」：{it['处理']}")
    print("transcript_edl.json 已写好：prep.py captions 用它（--transcript 工作目录/transcript_edl.json）")


if __name__ == "__main__":
    main()
