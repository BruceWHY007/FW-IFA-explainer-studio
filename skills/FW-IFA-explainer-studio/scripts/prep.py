# -*- coding: utf-8 -*-
"""前期准备（macOS／Windows／Linux 通用，只依赖 ffmpeg、Python 标准库，numpy 可选）。

所有命令都以「工作目录 W」为中心：素材生成到 W/om_assets/，导入清单累积在 W/import.json（om.py import 用）。

  python prep.py cut      --work W --src 原片.mp4 --edl edl.json        剪辑：保留段 → aroll.mp4（1080×1920，无声）＋voice_raw.wav＋cuts.json
  python prep.py voice    --work W                                       人声：低切 70Hz、轻压缩、两遍响度统一到 −16 LUFS → voice.wav
  python prep.py captions --work W --transcript transcript.json [--fix fix.json]   字幕：按剪辑映射时间、断句（≤14 字）。
                                                                         校对过的句子（fix.json）按标点和 | 断；没校对的按词边界和停顿断
  python prep.py broll    --work W --src 素材.mp4 --key trading [--start 2 --dur 10] [--kinds band,tile,bg,thumb,full]
  python prep.py image    --work W --src 图片.jpg --key chip [--kinds bg,thumb]
  python prep.py mix      --work W --music 配乐.mp3 [--gain -6]          配乐：按人声压低（侧链），首尾淡入淡出 → bgm.wav
  python prep.py base     --work W                                       把字体（带许可证）、底纹、音效加进导入清单

edl.json：[[起, 止], …] 原片里要保留的时间段（秒）。fix.json：{"句号": "改正后的文字，用 | 强制断行", "drop": [不要的句号]}。
transcript.json：IFA口播成片 的 ingest.py 输出（{"sentences":[{start,end,text}]}），或任何 [{start,end,text}] 列表。
"""
import argparse, json, math, os, re, shutil, subprocess, sys, wave, array

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FPS = 30
SFX_DIR = os.environ.get("TUJIE_SFX_DIR") or os.path.join(os.path.expanduser("~"), ".agents", "skills", "video-shotcraft", "template", "public", "audio")
SFX = ["transition-soft", "transition-snap", "swoosh-quick", "whoosh-fast", "impact-cine", "click-camera"]


def ff(*args):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        sys.exit("ffmpeg 失败：" + r.stderr[-1500:])


def probe(path, *entries):
    return subprocess.check_output(["ffprobe", "-v", "error", *entries, "-of", "csv=p=0", path]).decode().strip()


def om(work):
    d = os.path.join(work, "om_assets")
    os.makedirs(d, exist_ok=True)
    return d


def manifest_add(work, key, path, name, license=None):
    p = os.path.join(work, "import.json")
    items = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
    items = [x for x in items if x["key"] != key]
    it = {"key": key, "path": os.path.abspath(path), "name": name}
    if license:
        it["license"] = os.path.abspath(license)
    items.append(it)
    json.dump(items, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


BT709 = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"
ENC = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-g", "30", "-pix_fmt", "yuv420p",
       "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart"]


# ---------------------------------------------------------------- 剪辑
def cmd_cut(a):
    edl = json.load(open(a.edl, encoding="utf-8"))
    edl = [[round(round(x / (1 / FPS)) / FPS, 4), round(round(y / (1 / FPS)) / FPS, 4)] for x, y in edl]
    o = om(a.work)
    n = len(edl)
    v = "".join(f"[0:v]trim={x}:{y},setpts=PTS-STARTPTS[v{k}];" for k, (x, y) in enumerate(edl))
    au = "".join(f"[0:a]atrim={x}:{y},asetpts=PTS-STARTPTS[a{k}];" for k, (x, y) in enumerate(edl))
    cat = "".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac];"
    scale = f"[vc]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps={FPS},{BT709}[vo]"
    ff("-i", a.src, "-filter_complex", v + au + cat + scale, "-map", "[vo]", *ENC, "-an", os.path.join(o, "aroll.mp4"),
       "-map", "[ac]", "-ar", "48000", "-ac", "1", os.path.join(a.work, "voice_raw.wav"))
    cuts, acc = [], 0.0
    for x, y in edl[:-1]:
        acc += y - x
        cuts.append(round(acc, 3))
    json.dump(edl, open(os.path.join(a.work, "edl_frames.json"), "w"), indent=0)
    json.dump(cuts, open(os.path.join(a.work, "cuts.json"), "w"))
    dur = float(probe(os.path.join(o, "aroll.mp4"), "-show_entries", "format=duration"))
    manifest_add(a.work, "aroll", os.path.join(o, "aroll.mp4"), "口播－剪辑版（无声）")
    print(f"aroll.mp4 {dur:.2f}s，{n} 段，剪辑点 {len(cuts)} 个")


