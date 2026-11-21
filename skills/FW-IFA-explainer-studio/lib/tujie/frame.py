# -*- coding: utf-8 -*-
"""全片骨架：图解段背景、母题纹样、底座（章节进度条＋补充信息卡＋署名牌）、字幕层、音效、index.html。
五套风格共用这一份结构，只换 CSS。"""
import json, os
from .core import W, H, HOST_H, CAP_Y, ZOOM, esc, icon, stamp_ids, drift

SFX_FILES = {
    "soft": ("transition-soft", 0.28), "snap": ("transition-snap", 0.16), "swoosh": ("swoosh-quick", 0.20),
    "whoosh": ("whoosh-fast", 0.18), "impact": ("impact-cine", 0.26), "click": ("click-camera", 0.22),
}


# ---------------------------------------------------------------- 图解段背景
def motif_pattern(film, seg, opacity=1.0, size=58, gap=150, rot=-12):
    """母题纹样：从本片的母题图标里取，铺成斜向网格，慢慢漂移。每支片按内容换图标，所以同风格的片子底纹不一样。"""
    names = film.motif or ["circle-dollar-sign", "trending-up"]
    cells = []
    k = 0
    for row in range(-1, 14):
        for col in range(-1, 8):
            x = col * gap + (gap / 2 if row % 2 else 0)
            y = row * gap
            cells.append(f'<div class="ab" style="left:{x:.0f}px;top:{y:.0f}px">{icon(names[k % len(names)], size, "currentColor", 1.6)}</div>')
            k += 1
    return (f'<div id="{seg.id}-motif" class="ab motifc" style="left:-200px;top:-200px;width:1500px;height:2400px;opacity:{opacity};transform:rotate({rot}deg)">'
            + "".join(cells) + "</div>")


def graphic_bg(film, seg, photo=None, dim=None, pattern=None):
    """按风格铺图解段背景。photo 是素材键（图片或视频），pattern=True 时铺母题纹样。"""
    st = film.st.key
    body = '<div class="bgbase"></div>'
    script = ""
    photo = photo or seg.bg
    if photo:
        is_video = film.a(photo).lower().endswith((".mp4", ".mov", ".webm"))
        filt = {"dangan": "grayscale(.35) sepia(.35) brightness(.6)", "kuangshi": "grayscale(.5) brightness(.55)",
                "cilan": "saturate(.8) brightness(.75)", "nihong": "saturate(1.1) brightness(.6)"}.get(st, "brightness(.7)")
        d0 = {"tanjin": .38, "dangan": .32, "kuangshi": .42, "cilan": .35, "nihong": .4}[st] if dim is None else dim
        if is_video:
            body += (f'<video id="{seg.id}-bg" class="clip" data-start="0" data-duration="{seg.d:.3f}" src="{film.a(photo)}" muted playsinline '
                     f'style="position:absolute;left:-60px;top:-60px;width:1200px;height:2040px;object-fit:cover;filter:{filt}"></video>')
        else:
            body += (f'<div id="{seg.id}-bg" class="ab" style="left:-60px;top:-60px;width:1200px;height:2040px;'
                     f'background:url(\'{film.a(photo)}\') center/cover;filter:{filt}"></div>')
        body += f'<div class="ab" style="inset:0;background:rgba(0,0,0,{d0})"></div>'
        script += drift(f"#{seg.id}-bg", seg.d)
    if pattern is None:
        pattern = st in ("cilan", "nihong") and not photo
    if pattern:
        body += motif_pattern(film, seg)
        script += f'tl.fromTo("#{seg.id}-motif",{{y:0}},{{y:-150,duration:{seg.d:.2f},ease:"none"}},0);\n'
    body += '<div class="vig"></div>'
    if st in ("tanjin", "dangan"):
        body += '<div class="grain"></div>'
    return body, script


