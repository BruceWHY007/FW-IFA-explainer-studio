# -*- coding: utf-8 -*-
"""自检：不用任何真人视频，生成占位素材（灰色人形剪影、渐变横条、配图），按 examples/demo 的分镜表把五套风格各构建一遍，
有 OpenMotion 时再跑 lint 和抽帧。装完环境、改完代码都可以跑它确认链路通。

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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--style", choices=STYLES)
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "ifa-tujie-selftest"))
    ap.add_argument("--snapshot", action="store_true")
    a = ap.parse_args()
    OUT = os.path.abspath(a.out)
    A = os.path.join(OUT, "assets")
    os.makedirs(A, exist_ok=True)
    print(f"自检目录：{OUT}")
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
    for f in ("captions_demo.json", "cuts_demo.json"):
        shutil.copy(os.path.join(demo, f), OUT)
    plan0 = json.load(open(os.path.join(demo, "plan_demo.json"), encoding="utf-8"))
    results = []
    for st in ([a.style] if a.style else STYLES):
        plan = dict(plan0, style=st, title=f"{plan0['title']}·{st}")
        pp = os.path.join(OUT, f"plan_{st}.json")
        json.dump(plan, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
        d = os.path.join(OUT, st)
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
            if a.snapshot and lr.returncode == 0:
                sd = os.path.join(OUT, f"snap_{st}")
                subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "snapshot", "--dir", d, "--at", "2.5,6.5,12.5,17.5,24,29,33.8,39", "--out", sd],
                               capture_output=True, text=True)
                lint += f"；抽帧 → {sd}"
        results.append((st, ok_build, line, lint))
    print()
    for st, okb, line, lint in results:
        print(f"[{st}] 构建：{'✓' if okb else '✗'} {line}\n         检查：{lint}")
    if not all(r[1] for r in results):
        sys.exit("有风格构建失败，见上面的错误")


if __name__ == "__main__":
    main()