# ---------------------------------------------------------------- 人声
def cmd_voice(a):
    src = os.path.join(a.work, "voice_raw.wav")
    chain = "highpass=f=70,acompressor=threshold=-24dB:ratio=2.2:attack=10:release=150:makeup=1.5"
    r = subprocess.run(["ffmpeg", "-nostats", "-i", src, "-af", chain + ",loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8")
    j = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    ln = (f"loudnorm=I=-16:TP=-1.5:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    out = os.path.join(om(a.work), "voice.wav")
    ff("-i", src, "-af", chain + "," + ln, "-ar", "48000", out)
    manifest_add(a.work, "voice", out, "人声（处理后）")
    print(f"voice.wav：原始 {j['input_i']} LUFS → −16 LUFS")


# ---------------------------------------------------------------- 字幕
def weight(ch):
    return 0.55 if re.match(r"[A-Za-z0-9]", ch) else (0 if re.match(r"[，。？：、！,.?:|\s]", ch) else 1)


def phrases(text, maxc=14):
    out = []
    for h in text.split("|"):
        parts = [p for p in re.split(r"(?<=[，。？：！；])", h) if p.strip()]
        cur = ""
        for p in parts:
            cand = cur + p
            if cur and sum(weight(c) for c in cand) > maxc:
                out.append(cur)
                cur = p
            else:
                cur = cand
        if cur:
            out.append(cur)
    res = []
    for o in out:
        o = o.strip()
        while sum(weight(c) for c in o) > maxc + 4:  # 没有标点的超长句硬切
            k = 0; acc = 0
            for k, c in enumerate(o):
                acc += weight(c)
                if acc >= maxc:
                    break
            res.append(o[:k + 1]); o = o[k + 1:]
        res.append(re.sub(r"[，。：！；]$", "", o))
    return [r for r in res if r.strip()]


def phrases_from_chars(chars, maxc=14):
    """没有校对稿时：按词（w 相同的字是一个词）累积，只在词边界断，优先断在停顿最长的地方。返回 [(文字, 起, 止)]。"""
    words = []
    for c in chars:
        if words and c.get("w") is not None and words[-1]["w"] == c.get("w"):
            words[-1]["t"] += c["c"]; words[-1]["e"] = c["e"]
        else:
            words.append({"w": c.get("w"), "t": c["c"], "s": c["s"], "e": c["e"]})
    out, cur = [], []
    wsum = lambda ws: sum(weight(ch) for x in ws for ch in x["t"])
    i = 0
    while i < len(words):
        cur.append(words[i]); i += 1
        if wsum(cur) >= maxc * 0.55 and i < len(words):
            # 往后看，在不超长的范围里挑停顿最长的词边界
            best, bgap, j, tmp = None, -1, i, list(cur)
            while True:
                gap = words[j]["s"] - tmp[-1]["e"] if j < len(words) else 9
                if gap > bgap:
                    best, bgap = j, gap
                if j >= len(words) or wsum(tmp + [words[j]]) > maxc:
                    break
                tmp.append(words[j]); j += 1
            cur += words[i:best]; i = best
            out.append(cur); cur = []
    if cur:
        if out and wsum(cur) <= 3 and wsum(out[-1]) + wsum(cur) <= maxc + 3:
            out[-1] += cur
        else:
            out.append(cur)
    return [("".join(x["t"] for x in ws), ws[0]["s"], ws[-1]["e"]) for ws in out]


def energy(wav):
    wf = wave.open(wav, "rb")
    sr, n, ch = wf.getframerate(), wf.getnframes(), wf.getnchannels()
    A = array.array("h", wf.readframes(n))
    if ch == 2:
        A = A[::2]
    hop = int(sr * 0.01)
    E = []
    for i in range(0, len(A) - hop, hop):
        seg = A[i:i + hop:4]
        E.append(10 * math.log10(sum(x * x for x in seg) / max(1, len(seg)) / 32768 ** 2 + 1e-12))
    return E


def cmd_captions(a):
    edl = json.load(open(os.path.join(a.work, "edl_frames.json")))
    t = json.load(open(a.transcript, encoding="utf-8"))
    ss = t["sentences"] if isinstance(t, dict) else t
    fix = json.load(open(a.fix, encoding="utf-8")) if a.fix else {}
    drop = set(fix.get("drop", []))
    offs, acc = [], 0.0
    for x, y in edl:
        offs.append((x, y, acc)); acc += y - x

    def m(tt, side):
        for x, y, o in offs:
            if x - 0.02 <= tt <= y + 0.02:
                return o + min(max(tt, x), y) - x
        if side == "s":
            for x, y, o in offs:
                if x > tt:
                    return o
        best = None
        for x, y, o in offs:
            if y < tt:
                best = o + y - x
        return best

    spans = []
    for i, s in enumerate(ss):
        if i in drop or str(i) in drop:
            continue
        ma, mb = m(s["start"], "s"), m(s["end"], "e")
        if ma is None or mb is None or mb - ma < 0.15:
            continue
        spans.append((ma, mb, fix.get(str(i), s["text"]).strip(), i))
    spans.sort()
    caps = []
    for i, s in enumerate(ss):  # 没有校对稿的句子：用字级时间断句
        if str(i) in fix or i in drop or str(i) in drop or not s.get("chars"):
            continue
        for txt, cs, ce in phrases_from_chars(s["chars"], a.maxc):
            ma, mb = m(cs, "s"), m(ce, "e")
            if ma is not None and mb is not None and mb - ma > 0.1:
                caps.append({"text": txt, "start": round(ma, 3), "end": round(mb, 3), "sid": i, "chars": True})
    spans = [x for x in spans if str(x[3]) in fix or not ss[x[3]].get("chars")]
    # 字级时间（剪辑后时间轴）：build 用它把「说到某个词」换成秒数、让逐字展开跟语速走
    inside = lambda tt: any(x - 0.02 <= tt <= y + 0.02 for x, y in edl)
    ct = []
    for i, s in enumerate(ss):
        if i in drop or str(i) in drop:
            continue
        for c in s.get("chars") or []:
            if inside(c["s"]) and inside(c["e"]):
                a_, b_ = m(c["s"], "s"), m(c["e"], "e")
                if a_ is not None and b_ is not None:
                    ct.append([c["c"], round(a_, 3), round(b_, 3)])
    ct.sort(key=lambda x: x[1])
    json.dump(ct, open(os.path.join(a.work, "chartimes.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for ma, mb, text, i in spans:
        ps = phrases(text, a.maxc)
        tw = [max(0.5, sum(weight(c) for c in p)) for p in ps]
        T = sum(tw); tt = ma
        for p, w in zip(ps, tw):
            d = (mb - ma) * w / T
            caps.append({"text": re.sub(r"[、，：]", " ", p).replace("|", ""), "start": round(tt, 3), "end": round(tt + d, 3), "sid": i})
            tt += d
    vw = os.path.join(om(a.work), "voice.wav")
    if os.path.exists(vw):
        E = energy(vw)

        def snap(tt, r=0.22):
            i0, i1 = max(0, int((tt - r) / 0.01)), min(len(E) - 1, int((tt + r) / 0.01))
            return min(range(i0, i1 + 1), key=lambda i: (E[i], abs(i * 0.01 - tt))) * 0.01
        caps.sort(key=lambda c: c["start"])
        for k in range(1, len(caps)):
            if caps[k]["sid"] == caps[k - 1]["sid"] and not caps[k].get("chars"):
                b = snap(caps[k]["start"]); caps[k]["start"] = round(b, 3); caps[k - 1]["end"] = round(b, 3)
    caps.sort(key=lambda c: c["start"])
    for c in caps:
        c.pop("chars", None)
    for k in range(len(caps) - 1):
        g = caps[k + 1]["start"] - caps[k]["end"]
        if 0 < g < 0.35:
            caps[k]["end"] = caps[k + 1]["start"]
    json.dump(caps, open(os.path.join(a.work, "captions.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"captions.json：{len(caps)} 条；chartimes.json：{len(ct)} 个字的时间（分镜表里可以写 \"t\": \"@关键词\"）")


# ---------------------------------------------------------------- B-roll
def cmd_broll(a):
    o = om(a.work)
    kinds = a.kinds.split(",")
    ss = ["-ss", str(a.start)] if a.start else []
    dur = ["-t", str(a.dur)] if a.dur else []
    made = []
    if "band" in kinds:  # 横条 1080×608
        p = os.path.join(o, f"band_{a.key}.mp4")
        ff(*ss, *dur, "-i", a.src, "-vf", f"scale=1080:608:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:608,fps={FPS},{BT709}", *ENC, "-an", p)
        manifest_add(a.work, f"band_{a.key}", p, f"{a.name or a.key}－横条"); made.append("band")
    if "tile" in kinds:  # 宫格 528×396
        p = os.path.join(o, f"tile_{a.key}.mp4")
        ff(*ss, *dur, "-i", a.src, "-vf", f"scale=528:396:force_original_aspect_ratio=increase:flags=lanczos,crop=528:396,fps={FPS},{BT709}", *ENC, "-an", p)
        manifest_add(a.work, f"tile_{a.key}", p, f"{a.name or a.key}－宫格"); made.append("tile")
    if "full" in kinds:  # 竖版全屏
        p = os.path.join(o, f"full_{a.key}.mp4")
        ff(*ss, *dur, "-i", a.src, "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,fps={FPS},{BT709}", *ENC, "-an", p)
        manifest_add(a.work, f"full_{a.key}", p, f"{a.name or a.key}－全屏"); made.append("full")
    still_at = str((a.start or 0) + 1.0)
    if "bg" in kinds:
        p = os.path.join(o, f"bg_{a.key}.jpg")
        ff("-ss", still_at, "-i", a.src, "-frames:v", "1", "-vf", "scale=1200:2040:force_original_aspect_ratio=increase,crop=1200:2040", "-q:v", "3", p)
        manifest_add(a.work, f"bg_{a.key}", p, f"{a.name or a.key}－背景"); made.append("bg")
    if "thumb" in kinds:
        p = os.path.join(o, f"thumb_{a.key}.jpg")
        ff("-ss", still_at, "-i", a.src, "-frames:v", "1", "-vf", "scale=960:540:force_original_aspect_ratio=increase,crop=960:540", "-q:v", "3", p)
        manifest_add(a.work, f"thumb_{a.key}", p, f"{a.name or a.key}－配图"); made.append("thumb")
    print(f"{a.key}：{', '.join(made)}")


def cmd_image(a):
    o = om(a.work)
    for k in a.kinds.split(","):
        size = {"bg": "1200:2040", "thumb": "960:540"}[k]
        p = os.path.join(o, f"{k}_{a.key}.jpg")
        ff("-i", a.src, "-vf", f"scale={size}:force_original_aspect_ratio=increase,crop={size}", "-q:v", "3", p)
        manifest_add(a.work, f"{k}_{a.key}", p, f"{a.name or a.key}－{'背景' if k == 'bg' else '配图'}")
    print("ok")


# ---------------------------------------------------------------- 配乐
def cmd_mix(a):
    o = om(a.work)
    voice = os.path.join(o, "voice.wav")
    dur = a.dur or float(probe(os.path.join(o, "aroll.mp4"), "-show_entries", "format=duration")) + 1.2
    out = os.path.join(o, "bgm.wav")
    ff("-i", a.music, "-i", voice, "-filter_complex",
       f"[0:a]atrim=0:{dur},asetpts=PTS-STARTPTS,aresample=48000,volume={a.gain}dB,afade=t=in:d=0.6,afade=t=out:st={max(0, dur - 2.5)}:d=2.5[m];"
       f"[1:a]aresample=48000,apad=whole_dur={dur}[v];[m][v]sidechaincompress=threshold=0.04:ratio=4:attack=25:release=450:makeup=1[md]",
       "-map", "[md]", "-ar", "48000", "-ac", "2", out)
    manifest_add(a.work, "bgm", out, f"配乐－{os.path.splitext(os.path.basename(a.music))[0]}（避让人声）")
    r = subprocess.run(["ffmpeg", "-nostats", "-i", out, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8")
    li = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    print(f"bgm.wav {dur:.1f}s，响度 {li[-1] if li else '?'} LUFS（人声 −16，配乐建议 −29 到 −33）")


def cmd_base(a):
    F = os.path.join(ROOT, "assets", "fonts")
    for key, f, lic, nm in (("font_sm", "SmileySans-Oblique.otf", "SmileySans-OFL.txt", "得意黑 Smiley Sans"),
                            ("font_en", "Inter.ttf", "Inter-OFL.txt", "Inter"),
                            ("font_num", "Oswald.ttf", "Oswald-OFL.txt", "Oswald"),
                            ("font_sr", "ZCOOLXiaoWei-Regular.ttf", "ZCOOLXiaoWei-OFL.txt", "站酷小薇"),
                            ("font_br", "ZhiMangXing-Regular.ttf", "ZhiMangXing-OFL.txt", "志莽行书")):
        manifest_add(a.work, key, os.path.join(F, f), nm, os.path.join(F, lic))
    T = os.path.join(ROOT, "assets", "textures")
    manifest_add(a.work, "tex_stone", os.path.join(T, "stone.jpg"), "底纹－石墨岩面")
    manifest_add(a.work, "tex_archive", os.path.join(T, "archive.jpg"), "底纹－暖黑纸面")
    n = 0
    styles = [a.style] if a.style else ["tanjin", "dangan", "kuangshi", "cilan", "nihong"]
    for st in styles:  # 各风格自己的音效（程序合成，随技能附带）
        for kind in ("soft", "snap", "swoosh", "whoosh", "impact", "click"):
            p = os.path.join(ROOT, "assets", "sfx", st, kind + ".mp3")
            if os.path.exists(p):
                manifest_add(a.work, f"sfx_{st}_{kind}", p, f"音效－{st}－{kind}"); n += 1
    m = 0
    for s in SFX:  # 可选：通用音效目录（TUJIE_SFX_DIR），风格音效缺项时补位
        p = os.path.join(SFX_DIR, s + ".mp3")
        if os.path.exists(p):
            manifest_add(a.work, f"sfx_{s}", p, f"音效－{s}"); m += 1
    print(f"字体 5 个、底纹 2 张、风格音效 {n} 个、通用音效 {m} 个")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("cut"); p.add_argument("--work", required=True); p.add_argument("--src", required=True); p.add_argument("--edl", required=True)
    p = sp.add_parser("voice"); p.add_argument("--work", required=True)
    p = sp.add_parser("captions"); p.add_argument("--work", required=True); p.add_argument("--transcript", required=True); p.add_argument("--fix"); p.add_argument("--maxc", type=int, default=14)
    p = sp.add_parser("broll"); p.add_argument("--work", required=True); p.add_argument("--src", required=True); p.add_argument("--key", required=True)
    p.add_argument("--name"); p.add_argument("--start", type=float, default=0); p.add_argument("--dur", type=float, default=12); p.add_argument("--kinds", default="band,thumb")
    p = sp.add_parser("image"); p.add_argument("--work", required=True); p.add_argument("--src", required=True); p.add_argument("--key", required=True); p.add_argument("--name"); p.add_argument("--kinds", default="bg,thumb")
    p = sp.add_parser("mix"); p.add_argument("--work", required=True); p.add_argument("--music", required=True); p.add_argument("--gain", type=float, default=-6); p.add_argument("--dur", type=float)
    p = sp.add_parser("base"); p.add_argument("--work", required=True); p.add_argument("--style", help="只加这一套风格的音效（不写就五套都加）")
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