def band(film, seg, key, y, h=608, name="band", start=0.0, dur=None, edge=True):
    """素材横条（16:9 实拍放在画面中上部）。"""
    dur = seg.d - start if dur is None else dur
    fade = ('<div class="ab" style="inset:0;background:linear-gradient(180deg,rgba(0,0,0,.45),rgba(0,0,0,0) 18%,rgba(0,0,0,0) 80%,rgba(0,0,0,.75))"></div>'
            if edge else "")
    src = film.a(key)
    media = (f'<video id="{seg.id}-{name}" class="clip" data-start="{start:.3f}" data-duration="{dur:.3f}" src="{src}" muted playsinline '
             f'style="position:absolute;left:0;top:0;width:1080px;height:{h}px;object-fit:cover"></video>'
             if src.lower().endswith((".mp4", ".mov", ".webm")) else
             f'<div class="ab" style="inset:0;background:url(\'{src}\') center/cover"></div>')
    return f'<div id="{seg.id}-{name}w" class="ab" style="left:0;top:{y}px;width:1080px;height:{h}px;overflow:hidden">{media}{fade}</div>'


# ---------------------------------------------------------------- 底座
DOCK_LAYOUT_CSS = """
.chap{position:absolute;left:44px;right:44px;top:1652px;height:110px}
.chap .it{position:absolute;top:0;height:100px;text-align:center}
.chap .on{position:absolute;left:0;top:0;width:100%;opacity:0}
.chap .u,.chap .ud{position:absolute;left:30px;right:30px;top:86px;height:3px;border-radius:2px}
.chap .ud{transform-origin:0 50%;transform:scaleX(0)}
.upd{position:absolute;left:36px;right:36px;top:1626px;height:176px;opacity:0}
.upd .lab{position:absolute;left:30px;top:26px;display:flex;align-items:center;gap:12px;font:400 30px/1 SM}
.upd .dot{width:14px;height:14px;border-radius:50%}
.upd .lab small{font:600 15px/1 EN,Inter,sans-serif;letter-spacing:4px;opacity:.75}
.upd .ti{position:absolute;left:30px;top:74px;font-size:44px;line-height:1.1;white-space:nowrap}
.upd .nt{position:absolute;left:30px;top:134px;font:600 17px/1 EN,Inter,sans-serif;letter-spacing:2px;color:rgba(255,255,255,.42)}
.upd .sts{position:absolute;right:28px;top:30px;display:flex;gap:14px}
.upd .st{width:136px;height:116px;border-radius:12px;text-align:center;padding-top:18px}
.upd .sl{font:400 20px/1 SM;color:rgba(255,255,255,.55)}
.upd .sv{font-size:44px;line-height:1;margin-top:14px}
.upd .up{color:#6CEBB4 !important}.upd .down{color:#FF7A70 !important}
"""


def dock(film):
    p = film.plan
    ch = p.get("chapters") or [[0, p.get("title", "")]]
    n = len(ch)
    span = (W - 88) / n
    items, script = "", ""
    for k, (t0, nm) in enumerate(ch):
        items += (f'<div id="dk-i{k}" class="it" style="left:{k * span:.0f}px;width:{span - 8:.0f}px"><div class="n">{k + 1:02d}</div><div class="l">{esc(nm)}</div>'
                  f'<div id="dk-on{k}" class="on"><div class="n">{k + 1:02d}</div><div class="l">{esc(nm)}</div></div>'
                  f'<div class="u"></div><div id="dk-ud{k}" class="ud"></div></div>')
        script += (f'tl.fromTo("#dk-on{k}",{{opacity:0}},{{opacity:1,duration:0.35}},{t0 + 0.05:.2f});\n'
                   f'tl.fromTo("#dk-ud{k}",{{scaleX:0}},{{scaleX:1,duration:0.5,ease:"power3.out"}},{t0 + 0.05:.2f});\n')
        if k > 0:
            script += f'tl.to("#dk-on{k - 1}",{{opacity:0.55,duration:0.35}},{t0 + 0.05:.2f});\n'
    ups = ""
    for i, u in enumerate(p.get("updates", [])):
        stats = "".join(
            f'<div class="st"><div class="sl">{esc(s[0])}</div><div class="sv {s[2] if len(s) > 2 else ""}">{esc(s[1])}</div></div>'
            for s in u.get("stats", [])[:2])
        ups += (f'<div id="dk-up{i}" class="upd"><div class="lab"><span class="dot"></span>{esc(u.get("label", "最新进展"))}'
                f'<small>{esc(u.get("label_en", "LATEST"))}</small></div>'
                f'<div class="ti">{esc(u["title"])}</div><div class="nt">{esc(u.get("note", ""))}</div><div class="sts">{stats}</div></div>')
        a0, a1 = float(u["start"]), float(u["end"])
        script += (f'tl.to("#dk-chap",{{opacity:0,duration:0.25}},{a0:.2f});\n'
                   f'tl.fromTo("#dk-up{i}",{{opacity:0,y:40}},{{opacity:1,y:0,duration:0.4,ease:"back.out(1.5)"}},{a0:.2f});\n'
                   f'tl.to("#dk-up{i}",{{opacity:0,duration:0.25}},{a1 - 0.3:.2f});\n'
                   f'tl.to("#dk-chap",{{opacity:1,duration:0.3}},{a1 - 0.05:.2f});\n')
        film.sfx.append((a0, "click", None))
    host = p.get("host", {})
    b = host.get("badge") or [host.get("name", ""), ""]
    body = (f'<div class="dk"></div><div class="dkg"></div>'
            f'<div id="dk-chap" class="chap">{items}</div>{ups}'
            f'<div class="rule"></div><div id="dk-badge" class="badge">{esc(b[0])}<b>{esc(b[1]) if len(b) > 1 else ""}</b></div>')
    film.scene("dock", body, script, DOCK_LAYOUT_CSS)


