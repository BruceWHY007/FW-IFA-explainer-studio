# -*- coding: utf-8 -*-
"""自检：不用任何真人视频，生成占位素材（灰色人形剪影、渐变横条、配图），按 examples/demo 的分镜表把五套风格各构建一遍，
有 OpenMotion 时再跑 lint、完整检查、平台安全区检查和抽帧；另外用占位句子测找重说的判定规则和重剪时的时间搬移。装完环境、改完代码都可以跑它确认链路通。

用法：python selftest.py [--style tanjin] [--out 目录] [--snapshot]
  不写 --style 就五套都跑；--snapshot 抽 8 帧拼成总览图（每套约 30 秒）。
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import om  # noqa: E402

STYLES = ["tanjin", "dangan", "kuangshi", "cilan", "nihong"]
DUR = 40
# 占位人形：头（椭圆）中心 (540,700)，脸框按「眉到下巴」取
HEAD = (540, 700, 150, 185)
FACE = [400, 570, 280, 320]


def ff(*a):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg 失败：" + r.stderr[-800:])


def gradient(path, w, h, c0, c1, label, font):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        t = y / max(1, h - 1)
        col = tuple(int(c0[i] * (1 - t) + c1[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = col
    d = ImageDraw.Draw(im)
    if label:
        d.text((w * 0.06, h * 0.08), label, fill=(255, 255, 255), font=font)
    im.save(path, quality=88)


def make_media(A):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(A, exist_ok=True)
    font = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "SmileySans-Oblique.otf"), 56)
    small = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "SmileySans-Oblique.otf"), 40)
    # 人物占位：暖灰背景＋灰色人形
    im = Image.new("RGB", (1080, 1920))
    px = im.load()
    for y in range(1920):
        for x in range(1080):
            v = 150 - y * 0.03 + (x - 540) * 0.01
            px[x, y] = (int(v * 1.05), int(v), int(v * 0.92))
    mask = Image.new("L", (1080, 1920), 0)
    md = ImageDraw.Draw(mask)
    cx, cy, rx, ry = HEAD
    md.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    md.rectangle([cx - 70, cy + ry - 40, cx + 70, cy + ry + 90], fill=255)
    md.polygon([(cx - 120, 960), (cx + 120, 960), (cx + 470, 1300), (cx + 470, 1920), (cx - 470, 1920), (cx - 470, 1300)], fill=255)
    md.ellipse([cx - 470, 1180, cx - 270, 1420], fill=255)
    md.ellipse([cx + 270, 1180, cx + 470, 1420], fill=255)
    body = Image.new("RGB", (1080, 1920), (92, 96, 104))
    im.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(im)
    d.text((cx - 150, 1120), "人物画面占位", fill=(230, 230, 230), font=font)
    d.text((cx - 170, 1190), "HOST PLACEHOLDER", fill=(200, 200, 200), font=small)
    im.save(os.path.join(A, "host.png"))
    ff("-loop", "1", "-i", os.path.join(A, "host.png"), "-t", str(DUR), "-r", "30", "-vf", "format=yuv420p",
       "-c:v", "libx264", "-crf", "24", "-g", "30", os.path.join(A, "aroll.mp4"))
    ff("-f", "lavfi", "-i", "gradients=s=1080x608:c0=0x1f3b73:c1=0xc07a3a:c2=0x2a6f5a:x0=0:y0=0:x1=1080:y1=608:speed=0.02:d=12:r=30",
       "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "24", "-g", "30", os.path.join(A, "band_demo.mp4"))
    gradient(os.path.join(A, "bg_demo.jpg"), 600, 1020, (40, 44, 60), (20, 18, 22), "", font)
    for k, (c0, c1) in enumerate([((70, 110, 160), (20, 30, 50)), ((150, 120, 70), (40, 30, 20)), ((60, 140, 100), (20, 40, 30))], start=1):
        gradient(os.path.join(A, f"thumb_demo{k}.jpg"), 480, 270, c0, c1, f"配图 {k}", font)
    # 量出的几何（和真实 measure.py 输出同格式）
    rows = []
    for y in range(0, 1920, 12):
        xs = [x for x in range(0, 1080, 4) if mask.getpixel((x, y))]
        rows.append([y, xs[0] if xs else -1, xs[-1] if xs else -1])
    frames = [{"t": round(i * 0.5, 2), "face": FACE, "head_top": cy - ry, "extents": rows} for i in range(DUR * 2 + 1)]
    return {"video": "aroll.mp4", "width": 1080, "height": 1920, "duration": DUR, "step": 0.5, "backend": "synthetic", "frames": frames}


def logic_checks():
    """不用音频的两项：找重说的判定规则（占位句子）、重剪时分镜表时间怎么搬。返回 (通过数, 总数, 没通过的说明)。"""
    import edl
    from recut import mapper
    t = 0.0
    def isl(text, d):
        nonlocal t
        n = edl.norm(text)
        x = {"a": t, "b": t + d, "text": text, "n": n, "k": edl.key(n), "chars": []}
        t += d + 0.5
        return x
    cases = [  # (前一段, 时长, 后一段, 应该：None 不算重说／(类型, 剪不剪))
        ("这笔钱放在房", 0.8, "这笔钱放在存款里", ("改口", True)),
        ("先看利率再看期限", 1.6, "再看期限和条件", ("尾头重复", True)),
        ("想赌他下个月", 1.2, "想堵它下个月反弹", ("改口", True)),   # 同音错字：他／它、赌／堵
        ("比如说房子", 1.0, "比如说黄金", ("改口", False)),           # 排比，不剪
        ("今天我们聊聊黄金", 1.5, "先说结论", None),
    ]
    ok, bad = 0, []
    for a_, d, b_, want in cases:
        A, B = isl(a_, d), isl(b_, 1.5)
        hits = edl.find_retakes([A, B])
        got = (hits[0]["kind"], hits[0]["cut"]) if hits else None
        if got == want:
            ok += 1
        else:
            bad.append(f"「{a_}」→「{b_}」应该 {want}，实际 {got}")
    f, ot, nt = mapper([[0, 5], [6, 10]], [[0, 5], [7, 10]])
    for v, want in ((2, 2.0), (5.5, 5.0), (8, 7.0), (9.5, 8.5)):  # 落进新剪掉那段的贴到下一段开头；落版跟着片尾平移
        if abs(f(v) - want) < 1e-6:
            ok += 1
        else:
            bad.append(f"时间搬移 {v} 应该到 {want}，实际 {f(v)}")
    return ok, len(cases) + 4, bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--style", choices=STYLES)
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "ifa-tujie-selftest"))
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--plan", default="all", help="examples/demo 里的哪份分镜表：demo／variants／all（默认全跑）")
    a = ap.parse_args()
    OUT = os.path.abspath(a.out)
    A = os.path.join(OUT, "assets")
    os.makedirs(A, exist_ok=True)
    print(f"自检目录：{OUT}")
    lk_ok, lk_n, lk_bad = logic_checks()
    print(f"[剪辑逻辑] 找重说判定和重剪时间搬移：{lk_ok}/{lk_n} 通过" + "".join("\n  ✗ " + b for b in lk_bad))
    geom = make_media(os.path.join(A, "demo"))
    json.dump(geom, open(os.path.join(OUT, "geom.json"), "w"))
    for sub, src in (("fonts", os.path.join(ROOT, "assets", "fonts")), ("tex", os.path.join(ROOT, "assets", "textures"))):
        shutil.copytree(src, os.path.join(A, sub), dirs_exist_ok=True)
    assets = {"aroll": "assets/demo/aroll.mp4", "band_demo": "assets/demo/band_demo.mp4", "bg_demo": "assets/demo/bg_demo.jpg",
              "font_sm": "assets/fonts/SmileySans-Oblique.otf", "font_en": "assets/fonts/Inter.ttf", "font_num": "assets/fonts/Oswald.ttf",
              "font_sr": "assets/fonts/ZCOOLXiaoWei-Regular.ttf", "font_br": "assets/fonts/ZhiMangXing-Regular.ttf",
              "tex_stone": "assets/tex/stone.jpg", "tex_archive": "assets/tex/archive.jpg"}
    for k in (1, 2, 3):
        assets[f"thumb_demo{k}"] = f"assets/demo/thumb_demo{k}.jpg"
    sfx_src = os.path.join(ROOT, "assets", "sfx")
    if os.path.isdir(sfx_src):
        shutil.copytree(sfx_src, os.path.join(A, "sfx_style"), dirs_exist_ok=True)
        for st_ in os.listdir(sfx_src):
            for f in os.listdir(os.path.join(sfx_src, st_)):
                if f.endswith(".mp3"):
                    assets[f"sfx_{st_}_{f[:-4]}"] = f"assets/sfx_style/{st_}/{f}"
    from prep import SFX_DIR, SFX
    if os.path.isdir(SFX_DIR):
        os.makedirs(os.path.join(A, "sfx"), exist_ok=True)
        for s in SFX:
            p = os.path.join(SFX_DIR, s + ".mp3")
            if os.path.exists(p):
                shutil.copy(p, os.path.join(A, "sfx"))
                assets[f"sfx_{s}"] = f"assets/sfx/{s}.mp3"
    have_om = os.path.exists(os.path.join(om.om_home(), "install.json"))
    if have_om:
        g = os.path.join(om.install()["appRoot"], "node_modules", "gsap", "dist", "gsap.min.js")
        if os.path.exists(g):
            shutil.copy(g, os.path.join(A, "gsap.min.js"))
    json.dump(assets, open(os.path.join(OUT, "assets.json"), "w"), indent=1)
    demo = os.path.join(ROOT, "examples", "demo")
    for f in os.listdir(demo):
        if f.startswith(("captions_", "cuts_")):
            shutil.copy(os.path.join(demo, f), OUT)
    srcs = {f[5:-5]: os.path.join(demo, f) for f in os.listdir(demo) if f.startswith("plan_") and f.endswith(".json")}
    if a.plan in ("all", "draft"):  # 自动出分镜表草稿，再构建一遍
        dp = os.path.join(OUT, "plan_draft_src.json")
        r = subprocess.run([sys.executable, os.path.join(HERE, "draft_plan.py"), "--captions", os.path.join(OUT, "captions_demo.json"),
                            "--style", "tanjin", "--title", "示例｜自动草稿", "--host", "主讲人", "--badge", "主讲人,示例", "--duration", str(DUR),
                            "--aroll-duration", str(DUR), "--out", dp, "--fill-placeholders", "band=band_demo,thumb=thumb_demo1,tile=band_demo"],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            srcs["draft"] = dp
        else:
            print("✗ 草稿生成失败：" + (r.stdout + r.stderr)[-500:])
    names = sorted(srcs) if a.plan == "all" else [a.plan]
    results = []
    for pn in names:
        plan0 = json.load(open(srcs[pn], encoding="utf-8"))
        for st in ([a.style] if a.style else STYLES):
            plan = dict(plan0, style=st, title=f"{plan0['title']}·{st}")
            tag = st if pn == "demo" else f"{st}_{pn}"
            pp = os.path.join(OUT, f"plan_{tag}.json")
            json.dump(plan, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
            d = os.path.join(OUT, tag)
            shutil.rmtree(d, ignore_errors=True)
            r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), pp, "--assets", os.path.join(OUT, "assets.json"),
                                "--geom", os.path.join(OUT, "geom.json"), "--out", d], capture_output=True, text=True, encoding="utf-8")
            ok_build = r.returncode == 0
            line = (r.stdout.strip().splitlines() or ["?"])[-1] if ok_build else (r.stdout + r.stderr)[-600:]
            lint = "跳过（没装 OpenMotion）"
            if ok_build and have_om:
                om.link_dir(A, os.path.join(d, "assets"))
                json.dump({"paths": {"blocks": "compositions", "assets": "assets"}}, open(os.path.join(d, "hyperframes.json"), "w"))
                lr = subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "lint", "--dir", d], capture_output=True, text=True, encoding="utf-8")
                lint = (lr.stdout.strip().splitlines() or ["?"])[0]
                cr = subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "check", "--dir", d], capture_output=True, text=True, encoding="utf-8")
                lint += "；" + (cr.stdout.strip().splitlines() or ["?"])[0]
                if cr.returncode:
                    ok_build = False
                    lint += "\n" + "\n".join(cr.stdout.strip().splitlines()[1:6])
                sr = subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "safe", "--dir", d], capture_output=True, text=True, encoding="utf-8")
                lint += "；" + (sr.stdout.strip().splitlines() or ["?"])[0]
                if sr.returncode:
                    ok_build = False
                    lint += "\n" + "\n".join(sr.stdout.strip().splitlines()[1:6])
                if a.snapshot and lr.returncode == 0:
                    sd = os.path.join(OUT, f"snap_{tag}")
                    ats = "2.5,6.5,12.5,17.5,24,29,33.8,39" if pn == "demo" else "3.2,8.8,14.5,18.6,25.2,31.0,36.8,41.5"
                    subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "snapshot", "--dir", d, "--at", ats, "--out", sd],
                                 capture_output=True, text=True)
                    lint += f"；抽帧 → {sd}"
            results.append((tag, ok_build, line, lint))
    print()
    for st, okb, line, lint in results:
        print(f"[{st}] 构建：{'✓' if okb else '✗'} {line}\n         检查：{lint}")
    print(f"[剪辑逻辑] {lk_ok}/{lk_n} 通过")
    if lk_bad:
        sys.exit("剪辑逻辑自检没通过，见上面")
    if not all(r[1] for r in results):
        sys.exit("有风格构建失败，见上面的错误")


if __name__ == "__main__":
    main()
