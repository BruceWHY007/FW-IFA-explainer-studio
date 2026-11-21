# -*- coding: utf-8 -*-
"""自动出封面：取成片里的一帧人物画面，按本片风格的字和材质压标题，出 9:16（1080×1920）和 3:4（1080×1440，视频号／小红书）两张。
标题按实测头顶放在人物头顶上方；头顶空间不够时把人物画面整体下移、上方铺本风格底色，绝不压脸。

用法：python cover.py plan.json --assets assets.json --geom geom.json --stage 已 stage 的工程目录 --video 剪好的人物视频.mp4 --out 封面目录
plan.json 里可以写（不写就用片名）：
  "cover": {"title": "Claude|*又要上市了*", "sub": "AI公司，真的这么赚钱吗？", "t": 2.0, "tag": "第 1 期"}
  title 里 | 换行、*…* 强调色；t 是取人物画面的时间（选眼睛睁开、表情好的一帧）。
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, HERE)
from tujie.core import Film, esc, fit_fs, rich, tw  # noqa: E402
import om  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan"); ap.add_argument("--assets", required=True); ap.add_argument("--geom", required=True)
    ap.add_argument("--stage", required=True); ap.add_argument("--video", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    plan["segments"] = plan.get("segments", [])
    assets = json.load(open(a.assets, encoding="utf-8"))
    geom = json.load(open(a.geom, encoding="utf-8"))
    cv = plan.get("cover", {})
    title = cv.get("title") or plan["title"].split("｜")[-1]
    sub = cv.get("sub", "")
    t = float(cv.get("t", 1.0))
    os.makedirs(a.out, exist_ok=True)
    cs = os.path.join(a.out, "_stage")
    shutil.rmtree(cs, ignore_errors=True)
    os.makedirs(os.path.join(cs, "compositions"), exist_ok=True)
    om.link_dir(os.path.abspath(os.path.join(a.stage, "assets")), os.path.join(cs, "assets"))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", a.video, "-frames:v", "1", "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-q:v", "2", os.path.join(cs, "cover_host.jpg")], check=True)
    film = Film(plan, assets, geom, cs)
    st = film.st.bind(film)
    fr = min((f for f in geom["frames"] if f.get("face")), key=lambda f: abs(f["t"] - t))
    fx, fy, fw, fh = fr["face"]
    head = fr.get("head_top") or (fy - 0.6 * fh)
    chin = fy + fh
    lines = title.split("|")
    fs = min(150, fit_fs(max(lines, key=tw), 960, 150, 60))
    need = (84 if cv.get("tag") else 0) + len(lines) * fs * 1.08 + (84 if sub else 0)
    s = 1.06
    cx, cy = fx + fw / 2, fy + fh / 2
    top_after_zoom = cy + (head - cy) * s
    avail = top_after_zoom - 40 - 110
    # 头顶放不下标题时，把人物画面整体下移，上方铺本风格底色，照片上沿渐隐过去；标题始终在头顶、不压脸
    dy = int(min(560, max(0, need - avail + 30)))
    y0 = 110 + max(0, (avail + dy - need) / 2)
    cls = ["T2", "T1"] if len(lines) > 1 else ["T1"]
    html_lines = "".join(f'<div class="{cls[min(k, len(cls) - 1)]}" style="font-size:{fs}px;line-height:1.08;letter-spacing:4px;white-space:nowrap">{rich(ln)}</div>'
                         for k, ln in enumerate(lines))
    subh = f'<div style="margin-top:22px;font:400 52px/1.1 SM;color:{st.sub_color()};text-shadow:0 2px 8px rgba(0,0,0,.8)">{rich(sub)}</div>' if sub else ""
    host = plan.get("host", {})
    b = host.get("badge") or [host.get("name", ""), ""]
    tag = f'<div class="tag" style="position:relative;display:inline-block;margin-bottom:22px">{esc(cv["tag"])}</div><br>' if cv.get("tag") else ""
    mask = f"-webkit-mask:linear-gradient(180deg,transparent 0,#000 {min(260, dy + 40)}px);" if dy else ""
    body = ('<div class="bgbase"></div>'
            f'<img src="cover_host.jpg" style="position:absolute;left:0;top:{dy}px;width:1080px;height:1920px;transform-origin:{cx:.0f}px {cy:.0f}px;transform:scale({s});{mask}">'
            f'<div class="ab" style="left:0;right:0;top:0;height:{int(top_after_zoom + dy + 60)}px;background:linear-gradient(180deg,rgba(6,8,12,.85),rgba(6,8,12,.5) 55%,rgba(6,8,12,0))"></div>'
            f'<div class="ab" style="left:60px;right:60px;top:{y0:.0f}px;text-align:center">{tag}{html_lines}{subh}</div>'
            f'<div class="badge" style="top:1350px">{esc(b[0])}<b>{esc(b[1]) if len(b) > 1 else ""}</b></div>')
    zone = "top"
    css = (film.base_css() + st.css + ".ab{position:absolute}.tag{position:relative}"
           "html,body{margin:0;background:#000}#main{position:relative;width:1080px;height:1920px;overflow:hidden}")
    index = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>封面</title>
<script src="assets/gsap.min.js"></script><style>{css}</style></head><body>
<div id="main" data-composition-id="main" data-start="0" data-duration="1" data-width="1080" data-height="1920" data-fps="30">{body}</div>
<script>const tl = gsap.timeline({{paused:true}}); tl.to({{}},{{duration:1}},0); window.__timelines = window.__timelines || {{}}; window.__timelines.main = tl;</script>
</body></html>"""
    open(os.path.join(cs, "index.html"), "w", encoding="utf-8").write(index)
    json.dump({"paths": {"blocks": "compositions", "assets": "assets"}}, open(os.path.join(cs, "hyperframes.json"), "w"))
    snap = os.path.join(cs, "_snap")
    r = subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "snapshot", "--dir", cs, "--at", "0.5", "--out", snap], capture_output=True, text=True)
    pngs = sorted(f for f in os.listdir(snap) if f.startswith("frame-")) if os.path.isdir(snap) else []
    if not pngs:
        sys.exit("封面渲染失败：" + (r.stdout + r.stderr)[-800:])
    from PIL import Image
    im = Image.open(os.path.join(snap, pngs[0])).convert("RGB")
    p916 = os.path.join(a.out, "cover_9x16.jpg")
    p34 = os.path.join(a.out, "cover_3x4.jpg")
    im.save(p916, quality=92)
    im.crop((0, 0, 1080, 1440)).save(p34, quality=92)
    print(f"封面（标题在头顶{'，人物下移 ' + str(dy) + 'px 给标题留空间' if dy else ''}）：{p916}\n      {p34}")


if __name__ == "__main__":
    main()