# ---------------------------------------------------------------- 字幕
def sg_of(film, t):
    for s in film.segs:
        if s.start - 0.01 <= t < s.end:
            return s
    return None


def place_caption(seg, text, y):
    """字幕和小窗相撞时让开：小窗在左（右）就挪到右（左）边剩下的空间居中；小窗居中就放到小窗上方。"""
    from .core import tw
    pr = getattr(seg, "pip_rect", None) if seg else None
    w = min(980, tw(text) * 61 + 24)
    if not pr:
        return f"top:{y}px"
    px, py, pw, ph = pr
    if not (y < py + ph and y + 76 > py and 540 - w / 2 < px + pw and 540 + w / 2 > px):
        return f"top:{y}px"
    if px + pw < 430:
        avail = W - 50 - (px + pw + 16)
        if avail >= w * 0.74:
            fs = min(60, int(60 * avail / w))
            return f"top:{y}px;left:{px + pw + 16:.0f}px;right:50px;font-size:{fs}px"
    if px > 650:
        avail = px - 16 - 50
        if avail >= w * 0.74:
            fs = min(60, int(60 * avail / w))
            return f"top:{y}px;left:50px;right:{W - px + 16:.0f}px;font-size:{fs}px"
    ny = py - 88
    if ny < 260:
        ny = py + ph + 14
    return f"top:{ny:.0f}px"


def caption_keywords(film):
    """字幕里要变色的词：plan.keywords ＋ 分镜表各段文字里用 *…* 标出的重点词。"""
    import re as _re
    kws = set(film.plan.get("keywords", []))

    def walk(v):
        if isinstance(v, str):
            kws.update(w for w in _re.findall(r"\*(.+?)\*", v) if 1 < len(w) <= 8)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for s in film.segs:
        walk(s.data)
    return sorted(kws, key=len, reverse=True)


def mark(text, kws):
    out = esc(text)
    for w in kws:
        ew = esc(w)
        if ew in out and f'>{ew}<' not in out:
            out = out.replace(ew, f'<span class="hl">{ew}</span>', 1)
    return out


def captions(film):
    caps = film.plan.get("_captions", [])
    kws = caption_keywords(film)
    skip = film.plan.get("caption_skip", [])
    slots = []
    for s in film.segs:
        y = getattr(s, "cap_y_set", None) or s.cap_y or CAP_Y
        slots.append((s.start, s.end, y, s))
    groups, cs = "", ""
    for k, c in enumerate(caps):
        s0, s1 = float(c["start"]), float(c["end"])
        if any(a <= s0 < b for a, b in skip):
            continue
        y = CAP_Y
        for a, b, yy, sg in slots:
            if a - 0.01 <= s0 < b:
                y = yy
                if getattr(sg, "no_caption", False):
                    y = None
                break
        if y is None:
            continue
        gid = f"cp{k}"
        pos = place_caption(sg_of(film, s0), c["text"], y)
        groups += f'<div id="{gid}" class="cap" style="{pos}">{mark(c["text"], kws)}</div>'
        cs += (f'tl.fromTo("#{gid}",{{opacity:0,y:8}},{{opacity:1,y:0,duration:0.12,ease:"power2.out"}},{s0:.3f});\n'
               f'tl.to("#{gid}",{{opacity:0,duration:0.08}},{max(s0 + 0.15, s1 - 0.08):.3f});\n'
               f'tl.set("#{gid}",{{visibility:"hidden"}},{s1:.3f});\n')
    css = ".cap{position:absolute;left:50px;right:50px;text-align:center;font:400 60px/1.2 SM;color:#fff;letter-spacing:1px;opacity:0}"
    film.scene("captions", groups, cs, css)


# ---------------------------------------------------------------- index.html
def index(film, hosts_order):
    p = film.plan
    sfx_dir_keys = {k: f"sfx_{v[0]}" for k, v in SFX_FILES.items()}
    tags = ""
    for k, (t, kind, vol) in enumerate(sorted(film.sfx)):
        key = sfx_dir_keys.get(kind)
        if not key or not film.has(key) or t < 0 or t > film.dur - 0.3:
            continue
        v = vol if vol is not None else SFX_FILES[kind][1]
        tags += (f'<audio id="sfx{k}" class="clip" data-start="{t:.3f}" data-duration="1.8" data-track-index="{30 + k % 4}" '
                 f'data-volume="{v}" src="{film.a(key)}"></audio>\n')
    hosts = ""
    for cid, s0, s1, tr, z, kind in hosts_order:
        hosts += (f'<div id="{cid}" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="{s0:.3f}" '
                  f'data-duration="{s1 - s0:.3f}" data-track-index="{tr}" data-track-kind="{kind}" data-width="1080" data-height="1920" style="z-index:{z}"></div>\n')
    # 跳切推近：只在人物段，按剪辑点交替 1.0 / 1.08
    cuts = p.get("_cuts", [])
    zs = 'tl.set("#hostzoom",{scale:1},0);\n'
    flip = 0
    for s in film.segs:
        if s.kind != "host":
            continue
        marks = [s.start] + [c for c in cuts if s.start + 0.3 < c < s.end - 0.25]
        for m in marks:
            flip ^= 1
            sc = (ZOOM if flip else 1.0) if s.zoom else 1.0
            zs += f'tl.set("#hostzoom",{{scale:{sc}}},{m:.3f});\n'
    ox, oy = film.zoom_origin()
    voice = (f'<audio id="voice" class="clip" data-start="0" data-duration="{film.aroll_dur}" data-track-index="20" '
             f'data-volume="{p.get("voice_volume", 0.79)}" src="{film.a("voice")}"></audio>' if film.has("voice") else "")
    bgm = (f'<audio id="bgm" class="clip" data-start="0" data-duration="{film.dur}" data-track-index="21" data-volume="1" src="{film.a("bgm")}"></audio>'
           if film.has("bgm") else "")
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{esc(film.title)}</title>
<script src="assets/gsap.min.js"></script>
<style>
body{{margin:0;background:#000}}
#main{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#070707}}
#hostwrap{{position:absolute;left:0;top:0;width:1080px;height:{HOST_H}px;overflow:hidden;z-index:1}}
#hostzoom{{position:absolute;left:0;top:0;width:1080px;height:1920px}}
#aroll{{position:absolute;left:0;top:0;width:1080px;height:1920px}}
#hostscrim{{position:absolute;left:0;top:1120px;width:1080px;height:{HOST_H - 1120}px;background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.36))}}
</style></head>
<body>
<div id="main" data-composition-id="main" data-start="0" data-duration="{film.dur}" data-width="1080" data-height="1920" data-fps="30">
<div id="hostwrap"><div id="hostzoom">
<video id="aroll" class="clip" data-start="0" data-duration="{film.aroll_dur}" data-track-index="0" src="{film.a('aroll')}" muted playsinline></video>
</div><div id="hostscrim"></div></div>
{voice}
{bgm}
{tags}{hosts}</div>
<script>
const tl = gsap.timeline({{paused:true}});
tl.set("#hostzoom",{{transformOrigin:"{ox}px {oy}px"}},0);
{zs}tl.to({{}},{{duration:{film.dur}}},0);
window.__timelines = window.__timelines || {{}};
window.__timelines.main = tl;
</script>
</body></html>
"""
    open(os.path.join(film.out, "index.html"), "w", encoding="utf-8").write(stamp_ids(html, "main"))
