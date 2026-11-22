# -*- coding: utf-8 -*-
"""图解段版式（全屏，盖住人物画面，人物在小窗里）。排版只用 0–1576 这一区，底座常驻在下面。
每个版式读 seg.data；时间写全片秒数（t、t1…），没写的按段长均分。
变化来源：①风格的材质和入场动作 ②本片母题图标 ③film.rng(seg) 决定镜像、倾斜方向、入场方向 ④data 里的内容本身（条数、数值、配图）。
"""
import math
from .core import W, HOST_H, CAP_Y, BuildError, chars, chars_in, drift, esc, plain, rich, fit_fs, floaty, icon, lcg, pip, pip_in, sway, tw, BG_END, BLEED_W, BLEED_X
from .frame import band, grade_cls, grade_ov, graphic_bg, motif_pattern
from .styles import brush_in

NOTE = "示意 · ILLUSTRATIVE"
# 平台安全区：背景之后的元素整体缩到 93% 落进安全区（core.Film.scene），所以元素要排在设计区 x 24–1056、y 150–1440 里；
# 要铺满全宽的横条、滚动条、光带用 BLEED_X／BLEED_W；从屏幕边伸进来的装饰色块加 data-safe-bleed（留在缩放层外面）。


# ---------------------------------------------------------------- 公共件
def header(film, seg, zh, en, top=170, fs=None):
    fs = fs or (84 if tw(zh) <= 9 else fit_fs(zh, 960, 76, 48))
    seg.header_box = (540 - tw(zh) * fs / 2 - 20, top, tw(zh) * fs + 40, fs * 1.1 + 70)
    return (f'<div id="{seg.id}-head" class="head" style="top:{top}px"><div class="orn"><i></i><s></s><i class="r"></i></div>'
            f'<h2 style="font-size:{fs}px">{rich(zh)}</h2><p>{rich(en)}</p></div>')


def head_in(film, seg, t=0.05):
    return f'tl.fromTo("#{seg.id}-head",{{opacity:0,y:-24}},{{opacity:1,y:0,duration:0.45,ease:"power3.out"}},{t});\n'


def pip_spec(film, seg, default):
    """小窗参数：data.pip 覆盖版式默认值。default=(shape, x, y, w, h)。"""
    p = seg.data.get("pip", {})
    if p is False or seg.data.get("no_pip"):
        return None
    shape, x, y, w, h = default
    return (p.get("shape", shape), p.get("x", x), p.get("y", y), p.get("w", p.get("size", w)), p.get("h", p.get("size", h)))


def put_pip(film, seg, spec, t=0.25, amp=9):
    if not spec:
        return "", ""
    shape, x, y, w, h = spec
    hb = getattr(seg, "header_box", None)
    if hb and x < hb[0] + hb[2] and x + w > hb[0] and y < hb[1] + hb[3] and y + h > hb[1]:
        room = (x - 20 - 40) if x + w / 2 > W / 2 else (W - 40 - (x + w + 20))
        if hb[2] <= room:  # 标题挪到小窗另一侧那块空地里居中
            film.head_shift[seg.id] = ("right", W - x + 20) if x + w / 2 > W / 2 else ("left", x + w + 20)
        else:
            y = hb[1] + hb[3] + 14  # 放不下：小窗挪到标题下面
    seg.pip_rect = (x, y - amp, w, h + 2 * amp)
    return pip(film, seg, shape, x, y, w, h), pip_in(seg, t) + floaty(f"#{seg.id}-pipwf", seg.d, amp, 3.6, 0.0)


def style_pip(film, seg, region="free"):
    """各风格的默认小窗：炭金左下大圆、档案右上白边圆、矿石居中圆角方、瓷蓝左上圆、霓虹左下竖窗。"""
    k = film.st.key
    if k == "tanjin":
        return ("circle", 30, 980, 290, 290)
    if k == "dangan":
        return ("circle", W - 36 - 250, 162, 250, 250)
    if k == "kuangshi":
        return ("squircle", (W - 270) / 2, 1140, 270, 270)
    if k == "cilan":
        return ("circle", 36, 162, 230, 230)
    return ("rect", 30, 1040, 240, 300)


def card_img(seg_id, x, y, w, h, zh, en, img, num="", fs=56):
    numh = f'<div class="ab k" style="left:34px;top:{h / 2 - 60:.0f}px">{num}</div>' if num else ""
    tx = 150 if num else 40
    nl = zh.count("|") + 1
    iw = w * 0.44 if img else 0  # 缩略图宽；渐隐到 28% 处已经半透明，字最多写到这里
    fs = min(fs, fit_fs(max(zh.split("|"), key=tw), w - tx - (iw * 0.72 + 12 if img else 30), fs, 28))  # 按可用宽度缩字号，不换行
    ty = h / 2 - (nl * fs * 1.1 + 30) / 2
    ey = ty + nl * fs * 1.1 + 12
    imgh = (f'<div class="ab grade" style="right:0;top:0;width:{iw:.0f}px;height:100%;background:url(\'{img}\') center/cover;'
            f'-webkit-mask:linear-gradient(90deg,transparent,#000 60%);opacity:.9"></div>') if img else ""
    return (f'<div id="{seg_id}f" class="fl" style="left:{x:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h:.0f}px">'
            f'<div id="{seg_id}" class="card" style="left:0;top:0;width:{w:.0f}px;height:{h:.0f}px">{imgh}'
            f'<div class="dash"></div><div id="{seg_id}-g" class="glow"></div>{numh}'
            f'<div class="ab t" style="left:{tx}px;top:{ty:.0f}px;font-size:{fs}px;white-space:nowrap;text-shadow:0 2px 12px rgba(0,0,0,.35)">{rich(zh)}</div>'
            f'<div class="ab e" data-layout-allow-overlap style="left:{tx + 2}px;top:{ey:.0f}px;margin:0">{rich(en)}</div></div></div>')


def lightup(seg, ids, times, dim=0.42):
    """依次点亮：当前项亮＋发光，上一项回到半亮。"""
    s = ""
    for k, (i, t) in enumerate(zip(ids, times)):
        s += f'tl.to("#{i}",{{opacity:1,duration:0.3}},{t:.3f});\ntl.fromTo("#{i}-g",{{opacity:0}},{{opacity:1,duration:0.3}},{t:.3f});\n'
        if k > 0:
            s += f'tl.to("#{ids[k - 1]}",{{opacity:{dim + 0.2},duration:0.3}},{t:.3f});\ntl.to("#{ids[k - 1]}-g",{{opacity:0,duration:0.3}},{t:.3f});\n'
    return s


def asset_or_none(film, key):
    return film.a(key) if key and film.has(key) else None


# ================================================================ 1 大字＋素材横条
def bigword_band(film, seg):
    """data: intro{zh,en}（先出的小标题，可选）, word, t（大字出现）, band（横条素材键）, ticker[词…], cls（T1/T2/TR）。"""
    d = seg.data
    st = film.st
    bg, bs = graphic_bg(film, seg)
    wt = seg.at("t", 0.9)
    fs = min(230, fit_fs(d["word"], 980, 230))
    body = bg
    s = bs
    if d.get("intro"):
        body += header(film, seg, d["intro"]["zh"], d["intro"]["en"], 200)
        s += head_in(film, seg) + f'tl.to("#{seg.id}-head",{{opacity:0,y:-20,duration:0.25,ease:"power2.in"}},{wt - 0.2:.3f});\n'
    rv = d.get("reveal") == "chars"
    wcls = d.get("cls", "T1")
    body += (f'<div id="{seg.id}-big" class="ab {"" if rv else wcls}" style="left:0;right:0;top:150px;text-align:center;font-size:{fs}px;line-height:1.1;letter-spacing:8px;opacity:0">'
             f'{chars(d["word"], wcls) if rv else rich(d["word"])}</div>')
    body += band(film, seg, d["band"], 470)
    tick = "&nbsp;&nbsp;·&nbsp;&nbsp;".join(rich(x) for x in (d.get("ticker") or ["MARKET", "VALUE", "GROWTH"]) * 4)
    body += (f'<div id="{seg.id}-tick" class="ab" data-layout-allow-overflow style="left:{BLEED_X:.0f}px;top:1100px;width:{BLEED_W:.0f}px;height:64px;border-top:1px solid rgba(255,255,255,.25);'
             f'border-bottom:1px solid rgba(255,255,255,.25);background:rgba(0,0,0,.45);overflow:hidden">'
             f'<div id="{seg.id}-ticktx" class="EN chip" data-layout-ignore data-safe-bleed style="position:absolute;left:0;top:21px;white-space:nowrap">{tick}</div></div>')
    shape = film.st.pip["shape"]
    spec = pip_spec(film, seg, (shape, 30, 860, 280 if shape != "rect" else 240, 280 if shape != "rect" else 300))
    ph, ps = put_pip(film, seg, spec)
    body += ph
    s += (f'tl.fromTo("#{seg.id}-bandw",{{opacity:0,y:50}},{{opacity:1,y:0,duration:0.5,ease:"power3.out"}},0);\n'
          + (chars_in(f"#{seg.id}-big", wt, len(plain(d["word"])), d.get("per") or film.reveal_per(d["word"], seg, 0.09)) if rv else st.title_in(f"#{seg.id}-big", wt))
          + f'tl.fromTo("#{seg.id}-tick",{{opacity:0}},{{opacity:1,duration:0.4}},0.3);\n'
          + f'tl.fromTo("#{seg.id}-ticktx",{{x:0}},{{x:-900,duration:{seg.d:.2f},ease:"none"}},0);\n' + ps)
    film.sfx_at(seg, wt, "impact")
    film.scene(seg.id, body, s)


# ================================================================ 2 素材横条（标准 B-roll 段）
BAND_GEO = {  # 横条位置、小窗、字幕位置
    "tanjin": (380, ("circle", 30, 840, 280, 280), CAP_Y),
    "dangan": (280, ("circle", W - 36 - 240, 162, 240, 240), None),
    "kuangshi": (200, ("squircle", (W - 300) / 2, 958, 300, 300), None),
    "cilan": (330, ("circle", 36, 220, 220, 220), None),
    "nihong": (360, ("rect", 30, 760, 230, 290), CAP_Y),
}


def band_scene(film, seg):
    """data: band（素材键）, band2{key,t}（中途换镜，可选）, ruler{from,to,at,t}, dots, corner_tag{zh,en,icon}, badge{zh,t,x,y},
    person{name,role,t,photo}, stamp{text,t}, title{zh,en}（可选，放横条上方）。"""
    d = seg.data
    st = film.st
    by, pdef, cap = BAND_GEO[st.key]
    by = d.get("band_y", by)
    if d.get("title") and by < 300:  # 横条上方要放标题：标题最高到 150（缩完约 270），横条往下让
        by = 300
    bh = {"dangan": 760}.get(st.key, 608)
    bg, s = graphic_bg(film, seg, photo=d.get("bg_photo"))
    body = bg
    if d.get("band2"):
        t2 = seg.L(d["band2"]["t"])
        body += (f'<div id="{seg.id}-bandw" class="ab" data-layout-allow-overflow style="left:{BLEED_X:.0f}px;top:{by}px;width:{BLEED_W:.0f}px;height:608px;overflow:hidden">'
                 f'<video id="{seg.id}-b1" class="clip{grade_cls(film, seg)}" data-start="0" data-duration="{t2:.3f}" src="{film.a(d["band"])}" muted playsinline style="position:absolute;inset:0;width:{BLEED_W:.0f}px;height:608px;object-fit:cover"></video>'
                 f'<video id="{seg.id}-b2" class="clip{grade_cls(film, seg)}" data-start="{t2:.3f}" data-duration="{seg.d - t2:.3f}" src="{film.a(d["band2"]["key"])}" muted playsinline style="position:absolute;inset:0;width:{BLEED_W:.0f}px;height:608px;object-fit:cover"></video>'
                 f'<div class="ab" style="inset:0;background:linear-gradient(180deg,rgba(0,0,0,.45),rgba(0,0,0,0) 18%,rgba(0,0,0,0) 80%,rgba(0,0,0,.75))"></div></div>')
    else:
        body += band(film, seg, d["band"], by, h=bh)
    s += f'tl.fromTo("#{seg.id}-bandw",{{opacity:0,y:40}},{{opacity:1,y:0,duration:0.45,ease:"power3.out"}},0);\n'
    if d.get("title"):
        body += header(film, seg, d["title"]["zh"], d["title"]["en"], max(150, by - 210), 64)
        s += head_in(film, seg)
    if d.get("ruler"):
        r = d["ruler"]
        yrs = list(range(int(r["from"]), int(r["to"]) + 1))
        step = 1080 / max(1, len(yrs) - 1) if len(yrs) > 1 else 1080
        ticks = "".join(f'<div class="ab" style="left:{k * step - 40:.0f}px;top:0;width:80px;text-align:center;font:500 20px/1 NUM,EN;color:rgba(255,255,255,.75)">{y}</div>'
                        for k, y in enumerate(yrs))
        minor = "".join(f'<div class="ab" style="left:{k * step / 5:.0f}px;top:{30 if k % 5 else 26}px;width:1px;height:{8 if k % 5 else 14}px;background:rgba(255,255,255,.55)"></div>'
                        for k in range((len(yrs) - 1) * 5 + 1))
        body += (f'<div id="{seg.id}-rul" class="ab" style="left:0;top:{by - 56}px;width:1080px;height:48px;overflow:hidden">'
                 f'<div id="{seg.id}-rult" class="ab" style="left:0;top:0;width:1080px;height:48px">{ticks}{minor}</div>'
                 f'<div class="ab" style="left:530px;top:40px;width:0;height:0;border-left:10px solid transparent;border-right:10px solid transparent;border-bottom:12px solid #fff"></div></div>')
        at = (int(r.get("at", yrs[len(yrs) // 2])) - yrs[0]) * step
        s += f'tl.fromTo("#{seg.id}-rult",{{x:{540 - at + 220:.0f}}},{{x:{540 - at:.0f},duration:{min(seg.d, 2.4):.2f},ease:"power2.out"}},{seg.at_t(r, 0.1)});\n'
    if d.get("dots") or st.key == "cilan" and d.get("dots") is not False:
        dots = "".join(f'<i style="position:absolute;left:{k * 64}px;top:-5px;width:12px;height:12px;border-radius:50%;background:{st.c["a"]};box-shadow:0 0 10px {st.c["a"]}"></i>'
                       for k in range(20))
        body += (f'<div class="ab" style="left:0;right:0;top:{by}px;height:2px;background:linear-gradient(90deg,transparent,{st.c["a"]},transparent)"></div>'
                 f'<div class="ab" style="left:260px;top:{by - 1}px;width:820px;height:4px;overflow:hidden"><div id="{seg.id}-dots" class="ab" style="left:0;top:0;width:1400px;height:4px">'
                 f'</div></div><div class="ab" style="left:260px;top:{by - 6}px;width:820px;height:16px;overflow:hidden"><div id="{seg.id}-dt" class="ab" style="left:0;top:0;width:1400px">{dots}</div></div>'
                 f'<div class="ab" style="left:0;right:0;top:{by + 606}px;height:2px;background:linear-gradient(90deg,transparent,{st.c["a"]},transparent)"></div>')
        s += f'tl.fromTo("#{seg.id}-dt",{{x:0}},{{x:-320,duration:{seg.d:.2f},ease:"none"}},0);\n'
    if d.get("corner_tag"):
        ct = d["corner_tag"]
        ic = icon(ct["icon"], 36, "#2A1F12", 2) if ct.get("icon") else ""
        body += (f'<div id="{seg.id}-ct" class="tag" style="left:30px;top:{by - 64}px;border-radius:10px;padding-left:22px;display:flex;align-items:center;gap:10px">'
                 f'<span>{rich(ct["zh"])}<span style="display:block;font:600 18px/1 EN,Inter;letter-spacing:3px;opacity:.7;margin-top:6px">{rich(ct.get("en", ""))}</span></span>{ic}</div>')
        s += f'tl.fromTo("#{seg.id}-ct",{{opacity:0,x:-120}},{{opacity:1,x:0,duration:0.45,ease:"power3.out"}},0.2);\n'
    if d.get("badge"):
        b = d["badge"]
        bx, byy = b.get("x", 600), b.get("y", by + 90)
        body += f'<div id="{seg.id}-bd" class="badge2" style="left:{bx}px;top:{byy}px;opacity:0">{rich(b["zh"])}</div>'
        bt = seg.at_t(b, 0.5)
        s += f'tl.fromTo("#{seg.id}-bd",{{opacity:0,scale:0.7}},{{opacity:1,scale:1,duration:0.35,ease:"back.out(2)"}},{bt:.3f});\n' + floaty(f"#{seg.id}-bd", seg.d, 6, 3.4, bt + 0.4)
        film.sfx_at(seg, bt, "snap")
    if d.get("person"):
        p = d["person"]
        pt = seg.at_t(p, 0.4)
        photo = asset_or_none(film, p.get("photo"))
        ph_html = f'<div class="ab" style="left:0;top:0;width:150px;height:100%;background:url(\'{photo}\') center/cover"></div>' if photo else ""
        tx = 170 if photo else 30
        body += (f'<div id="{seg.id}-pc" class="card" style="left:{W - 460}px;top:{by + 608 - 210}px;width:420px;height:160px;opacity:0">{ph_html}<div class="dash"></div>'
                 f'<div class="ab t" style="left:{tx}px;top:30px;font-size:44px">{rich(p["name"])}</div>'
                 f'<div class="ab" style="left:{tx + 2}px;top:94px;font:400 24px/1.3 SM;opacity:.75;right:20px">{rich(p.get("role", ""))}</div></div>')
        s += st.card_in(f"#{seg.id}-pc", pt, 0, film.rng(seg), "right")
        film.sfx_at(seg, pt, "swoosh")
    if d.get("stamp"):
        sp = d["stamp"]
        body += f'<div id="{seg.id}-stp" class="ab TR" style="left:0;right:0;top:{by + 200}px;text-align:center;font-size:200px;letter-spacing:10px;opacity:0">{rich(sp["text"])}</div>'
        s += st.stamp_in(f"#{seg.id}-stp", seg.at_t(sp, 1.0))
        film.sfx_at(seg, seg.at_t(sp, 1.0), "impact")
    ph, ps = put_pip(film, seg, pip_spec(film, seg, pdef))
    body += ph
    s += ps
    seg.cap_y_set = cap if cap else by + bh + 34
    if st.key == "kuangshi":
        seg.cap_y_set = by + 608 + 24
    film.scene(seg.id, body, s)


# ================================================================ 3 柱状图
def _bars_main(film, seg):
    """data: title{zh,en}, values[…], labels[…]（可选）, hi[起,止]（高亮区间）, hi_label, hi_t, line{label,t}（持平虚线）, q_t（问号）, bars_t, note。
    风格 chart=paper 时画在白纸立体面板上（瓷蓝），否则是深色底金色柱（其他风格）。"""
    d = seg.data
    st = film.st
    vals = d["values"]
    n = len(vals)
    vmax = max(vals)
    bt0 = seg.at("bars_t", 0.6)
    s = ""
    if st.chart == "paper" and not d.get("glass"):
        bg, s = graphic_bg(film, seg, pattern=True)
        pw, ph_ = 820, 1020
        cw, chh = pw - 140, 640
        bw = cw / n * 0.6
        bars_html = ""
        for k, v in enumerate(vals):
            h = chh * v / vmax
            x = 80 + k * cw / n + (cw / n - bw) / 2
            hi = d.get("hi") and d["hi"][0] <= k <= d["hi"][1]
            col = st.c["a"] if hi else st.c["navy"]
            bars_html += (f'<div id="{seg.id}-b{k}" class="ab" style="left:{x:.0f}px;top:{260 + chh - h:.0f}px;width:{bw:.0f}px;height:{h:.0f}px;'
                          f'background:linear-gradient(180deg,{col},{col}CC);border-radius:4px 4px 0 0;transform-origin:50% 100%"></div>')
            lab = (d.get("labels") or [""] * n)[k]
            bars_html += f'<div class="ab" style="left:{x - 20:.0f}px;top:{260 + chh + 14}px;width:{bw + 40:.0f}px;text-align:center;font:500 22px/1 NUM,EN;color:#5A6480">{rich(lab)}</div>'
        grid = "".join(f'<div class="ab" style="left:70px;right:50px;top:{260 + chh * k / 4:.0f}px;height:1px;background:rgba(20,40,92,.1)"></div>' for k in range(5))
        body = bg + (f'<div id="{seg.id}-pf" class="fl" style="left:{(W - pw) / 2:.0f}px;top:250px;width:{pw}px;height:{ph_}px">'
                     f'<div id="{seg.id}-p" class="paper" style="left:0;top:0;width:{pw}px;height:{ph_}px">'
                     f'<div class="ab" style="left:80px;top:80px;width:520px;font:400 60px/1.1 SM;color:{st.c["navy"]}">{rich(d["title"]["zh"])}</div>'
                     f'<div class="ab" style="left:82px;top:160px;font:600 18px/1 EN,Inter;letter-spacing:4px;color:#4E5A7E;text-transform:uppercase">{rich(d["title"]["en"])}</div>'
                     f'{grid}{bars_html}<div class="ab" style="right:50px;bottom:40px;font:600 16px/1 EN,Inter;letter-spacing:4px;color:#6B7591">{rich(d.get("note", NOTE))}</div></div></div>')
        s += (f'tl.set("#{seg.id}-p",{{transformPerspective:1600,transformOrigin:"50% 50%"}},0);\n'
              f'tl.fromTo("#{seg.id}-p",{{opacity:0,rotationY:-42,rotationX:12,x:120}},{{opacity:1,rotationY:-16,rotationX:5,x:0,duration:0.8,ease:"power3.out"}},0.05);\n'
              + sway(f"#{seg.id}-pf", seg.d, 2.5, 5.0, 0.9))
        ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", W - 40 - 220, 162, 220, 220)))
        body += ph
        s += ps
        seg.cap_y_set = CAP_Y
    else:
        bg, s = graphic_bg(film, seg)
        body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
        ph, ps = put_pip(film, seg, pip_spec(film, seg, ("rect", 330, 390, 420, 500)))
        body += ph
        bw = 46
        gap = 860 / n
        rects = ""
        for k, v in enumerate(vals):
            h = 330 * v / vmax
            x = 70 + k * gap
            hi = d.get("hi") and d["hi"][0] <= k <= d["hi"][1]
            rects += f'<rect id="{seg.id}-b{k}" x="{x:.0f}" y="{400 - h:.0f}" width="{bw}" height="{h:.0f}" rx="3" fill="url(#{seg.id}-g{"h" if hi else ""})"/>'
        hi_box = ""
        if d.get("hi"):
            x0 = 70 + d["hi"][0] * gap - 18
            x1 = 70 + d["hi"][1] * gap + bw + 18
            hi_box = f'<rect id="{seg.id}-hi" x="{x0:.0f}" y="40" width="{x1 - x0:.0f}" height="140" rx="6" fill="rgba(120,160,255,.24)" stroke="rgba(150,185,255,.8)" stroke-dasharray="6 6" opacity="0"/>'
        a = st.c["a"]
        body += (f'<svg id="{seg.id}-chart" class="ab" style="left:60px;top:880px" width="960" height="460" viewBox="0 0 960 460">'
                 f'<defs><linearGradient id="{seg.id}-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{a}" stop-opacity=".35"/></linearGradient>'
                 f'<linearGradient id="{seg.id}-gh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="{a}"/></linearGradient></defs>'
                 + "".join(f'<line x1="40" x2="920" y1="{y}" y2="{y}" stroke="rgba(255,255,255,.12)" stroke-dasharray="3 6"/>' for y in (100, 200, 300))
                 + f'<line x1="40" x2="920" y1="400" y2="400" stroke="rgba(255,255,255,.4)"/>{rects}{hi_box}'
                 + (f'<path id="{seg.id}-ln" d="M60 372 C 300 374, 560 370, 900 366" fill="none" stroke="rgba(255,255,255,.85)" stroke-width="5" stroke-dasharray="14 12" opacity="0"/>'
                    f'<text id="{seg.id}-lnl" x="44" y="446" fill="#FFFFFF" font-family="SM" font-size="40" opacity="0">{rich(d["line"]["label"])}</text>' if d.get("line") else "")
                 + f'<text x="920" y="446" fill="rgba(255,255,255,.4)" font-family="EN,Inter" font-size="18" letter-spacing="4" text-anchor="end">{rich(d.get("note", NOTE))}</text></svg>')
        if d.get("hi_label"):
            body += f'<div id="{seg.id}-up" class="ab T2" style="left:690px;top:830px;font-size:64px;opacity:0">{rich(d["hi_label"])}</div>'
        if d.get("q_t"):
            body += f'<div id="{seg.id}-q" class="ab T1" style="left:860px;top:1090px;font-size:200px;line-height:1;opacity:0">?</div>'
        s += head_in(film, seg) + ps
        seg.cap_y_set = 1380
    for k in range(n):
        s += f'tl.fromTo("#{seg.id}-b{k}",{{scaleY:0,transformOrigin:"50% 100%"}},{{scaleY:1,duration:0.45,ease:"power3.out"}},{bt0 + k * 0.14:.2f});\n'
    film.sfx_at(seg, bt0, "swoosh")
    if d.get("hi") and st.chart != "paper":
        ht = seg.at("hi_t", bt0 + n * 0.14 + 0.3)
        s += f'tl.fromTo("#{seg.id}-hi",{{opacity:0}},{{opacity:1,duration:0.35}},{ht:.3f});\n'
        if d.get("hi_label"):
            s += f'tl.fromTo("#{seg.id}-up",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.35,ease:"back.out(2)"}},{ht + 0.05:.3f});\n'
        film.sfx_at(seg, ht, "snap")
    if d.get("line") and st.chart != "paper":
        lt = seg.at_t(d["line"], seg.d * 0.65)
        s += f'tl.fromTo(["#{seg.id}-ln","#{seg.id}-lnl"],{{opacity:0}},{{opacity:1,duration:0.4}},{lt:.3f});\n'
    if d.get("q_t") and st.chart != "paper":
        s += f'tl.fromTo("#{seg.id}-q",{{opacity:0,scale:1.6,rotation:-12}},{{opacity:1,scale:1,rotation:0,duration:0.45,ease:"back.out(2)"}},{seg.L(d["q_t"]):.3f});\n'
        film.sfx_at(seg, seg.L(d["q_t"]), "impact", 0.2)
    film.scene(seg.id, body, s)


# ================================================================ 4 大竖窗＋右侧配图卡
def pip_cards(film, seg):
    """data: title{zh,en}, cards[{zh,en,img,t}]（2–3 张）。rng 决定竖窗在左还是右。"""
    d = seg.data
    st = film.st
    rng = film.rng(seg)
    mirror = d.get("mirror", rng.random() < 0.35)
    bg, s = graphic_bg(film, seg)
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
    cards = d["cards"]
    n = len(cards)
    px = 582 if mirror else 28
    cx = 28 if mirror else 528
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("rect", px, 420, 470, 800)), 0.2, 8)
    body += ph
    ch = 330 if n == 2 else 250
    gap = 50 if n == 2 else 28
    y0 = 470 if n == 2 else 430
    ids = []
    for k, c in enumerate(cards):
        cid = f"{seg.id}-c{k}"
        ids.append(cid)
        body += card_img(cid, cx, y0 + k * (ch + gap), 524, ch, c["zh"], c.get("en", ""), asset_or_none(film, c.get("img")), fs=52 if n == 2 else 46)
    s += head_in(film, seg) + ps
    for k, cid in enumerate(ids):
        s += st.card_in(f"#{cid}", 0.35 + k * 0.12, k, rng, "left" if mirror else "right")
        s += f'tl.to("#{cid}",{{opacity:0.42,duration:0.01}},{0.9 + k * 0.12:.2f});\n'
        s += floaty(f"#{cid}f", seg.d, 9, 3.4, k * 0.9)
    times = seg.times(cards, first=1.2)
    s += lightup(seg, ids, times)
    for t in times:
        film.sfx_at(seg, t, "snap")
    film.scene(seg.id, body, s)


# ================================================================ 5 2×2 实拍宫格
def _grid_2x2(film, seg):
    """data: title{zh,en}, tiles[{key,label,t}]×4, all_t（全部点亮）。"""
    d = seg.data
    bg, s = graphic_bg(film, seg)
    tiles = d["tiles"][:4]
    a = film.st.c["a"]
    html = ""
    for k, tdef in enumerate(tiles):
        x = 26 + (k % 2) * 520
        y = 440 + (k // 2) * 400
        src = film.a(tdef["key"])
        media = (f'<video id="{seg.id}-v{k}" class="clip{grade_cls(film, seg)}" data-start="0" data-duration="{seg.d:.3f}" src="{src}" muted playsinline style="position:absolute;left:-8px;top:-6px;width:528px;height:396px;object-fit:cover"></video>'
                 if src.lower().endswith((".mp4", ".mov", ".webm")) else f'<div class="ab" style="inset:0;background:url(\'{src}\') center/cover"></div>')
        html += (f'<div id="{seg.id}-t{k}" class="ab" style="left:{x}px;top:{y}px;width:508px;height:384px;border-radius:10px;overflow:hidden;border:1.5px solid rgba(255,255,255,.14)">{media}'
                 f'<div id="{seg.id}-d{k}" class="ab" style="inset:0;background:rgba(8,8,10,.62)"></div>'
                 f'<div id="{seg.id}-k{k}" class="ab" style="inset:-1px;border-radius:10px;border:3px solid {a};box-shadow:inset 0 0 30px {a}55;opacity:0"></div>'
                 f'<div id="{seg.id}-l{k}" class="card" style="left:18px;bottom:18px;height:70px;padding:12px 20px;border-radius:12px;opacity:0"><div class="t" style="font-size:40px;white-space:nowrap">{rich(tdef["label"])}</div></div></div>')
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"]) + html
    shp = film.st.pip["shape"]
    ph, ps = put_pip(film, seg, pip_spec(film, seg, (shp, 806, 250, 240, 240) if shp != "rect" else ("rect", 830, 220, 210, 260)))
    body += ph
    s += head_in(film, seg) + ps
    s += f'tl.fromTo([{",".join(chr(34) + "#" + seg.id + "-t" + str(k) + chr(34) for k in range(len(tiles)))}],{{opacity:0,scale:0.92}},{{opacity:1,scale:1,duration:0.45,stagger:0.1,ease:"power3.out"}},0.15);\n'
    times = seg.times(tiles, first=0.8)
    for k, t in enumerate(times):
        s += (f'tl.to("#{seg.id}-d{k}",{{opacity:0,duration:0.3}},{t:.3f});\n'
              f'tl.fromTo("#{seg.id}-k{k}",{{opacity:0}},{{opacity:1,duration:0.25}},{t:.3f});\n'
              f'tl.fromTo("#{seg.id}-l{k}",{{opacity:0,y:16}},{{opacity:1,y:0,duration:0.3,ease:"back.out(1.8)"}},{t + 0.05:.3f});\n')
        if k > 0:
            s += f'tl.to("#{seg.id}-k{k - 1}",{{opacity:0.35,duration:0.3}},{t:.3f});\n'
        film.sfx_at(seg, t, "snap")
    if d.get("all_t"):
        s += f'tl.to([{",".join(chr(34) + "#" + seg.id + "-k" + str(k) + chr(34) for k in range(len(tiles)))}],{{opacity:1,duration:0.3}},{seg.L(d["all_t"]):.3f});\n'
    seg.cap_y_set = CAP_Y
    film.scene(seg.id, body, s)


# ================================================================ 6 透视编号链
def _chain_list(film, seg):
    """data: title{zh,en}, items[{zh,en,img,t}]（3–5）, stamp{text,en,t}（可选）。rng 决定面板朝向。"""
    d = seg.data
    st = film.st
    rng = film.rng(seg)
    mirror = d.get("mirror", rng.random() < 0.4)
    items = d["items"][:5]
    n = len(items)
    gap = 170 if n >= 5 else 200
    top0 = 170
    bg, s = graphic_bg(film, seg)
    plates = ""
    for k, it in enumerate(items):
        y = top0 + k * gap
        img = asset_or_none(film, it.get("img"))
        ih = (f'<div class="ab grade" style="right:0;top:0;width:250px;height:100%;background:url(\'{img}\') center/cover;-webkit-mask:linear-gradient(90deg,transparent,#000 45%)"></div>' if img else "")
        hh = gap - 26
        plates += (f'<div id="{seg.id}-p{k}" class="card" style="left:66px;top:{y}px;width:560px;height:{hh}px">{ih}<div class="dash"></div><div id="{seg.id}-p{k}-g" class="glow"></div>'
                   f'<div class="ab k" style="left:26px;top:{hh / 2 - 56:.0f}px">{k + 1}</div>'
                   f'<div class="ab t" style="left:110px;top:{hh / 2 - 34:.0f}px;font-size:{min(54, fit_fs(it["zh"], 230 if img else 420, 54))}px;white-space:nowrap">{rich(it["zh"])}</div>'
                   f'<div class="ab e" style="left:112px;top:{hh / 2 + 32:.0f}px;margin:0">{rich(it.get("en", ""))}</div></div>')
    arrows = "".join(f'<path d="M {640 if k % 2 == 0 else 46} {top0 + (gap - 26) / 2 + k * gap:.0f} q {40 if k % 2 == 0 else -40} {gap / 2:.0f} 0 {gap}" fill="none" stroke="{st.c["a"]}" stroke-opacity=".6" stroke-width="3" stroke-dasharray="8 10"/>' for k in range(n - 1))
    ph_ = top0 + n * gap + 50
    px = 64 if mirror else 290  # 面板做 3D 倾斜，靠近镜头的一边会被透视放大，离安全线多留一点
    body = bg + (f'<div id="{seg.id}-pf" class="fl" style="left:{px}px;top:200px;width:700px;height:{ph_}px">'
                 f'<div id="{seg.id}-panel" class="ab" style="left:0;top:0;width:700px;height:{ph_}px">'
                 f'<div class="ab" style="left:0;top:0;width:700px;height:{ph_}px;border-radius:20px;border:1.5px solid rgba(255,255,255,.18);background:linear-gradient(180deg,rgba(30,28,30,.5),rgba(10,10,12,.7))"></div>'
                 f'<div class="ab" style="left:70px;top:58px;white-space:nowrap"><span class="T2" style="font-size:66px">{rich(d["title"]["zh"])}</span>'
                 f'<span class="EN" style="margin-left:18px">{rich(d["title"]["en"])}</span></div>'
                 f'<svg class="ab" style="left:0;top:0" width="700" height="{ph_}">{arrows}</svg>{plates}</div></div>')
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("rect", 726 if mirror else 30, 640, 330, 480)), 0.3)
    body += ph
    rot0, rot1 = (34, 14) if mirror else (-34, -14)
    s += (f'tl.set("#{seg.id}-panel",{{transformPerspective:1800,transformOrigin:"{80 if mirror else 20}% 50%"}},0);\n'
          f'tl.fromTo("#{seg.id}-panel",{{opacity:0,rotationY:{rot0},x:{-80 if mirror else 80}}},{{opacity:1,rotationY:{rot1},x:0,duration:0.7,ease:"power3.out"}},0);\n'
          + sway(f"#{seg.id}-pf", seg.d, 3, 4.8, 0.7) + ps)
    for k in range(n):
        s += f'tl.fromTo("#{seg.id}-p{k}",{{opacity:0,filter:"blur(6px)"}},{{opacity:0.38,filter:"blur(3px)",duration:0.1}},0.0);\n'
    times = [max(0.15, t) for t in seg.times(items, first=0.8)]
    for k, t in enumerate(times):
        s += (f'tl.to("#{seg.id}-p{k}",{{opacity:1,filter:"blur(0px)",x:-14,duration:0.3,ease:"power3.out"}},{t:.3f});\n'
              f'tl.to("#{seg.id}-p{k}",{{x:0,duration:0.35,ease:"power2.out"}},{t + 0.3:.3f});\n'
              f'tl.fromTo("#{seg.id}-p{k}-g",{{opacity:0}},{{opacity:1,duration:0.25}},{t:.3f});\n')
        if k > 0:
            s += f'tl.to("#{seg.id}-p{k - 1}-g",{{opacity:0.35,duration:0.3}},{t:.3f});\n'
        film.sfx_at(seg, t, "snap")
    if d.get("stamp"):
        sp = d["stamp"]
        # 印章放在面板下方、小窗的另一侧，不压条目和小窗
        sfs = min(170, fit_fs(sp["text"], 600, 170))
        swd = tw(sp["text"]) * sfs + 6 * len(plain(sp["text"]))
        sy = min(200 + ph_ + 20, 1440 - sfs * 1.1 - 50)
        sx = 60 if mirror else W - 60 - swd
        body += (f'<div id="{seg.id}-stamp" class="ab TR" style="left:{sx:.0f}px;top:{sy:.0f}px;font-size:{sfs}px;letter-spacing:6px;white-space:nowrap;opacity:0">{rich(sp["text"])}</div>'
                 f'<div id="{seg.id}-stampen" class="ab EN" style="left:{sx + 10:.0f}px;top:{sy + sfs * 1.1 + swd * 0.07 + 6:.0f}px;color:#FF8A80;letter-spacing:8px;opacity:0">{rich(sp.get("en", ""))}</div>')
        stt = seg.at_t(sp, seg.d - 1.5)
        s += st.stamp_in(f"#{seg.id}-stamp", stt) + f'tl.fromTo("#{seg.id}-stampen",{{opacity:0}},{{opacity:1,duration:0.3}},{stt + 0.35:.3f});\n'
        film.sfx_at(seg, stt, "impact")
    film.scene(seg.id, body, s)


# ================================================================ 7 斜向层叠卡片
def _cascade_diag(film, seg):
    """data: title{zh,en}, items[{zh,en,img,t}]（3–4）, line{label}（可选，背景一条上升线）。"""
    d = seg.data
    st = film.st
    rng = film.rng(seg)
    mirror = d.get("mirror", rng.random() < 0.4)
    items = d["items"][:4]
    bg, s = graphic_bg(film, seg)
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
    if d.get("line"):
        body += (f'<svg class="ab" style="left:0;top:330px" width="1080" height="900"><path id="{seg.id}-l" d="M0 860 C 260 820, 520 700, 760 420 S 1000 80, 1080 40" fill="none" stroke="rgba(67,214,154,.55)" stroke-width="6"/>'
                 f'<path d="M0 860 C 260 820, 520 700, 760 420 S 1000 80, 1080 40 L 1080 900 L 0 900 Z" fill="rgba(67,214,154,.06)"/></svg>'
                 f'<div id="{seg.id}-lt" class="ab" style="left:700px;top:420px;font:400 44px/1 SM;color:#7BE8B9;opacity:0">{rich(d["line"]["label"])}</div>')
        s += (f'tl.fromTo("#{seg.id}-l",{{strokeDasharray:1600,strokeDashoffset:1600}},{{strokeDashoffset:0,duration:1.6,ease:"power2.out"}},0.2);\n'
              f'tl.fromTo("#{seg.id}-lt",{{opacity:0}},{{opacity:1,duration:0.4}},0.6);\n')
    times = seg.times(items, first=0.8)
    for k, it in enumerate(items):
        x = (W - 680 - 40 - k * 110) if mirror else 40 + k * 110
        body += card_img(f"{seg.id}-q{k}", x, 390 + k * 222, 640, 230, it["zh"], it.get("en", ""), asset_or_none(film, it.get("img")), num=f"0{k + 1}", fs=50)
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", 40 if mirror else 790, 360, 250, 250) if st.pip["shape"] != "rect" else ("rect", 40 if mirror else 810, 330, 230, 290)))
    body += ph
    s += head_in(film, seg) + ps
    r0, r1 = (20, 9) if mirror else (-20, -9)
    for k, t in enumerate(times):
        if d.get("line") and k == 0:
            s += f'tl.to("#{seg.id}-lt",{{opacity:0,duration:0.3}},{t - 0.3:.3f});\n'
        s += (f'tl.fromTo("#{seg.id}-q{k}",{{opacity:0,y:-120,rotation:{r0}}},{{opacity:1,y:0,rotation:{r1},duration:0.5,ease:"back.out(1.6)"}},{t - 0.1:.3f});\n'
              f'tl.fromTo("#{seg.id}-q{k}-g",{{opacity:0}},{{opacity:1,duration:0.25}},{t + 0.2:.3f});\n')
        if k > 0:
            s += f'tl.to("#{seg.id}-q{k - 1}",{{opacity:0.55,duration:0.3}},{t:.3f});\ntl.to("#{seg.id}-q{k - 1}-g",{{opacity:0,duration:0.3}},{t:.3f});\n'
        s += floaty(f"#{seg.id}-q{k}f", seg.d, 7, 3.2, k * 0.6)
        film.sfx_at(seg, t - 0.1, "swoosh")
    seg.cap_y_set = 1330
    film.scene(seg.id, body, s)


# ================================================================ 8 倾斜图表＋事件徽章
def tilt_chart(film, seg):
    """data: title{zh,en}, values[…]（折线，按顺序）, spike[起,止]（高亮区间，可选）, badge{text,sub,t}, future{label,t}（往上的箭头线，可选），
    callout{label,value,t}（数值标注，可选）, line_t, note。"""
    d = seg.data
    st = film.st
    rng = film.rng(seg)
    sgn = -1 if rng.random() < 0.5 else 1
    vals = d["values"]
    n = len(vals)
    vmax, vmin = max(vals), min(vals)
    xs = [60 + k * 640 / (n - 1) for k in range(n)]
    ys = [600 - 470 * (v - vmin) / max(1e-6, vmax - vmin) for v in vals]
    pts = " ".join(f"{x:.0f},{y:.0f}" for x, y in zip(xs, ys))
    a = st.c["a"]
    lc = {"nihong": a, "cilan": st.c.get("lt", a)}.get(st.key, "#A9C1FF")
    bg, s = graphic_bg(film, seg)
    spike = ""
    if d.get("spike"):
        i0, i1 = d["spike"]
        spike = f'<rect id="{seg.id}-box" x="{xs[i0] - 24:.0f}" y="100" width="{xs[i1] - xs[i0] + 48:.0f}" height="540" rx="8" fill="rgba(255,90,87,.18)" stroke="rgba(255,110,100,.85)" stroke-width="3" stroke-dasharray="8 8" opacity="0"/>'
    fut = ""
    if d.get("future"):
        fut = (f'<path id="{seg.id}-fut" d="M {xs[-1]:.0f} {ys[-1]:.0f} C {xs[-1] + 80:.0f} {ys[-1] - 30:.0f}, 880 300, 960 160" fill="none" stroke="#43D69A" stroke-width="7" stroke-linecap="round"/>'
               f'<path id="{seg.id}-arw" d="M 940 148 L 968 150 L 958 178" fill="none" stroke="#43D69A" stroke-width="7" stroke-linecap="round" opacity="0"/>'
               f'<text id="{seg.id}-futl" x="950" y="120" fill="#7BE8B9" font-family="SM" font-size="46" text-anchor="end" opacity="0">{rich(d["future"]["label"])}</text>')
    call = ""
    if d.get("callout"):
        c = d["callout"]
        call = (f'<div id="{seg.id}-cl" class="badge2" style="left:{min(xs[-1] + 40, 700):.0f}px;top:{ys[-1] + 230:.0f}px;font-size:44px;opacity:0">'
                f'{rich(c["label"])}<div style="margin-top:12px;font:400 56px/1 SM;color:{st.c.get("m", a)};white-space:nowrap">{rich(c["value"])}</div></div>')
    badge = ""
    if d.get("badge"):
        b = d["badge"]
        bx = xs[d["spike"][0]] if d.get("spike") else xs[n // 2]
        badge = (f'<div id="{seg.id}-bdg" class="ab" style="left:{bx - 75:.0f}px;top:930px;width:150px;text-align:center;opacity:0">'
                 f'<div style="width:130px;height:130px;margin:0 auto;border-radius:50%;border:4px solid rgba(255,244,232,.95);background:radial-gradient(circle at 35% 30%,#3A2A22,#120C0A);'
                 f'box-shadow:0 0 26px {a}88;font:400 46px/122px SM;color:#FFE9D6">{rich(b["text"])}</div>'
                 f'<div style="display:inline-block;margin-top:-14px;padding:6px 14px;border-radius:8px;background:#E8524A;font:400 28px/1 SM;color:#fff;position:relative">{rich(b.get("sub", ""))}</div></div>')
    body = bg + (f'<div id="{seg.id}-tf" class="fl" style="left:40px;top:150px;width:1000px;height:1120px">'
                 f'<div id="{seg.id}-tilt" class="ab" style="left:0;top:0;width:1000px;height:1120px">'
                 f'<div class="ab" style="left:0;right:0;top:20px;text-align:center"><div class="T2" style="font-size:{min(92, fit_fs(d["title"]["zh"], 900, 92))}px;line-height:1.1;letter-spacing:3px">{rich(d["title"]["zh"])}</div>'
                 f'<div class="EN" style="margin-top:18px">{rich(d["title"]["en"])}</div></div>'
                 f'<svg class="ab" style="left:0;top:260px" width="1000" height="800" viewBox="0 0 1000 800">'
                 f'<defs><linearGradient id="{seg.id}-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{lc}" stop-opacity=".55"/><stop offset="1" stop-color="{lc}" stop-opacity="0"/></linearGradient></defs>'
                 + "".join(f'<line x1="60" x2="980" y1="{y}" y2="{y}" stroke="rgba(255,255,255,.07)"/>' for y in range(120, 660, 90))
                 + f'<line x1="60" x2="980" y1="640" y2="640" stroke="rgba(255,255,255,.35)"/>'
                 f'<polygon id="{seg.id}-area" points="60,640 {pts} {xs[-1]:.0f},640" fill="url(#{seg.id}-g)" opacity="0"/>'
                 f'<polyline id="{seg.id}-line" points="{pts}" fill="none" stroke="{lc}" stroke-width="5" stroke-linejoin="round"/>{spike}{fut}'
                 f'<text x="980" y="700" fill="rgba(255,255,255,.4)" font-family="EN,Inter" font-size="20" letter-spacing="4" text-anchor="end">{rich(d.get("note", NOTE))}</text></svg>'
                 f'{badge}{call}</div></div>')
    shape = st.pip["shape"]
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", 36 if sgn > 0 else 784, 420, 260, 260) if shape != "rect" else ("rect", 36, 1010, 230, 290)), 0.3)
    body += ph
    lt = seg.at("line_t", 0.5)
    s += (f'tl.set("#{seg.id}-tilt",{{transformPerspective:1700,transformOrigin:"50% 60%"}},0);\n'
          f'tl.fromTo("#{seg.id}-tilt",{{opacity:0,rotationX:30,rotationY:{-24 * sgn},y:60}},{{opacity:1,rotationX:12,rotationY:{-12 * sgn},y:0,duration:0.8,ease:"power3.out"}},0);\n'
          + sway(f"#{seg.id}-tf", seg.d, 2.5, 5.2, 0.8) + ps
          + f'const {seg.id}_L=document.getElementById("{seg.id}-line").getTotalLength();\n'
          f'tl.fromTo("#{seg.id}-line",{{strokeDasharray:{seg.id}_L,strokeDashoffset:{seg.id}_L}},{{strokeDashoffset:0,duration:2.2,ease:"power1.inOut"}},{lt:.3f});\n'
          f'tl.fromTo("#{seg.id}-area",{{opacity:0}},{{opacity:1,duration:0.6}},{lt + 1.6:.3f});\n')
    film.sfx_at(seg, lt, "whoosh")
    if d.get("spike"):
        s += f'tl.fromTo("#{seg.id}-box",{{opacity:0}},{{opacity:1,duration:0.3}},{seg.at_t(d.get("badge", {}), lt + 1.2):.3f});\n'
    if d.get("badge"):
        bt = seg.at_t(d["badge"], lt + 1.3)
        s += f'tl.fromTo("#{seg.id}-bdg",{{opacity:0,scale:0.5}},{{opacity:1,scale:1,duration:0.4,ease:"back.out(2)"}},{bt:.3f});\n'
        film.sfx_at(seg, bt, "snap")
    if d.get("future"):
        ft = seg.at_t(d["future"], lt + 2.6)
        s += (f'const {seg.id}_F=document.getElementById("{seg.id}-fut").getTotalLength();\n'
              f'tl.fromTo("#{seg.id}-fut",{{strokeDasharray:{seg.id}_F,strokeDashoffset:{seg.id}_F}},{{strokeDashoffset:0,duration:1.8,ease:"power1.out"}},{ft:.3f});\n'
              f'tl.fromTo("#{seg.id}-arw",{{opacity:0}},{{opacity:1,duration:0.3}},{ft + 1.7:.3f});\n'
              f'tl.fromTo("#{seg.id}-futl",{{opacity:0}},{{opacity:1,duration:0.4}},{ft + 1.8:.3f});\n')
        if d.get("badge"):
            s += f'tl.to(["#{seg.id}-box","#{seg.id}-bdg"],{{opacity:0.35,duration:0.4}},{ft:.3f});\n'
    if d.get("callout"):
        ct = seg.at_t(d["callout"], lt + 2.2)
        s += f'tl.fromTo("#{seg.id}-cl",{{opacity:0,x:-30}},{{opacity:1,x:0,duration:0.4,ease:"back.out(1.8)"}},{ct:.3f});\n'
    seg.cap_y_set = 1330 if shape != "rect" else 1360
    film.scene(seg.id, body, s)


# ================================================================ 9 金句卡（按风格四种做法）
def pband(seg, k, cx, cy, rx, ry, rgb, n=170, seed=5):
    g = lcg(seed + k * 13)
    dots = []
    for i in range(n):
        ang = next(g) * 2 * math.pi
        jr = (next(g) + next(g) + next(g) - 1.5) * 0.22
        x = cx + math.cos(ang) * rx * (1 + jr)
        y = cy + math.sin(ang) * ry * (1 + jr) + (next(g) - 0.5) * 26
        sz = 1.5 + next(g) * 3.2
        dots.append(f'<i style="left:{x:.0f}px;top:{y:.0f}px;width:{sz:.1f}px;height:{sz:.1f}px;opacity:{0.25 + next(g) * 0.7:.2f}"></i>')
    glow = (f'<div class="ab" style="left:{cx - rx * 1.1:.0f}px;top:{cy - ry * 1.6:.0f}px;width:{rx * 2.2:.0f}px;height:{ry * 3.2:.0f}px;'
            f'background:radial-gradient(ellipse at 50% 50%,rgba({rgb},.40),rgba({rgb},.10) 45%,transparent 70%)"></div>')
    return (f'<div id="{seg.id}-pb{k}" class="ab" data-layout-ignore style="inset:0">{glow}' + "".join(dots) + "</div>",
            f"#{seg.id}-pb{k} i{{position:absolute;border-radius:50%;background:rgba({rgb},1);box-shadow:0 0 6px rgba({rgb},.9)}}")


def quote(film, seg):
    """data: lab1,en1,big1,t1, lab2,en2,big2,t2（第二句可选）, video（背景视频键，可选）, mode（覆盖风格默认：particles/banner/brush/block）,
    block 模式另用 lines[{text,em}]。"""
    d = seg.data
    st = film.st
    mode = d.get("mode", st.quote)
    t1 = seg.at("t1", 0.4)
    t2 = seg.at("t2", None) if d.get("big2") else None
    css = ""
    s = ""
    argb = st.c.get("argb", "255,196,140")
    if mode == "particles":
        bgv = (f'<video id="{seg.id}-bgv" class="clip{grade_cls(film, seg)}" data-start="0" data-duration="{seg.d:.3f}" src="{film.a(d["video"])}" muted playsinline style="position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover"></video>'
               if d.get("video") else "")
        p1, c1 = pband(seg, 1, 540, 640, 380, 60, argb)
        p2, c2 = pband(seg, 2, 540, 1110, 380, 60, argb)
        css = c1 + c2
        body = (f'<div class="bgbase"></div>{bgv}'
                f'<div id="{seg.id}-rays" class="ab" data-layout-ignore style="left:-420px;top:-420px;width:1920px;height:2760px;background:repeating-conic-gradient(from 0deg at 50% 46%,rgba({argb},.16) 0deg 1.4deg,transparent 1.4deg 8deg);-webkit-mask:radial-gradient(circle at 50% 46%,transparent 16%,#000 58%)"></div>'
                f'<div class="ab" style="inset:0;background:radial-gradient(circle at 50% 46%,rgba(0,0,0,0) 8%,rgba(0,0,0,.78) 72%)"></div>{BG_END}{p1}{p2}')
        s += (f'tl.fromTo("#{seg.id}-rays",{{rotation:0}},{{rotation:12,duration:{seg.d:.2f},ease:"none"}},0);\n'
              f'tl.fromTo("#{seg.id}-pb1",{{opacity:0,scale:0.9}},{{opacity:1,scale:1.06,duration:{seg.d:.2f},ease:"none"}},0);\n'
              f'tl.fromTo("#{seg.id}-pb2",{{opacity:0,scale:0.9}},{{opacity:1,scale:1.06,duration:{seg.d:.2f},ease:"none"}},0);\n')
        y_lab, y_big = 690, 860
        pdef = ("circle", 760, 250, 290, 290) if st.pip["shape"] != "rect" else ("rect", 810, 220, 230, 290)
    elif mode == "banner":
        body, s = graphic_bg(film, seg)
        if d.get("video"):
            body += band(film, seg, d["video"], 230)
            s += f'tl.fromTo("#{seg.id}-bandw",{{opacity:0}},{{opacity:1,duration:0.5}},0);\n'
        m = st.c.get("m", "#E8487E")
        mrgb = st.c.get("mrgb", "232,72,126")
        streaks = "".join(
            f'<div class="ab" style="left:{-200 + k * 90}px;top:{40 + (k * 37) % 120}px;width:700px;height:{2 + k % 3}px;border-radius:2px;'
            f'background:linear-gradient(90deg,transparent,rgba({mrgb},.9),rgba(255,220,240,.9),transparent);transform:rotate({-8 + k % 5 * 3}deg);filter:blur(.6px)"></div>'
            for k in range(9))
        body += (f'<div id="{seg.id}-ban" class="streak" style="left:{BLEED_X:.0f}px;right:{BLEED_X:.0f}px;top:950px;height:240px;border-top:1px solid rgba({mrgb},.5);border-bottom:1px solid rgba({mrgb},.5)">'
                 f'<div id="{seg.id}-stk" class="ab" style="left:0;top:0;width:1600px;height:240px">{streaks}</div></div>')
        s += (f'tl.fromTo("#{seg.id}-ban",{{opacity:0,scaleY:0.2}},{{opacity:1,scaleY:1,duration:0.4,ease:"power3.out"}},0.1);\n'
              f'tl.fromTo("#{seg.id}-stk",{{x:-300}},{{x:200,duration:{seg.d:.2f},ease:"none"}},0);\n')
        y_lab, y_big = 852, 1000
        pdef = ("circle", W - 36 - 240, 162, 240, 240)
    elif mode == "brush":
        body, s = graphic_bg(film, seg, photo=d.get("video") or seg.bg)
        body += '<div class="ab" style="inset:0;background:radial-gradient(circle at 50% 45%,rgba(0,0,0,.1),rgba(0,0,0,.7) 75%)"></div>'
        y_lab, y_big = 560, 690
        pdef = style_pip(film, seg)
    else:  # block：引号文字块压在实拍上
        body, s = graphic_bg(film, seg)
        if d.get("video"):
            body += band(film, seg, d["video"], 330, h=760)
            s += f'tl.fromTo("#{seg.id}-bandw",{{opacity:0}},{{opacity:1,duration:0.5}},0);\n'
        body += f'<div class="ab" data-safe-bleed style="left:0;top:330px;width:760px;height:760px;background:linear-gradient(90deg,rgba(10,14,22,.92),rgba(10,14,22,.6) 70%,transparent)"></div>'
        lines = d.get("lines") or [x for x in ({"text": d.get("lab1", ""), "t": d.get("t1")}, {"text": d.get("big1", ""), "em": True, "t": d.get("t1")}) if x["text"]]
        lh = ""
        for k, ln in enumerate(lines):
            col = st.c.get("li", "#B9A6FF") if ln.get("em") else "#F2F5FF"
            fs = 70 if ln.get("em") else 48
            lh += f'<div id="{seg.id}-q{k}" style="font:400 {fs}px/1.35 SM;color:{col};opacity:0;white-space:nowrap">{rich(ln["text"])}</div>'
        body += (f'<div class="ab" style="left:60px;top:430px"><div style="font:400 120px/0.8 SR,serif;color:{st.c["a"]}">“</div>{lh}</div>')
        for k, ln in enumerate(lines):
            s += f'tl.fromTo("#{seg.id}-q{k}",{{opacity:0,x:-30}},{{opacity:1,x:0,duration:0.4,ease:"power3.out"}},{seg.at_t(ln, t1 + k * 0.35):.3f});\n'
        ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", W - 36 - 230, 170, 230, 230)))
        seg.cap_y_set = 1150
        film.sfx_at(seg, t1, "swoosh")
        film.scene(seg.id, body + ph, s + ps, css)
        return
    big_cls = "TB" if mode == "brush" else d.get("cls1", "T1")
    rv = d.get("reveal") == "chars"
    fs1 = d.get("fs1") or min(190 if mode == "brush" else 150, fit_fs(d["big1"], 980, 190 if mode == "brush" else 150))
    yb = {1: y_big, 2: y_big}
    if mode == "banner":  # 光带高 240：两行大字缩字号，并在光带里上下居中
        for k_, key_ in ((1, "big1"), (2, "big2")):
            txt_ = d.get(key_) or ""
            nl_ = txt_.count("|") + 1
            if not txt_:
                continue
            cap_ = int(200 / (nl_ * 1.05))
            if k_ == 1 and not d.get("fs1"):
                fs1 = min(fs1, cap_)
            fsk = fs1 if k_ == 1 else (d.get("fs2") or min(cap_, fit_fs(txt_, 980, 170)))
            if k_ == 2:
                d["fs2"] = fsk
            yb[k_] = 950 + (240 - nl_ * fsk * 1.05) / 2
    body += (f'<div id="{seg.id}-lab1" data-layout-allow-overlap class="head" style="top:{y_lab}px"><h2 style="font-size:{56 if mode != "banner" else 48}px">{rich(d.get("lab1", ""))}</h2><p>{rich(d.get("en1", ""))}</p></div>'
             f'<div id="{seg.id}-big1" data-layout-allow-overlap class="ab {"" if rv else big_cls}" style="left:0;right:0;top:{yb[1]:.0f}px;text-align:center;font-size:{fs1}px;line-height:1.05;letter-spacing:{10 if mode == "brush" else 6}px;opacity:0">{chars(d["big1"], big_cls) if rv else rich(d["big1"])}</div>')
    if not d.get("lab1"):
        body = body.replace(f'<div id="{seg.id}-lab1" class="head"', f'<div id="{seg.id}-lab1" data-layout-allow-overlap class="head" data-empty="1"', 1)
    if d.get("big2"):
        fs2 = d.get("fs2") or min(190 if mode == "brush" else 170, fit_fs(d["big2"], 980, 190 if mode == "brush" else 170))
        cls2 = "TB" if mode == "brush" else d.get("cls2", "T2")
        body += (f'<div id="{seg.id}-lab2" data-layout-allow-overlap class="head" style="top:{y_lab}px;opacity:0"><h2 style="font-size:{56 if mode != "banner" else 48}px">{rich(d.get("lab2", ""))}</h2><p>{rich(d.get("en2", ""))}</p></div>'
                 f'<div id="{seg.id}-big2" data-layout-allow-overlap class="ab {"" if rv else cls2}" style="left:0;right:0;top:{yb[2]:.0f}px;text-align:center;font-size:{fs2}px;line-height:1.05;letter-spacing:6px;opacity:0">{chars(d["big2"], cls2) if rv else rich(d["big2"])}</div>')
    s += f'tl.fromTo("#{seg.id}-lab1",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.4,ease:"power3.out"}},0.05);\n'
    if rv:
        s += chars_in(f"#{seg.id}-big1", t1, len(plain(d["big1"])), d.get("per") or film.reveal_per(d["big1"], seg))
    else:
        s += brush_in(st, f"#{seg.id}-big1", t1) if mode == "brush" else st.title_in(f"#{seg.id}-big1", t1)
    film.sfx_at(seg, t1, "impact" if mode != "banner" else "whoosh")
    if d.get("big2"):
        t2 = t2 if t2 is not None else seg.d * 0.55
        s += (f'tl.to(["#{seg.id}-big1","#{seg.id}-lab1"],{{opacity:0,y:-30,duration:0.3,ease:"power2.in"}},{t2 - 0.2:.3f});\n'
              f'tl.fromTo("#{seg.id}-lab2",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.35,ease:"power3.out"}},{t2:.3f});\n')
        if rv:
            s += chars_in(f"#{seg.id}-big2", t2 + 0.25, len(plain(d["big2"])), d.get("per") or film.reveal_per(d["big2"], seg))
        else:
            s += brush_in(st, f"#{seg.id}-big2", t2 + 0.25) if mode == "brush" else st.title_in(f"#{seg.id}-big2", t2 + 0.25)
        film.sfx_at(seg, t2 + 0.25, "impact", 0.2)
    ph, ps = put_pip(film, seg, pip_spec(film, seg, pdef), 0.2, 10)
    body += ph
    s += ps
    seg.cap_y_set = 1330
    film.scene(seg.id, body, s, css)


# ================================================================ 10 章节卡（按风格五种做法）
def chapter(film, seg):
    """data: zh, en, zh2（第二行，可选）, questions[{text,t}]（金框铭牌用）, t。"""
    d = seg.data
    st = film.st
    mode = d.get("mode", st.chapter)
    t = min(seg.at("t", 0.2), max(0.2, seg.d * 0.25))  # 章节卡是段落开头，标题要先出来；关键词常在句尾，不能等
    rng = film.rng(seg)
    body, s = graphic_bg(film, seg, pattern=False)
    zh = d["zh"]
    fs = min(170, fit_fs(zh, 900, 170))
    if mode == "marquee":
        names = film.motif or ["shield-check", "briefcase"]

        def row(rid, y):
            cells = "".join(
                f'<div class="ab" style="left:{k * 150}px;top:0;width:120px;height:120px;border-radius:14px;background:linear-gradient(180deg,#5A3A2A,#2E1D14);'
                f'box-shadow:inset 0 1px 0 rgba(255,255,255,.15),0 10px 20px rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center">'
                f'{icon(names[k % len(names)], 64, st.c["a"], 1.8)}</div>' for k in range(16))
            return f'<div id="{rid}" class="ab" data-layout-ignore style="left:-150px;top:{y}px;width:2400px;height:120px">{cells}</div>'
        body += row(f"{seg.id}-r1", 300) + row(f"{seg.id}-r2", 1120)
        body += (f'<div id="{seg.id}-tt" class="ab T1" style="left:0;right:0;top:{700 - fs / 2:.0f}px;text-align:center;font-size:{fs}px;line-height:1;letter-spacing:0.08em;opacity:0">{rich(zh)}</div>'
                 f'<div id="{seg.id}-en" class="ab EN" style="left:0;right:0;top:{720 + fs / 2:.0f}px;text-align:center;opacity:0">{rich(d.get("en", ""))}</div>')
        s += (f'tl.fromTo("#{seg.id}-r1",{{x:0}},{{x:-300,duration:{seg.d:.2f},ease:"none"}},0);\n'
              f'tl.fromTo("#{seg.id}-r2",{{x:-300}},{{x:0,duration:{seg.d:.2f},ease:"none"}},0);\n'
              f'tl.fromTo(["#{seg.id}-r1","#{seg.id}-r2"],{{opacity:0}},{{opacity:0.9,duration:0.5}},0);\n'
              + st.title_in(f"#{seg.id}-tt", t) + st.sub_in(f"#{seg.id}-en", t + 0.4))
    elif mode == "plaque":
        qs = d.get("questions", [])
        ph_ = 420 + 110 * len(qs)
        qh = "".join(
            f'<div id="{seg.id}-q{k}" class="ab" style="left:90px;right:90px;top:{330 + k * 110}px;height:84px;border-radius:14px;'
            f'background:linear-gradient(180deg,#1A1714,#0D0C0B);border:1.5px solid rgba(255,255,255,.18);text-align:center;font:400 46px/84px SM;color:#F6E7C2;opacity:0">{rich(q["text"])}</div>'
            for k, q in enumerate(qs))
        body += (f'<div id="{seg.id}-pf" class="fl" style="left:140px;top:{max(180, 700 - ph_ / 2):.0f}px;width:800px;height:{ph_}px">'
                 f'<div id="{seg.id}-pl" class="card" style="left:0;top:0;width:800px;height:{ph_}px;opacity:0"><div class="dash"></div>'
                 f'<div class="ab T1" style="left:0;right:0;top:60px;text-align:center;font-size:{min(130, fs)}px;line-height:1;letter-spacing:12px">{rich(zh)}</div>'
                 f'<div class="ab EN" style="left:0;right:0;top:{80 + min(130, fs)}px;text-align:center">{rich(d.get("en", ""))}</div>'
                 f'<div class="ab" style="left:120px;right:120px;top:{140 + min(130, fs)}px;height:2px;background:linear-gradient(90deg,transparent,{st.c["a"]},transparent)"></div>'
                 f'{qh}</div></div>')
        s += (f'tl.set("#{seg.id}-pl",{{transformPerspective:1400}},0);\n'
              f'tl.fromTo("#{seg.id}-pl",{{opacity:0,rotationY:-30,rotationX:10,scale:0.9}},{{opacity:1,rotationY:-8,rotationX:4,scale:1,duration:0.8,ease:"power3.out"}},{t:.3f});\n'
              + sway(f"#{seg.id}-pf", seg.d, 4, 5.0, t + 0.8))
        for k, q in enumerate(qs):
            qt = seg.at_t(q, t + 0.8 + k * 0.7)
            s += f'tl.fromTo("#{seg.id}-q{k}",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.4,ease:"back.out(1.6)"}},{qt:.3f});\n'
            film.sfx_at(seg, qt, "snap")
    elif mode == "split":
        zh2 = d.get("zh2", "")
        body += motif_pattern(film, seg)
        s += f'tl.fromTo("#{seg.id}-motif",{{y:0}},{{y:-150,duration:{seg.d:.2f},ease:"none"}},0);\n'
        a, m = st.c["a"], st.c["m"]
        body += (f'<div id="{seg.id}-pa" class="ab" data-safe-bleed style="left:0;top:420px;width:560px;height:300px;background:linear-gradient(90deg,{a}CC,{a}55);clip-path:polygon(0 0,100% 0,88% 100%,0 100%)"></div>'
                 f'<div id="{seg.id}-pb" class="ab" data-safe-bleed style="left:520px;top:760px;width:560px;height:300px;background:linear-gradient(270deg,{m}CC,{m}55);clip-path:polygon(12% 0,100% 0,100% 100%,0 100%)"></div>'
                 f'<div id="{seg.id}-t1" class="ab T1" style="left:50px;top:500px;font-size:{min(120, fit_fs(zh, 460, 120))}px;letter-spacing:10px;opacity:0">{rich(zh)}</div>'
                 f'<div id="{seg.id}-e1" class="ab EN" style="left:56px;top:650px;color:#fff;opacity:0">{rich(d.get("en", ""))}</div>'
                 f'<div id="{seg.id}-t2" class="ab TB" style="right:50px;top:820px;font-size:{min(130, fit_fs(zh2 or zh, 460, 130))}px;letter-spacing:6px;opacity:0">{rich(zh2)}</div>'
                 f'<div id="{seg.id}-cube" class="ab" style="left:470px;top:640px;width:140px;height:200px;background:linear-gradient(135deg,#FFD84A,#C79A10);box-shadow:0 0 30px rgba(255,200,40,.6);'
                 f'display:flex;align-items:center;justify-content:center;opacity:0">{icon((film.motif or ["star"])[0], 86, "#2A1A00", 2.2)}</div>')
        s += (f'tl.fromTo("#{seg.id}-pa",{{x:-600}},{{x:0,duration:0.5,ease:"power3.out"}},{t:.3f});\n'
              f'tl.fromTo("#{seg.id}-pb",{{x:600}},{{x:0,duration:0.5,ease:"power3.out"}},{t + 0.15:.3f});\n'
              + st.title_in(f"#{seg.id}-t1", t + 0.4) + st.sub_in(f"#{seg.id}-e1", t + 0.6)
              + brush_in(st, f"#{seg.id}-t2", t + 0.7)
              + f'tl.set("#{seg.id}-cube",{{transformPerspective:800}},0);\n'
              f'tl.fromTo("#{seg.id}-cube",{{opacity:0,rotationY:-90}},{{opacity:1,rotationY:-25,duration:0.6,ease:"back.out(1.6)"}},{t + 0.3:.3f});\n'
              f'tl.fromTo("#{seg.id}-cube",{{rotationY:-25}},{{rotationY:25,duration:{max(0.5, seg.d - t - 1):.2f},ease:"sine.inOut"}},{t + 0.9:.3f});\n')
    elif mode == "hud":
        a = st.c["a"]
        rings = "".join(f'<div id="{seg.id}-h{k}" class="ab" style="left:{540 - r}px;top:{700 - r}px;width:{2 * r}px;height:{2 * r}px;border-radius:50%;'
                        f'border:{3 if k == 0 else 2}px {"solid" if k != 1 else "dashed"} {a};opacity:{0.9 - k * 0.25};box-shadow:0 0 {30 - k * 8}px {a}88"></div>'
                        for k, r in enumerate((300, 360, 430)))
        body += rings + (f'<div class="ab" style="left:300px;top:460px;width:480px;height:480px;border-radius:50%;background:radial-gradient(circle,rgba(20,30,50,.95),rgba(20,30,50,.75))"></div>'
                         f'<div id="{seg.id}-tt" class="ab T1" style="left:0;right:0;top:{690 - min(130, fs) / 2:.0f}px;text-align:center;font-size:{min(130, fit_fs(zh, 420, 130))}px;line-height:1;opacity:0">{rich(zh)}</div>'
                         f'<div id="{seg.id}-en" class="ab EN" style="left:0;right:0;top:{720 + min(130, fs) / 2:.0f}px;text-align:center;opacity:0">{rich(d.get("en", ""))}</div>')
        s += "".join(f'tl.fromTo("#{seg.id}-h{k}",{{scale:0.6,rotation:0}},{{scale:1,rotation:{(-1) ** k * 60},duration:{seg.d:.2f},ease:"power1.out"}},0);\n' for k in range(3))
        s += st.title_in(f"#{seg.id}-tt", t) + st.sub_in(f"#{seg.id}-en", t + 0.4)
    else:  # orn：金属大字＋纹饰
        body += (f'<div id="{seg.id}-rays" class="ab" data-layout-ignore style="left:-420px;top:-500px;width:1920px;height:2600px;background:repeating-conic-gradient(from 0deg at 50% 46%,rgba({st.c.get("argb", "242,178,122")},.12) 0deg 1.4deg,transparent 1.4deg 8deg);-webkit-mask:radial-gradient(circle at 50% 46%,transparent 14%,#000 60%)"></div>'
                 f'<div id="{seg.id}-head" class="head" style="top:{560 - fs / 2:.0f}px"><div class="orn"><i></i><s></s><i class="r"></i></div></div>'
                 f'<div id="{seg.id}-tt" class="ab T1" style="left:0;right:0;top:{620 - fs / 2:.0f}px;text-align:center;font-size:{fs}px;line-height:1;letter-spacing:10px;opacity:0">{rich(zh)}</div>'
                 f'<div id="{seg.id}-en" class="ab EN" style="left:0;right:0;top:{650 + fs / 2:.0f}px;text-align:center;opacity:0">{rich(d.get("en", ""))}</div>')
        s += (f'tl.fromTo("#{seg.id}-rays",{{rotation:0}},{{rotation:10,duration:{seg.d:.2f},ease:"none"}},0);\n'
              + head_in(film, seg, t) + st.title_in(f"#{seg.id}-tt", t + 0.1) + st.sub_in(f"#{seg.id}-en", t + 0.5))
    film.sfx_at(seg, t, "whoosh")
    if not d.get("no_pip"):
        ph, ps = put_pip(film, seg, pip_spec(film, seg, style_pip(film, seg)))
        body += ph
        s += ps
    seg.cap_y_set = 1330
    film.scene(seg.id, body, s)


# ================================================================ 11 机构墙（档案招牌）
def logo_wall(film, seg):
    """data: names[…]（6–9 个，文字做成名牌）, seal{index,text,t}（盖章，可选）, t。人物竖窗放上方。"""
    d = seg.data
    st = film.st
    names = d["names"][:9]
    bg, s = graphic_bg(film, seg)
    fonts = ["SR", "EN", "NUM", "SM"]
    tiles = ""
    cols = 3
    tw_, th = 330, 150
    for k, nm in enumerate(names):
        x = 30 + (k % cols) * (tw_ + 15)
        y = 730 + (k // cols) * (th + 16)
        f = fonts[k % len(fonts)]
        fs = min(46, fit_fs(nm, tw_ - 40, 46, 22))
        tiles += (f'<div id="{seg.id}-t{k}" class="paper" style="left:{x}px;top:{y}px;width:{tw_}px;height:{th}px;border-radius:12px;display:flex;align-items:center;justify-content:center;'
                  f'text-align:center;font:{"600" if f == "EN" else "400"} {fs}px/1.1 {f},SM;color:#1E2A3A;letter-spacing:1px;padding:0 16px">{rich(nm)}</div>')
    body = bg + f'<div id="{seg.id}-wall" class="ab" style="left:0;top:0;width:1080px;height:1576px">{tiles}</div>'
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("rect", 360, 156, 360, 440)), 0.1, 6)
    body += ph
    t0 = seg.at("t", 0.3)
    s += (f'tl.fromTo([{",".join(chr(34) + "#" + seg.id + "-t" + str(k) + chr(34) for k in range(len(names)))}],{{opacity:0,y:40}},'
          f'{{opacity:1,y:0,duration:0.4,stagger:0.06,ease:"power3.out"}},{t0:.3f});\n'
          f'tl.fromTo("#{seg.id}-wall",{{x:6}},{{x:-6,duration:{seg.d:.2f},ease:"none"}},0);\n' + ps)
    film.sfx_at(seg, t0, "swoosh")
    if d.get("seal"):
        sl = d["seal"]
        k = sl.get("index", 0)
        x = 30 + (k % cols) * (tw_ + 15) + tw_ - 64
        y = 730 + (k // cols) * (th + 16) - 44
        body += f'<div id="{seg.id}-seal" class="seal" style="left:{x}px;top:{y}px;opacity:0">{rich(sl.get("text", "破产"))}</div>'
        stt = seg.at_t(sl, seg.d * 0.6)
        s += st.stamp_in(f"#{seg.id}-seal", stt)
        film.sfx_at(seg, stt, "impact")
    seg.cap_y_set = 590
    film.scene(seg.id, body, s, ".seal{position:absolute;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle at 38% 32%,#F07A3A,#C2361A 55%,#8E220E);box-shadow:0 6px 14px rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;font:400 38px/1 SM;color:rgba(255,236,220,.92)}")


# ================================================================ 12 文件高亮
def doc(film, seg):
    """data: source（来源，如「某报 2025-07」）, headline, highlight（标题里要高亮的那几个字）, lines[…], t_hi。"""
    d = seg.data
    st = film.st
    bg, s = graphic_bg(film, seg)
    hl = d["headline"]
    key = d.get("highlight", "")
    if key and key in hl:
        a, b = hl.split(key, 1)
        hl_html = f'{rich(a)}<span style="position:relative;display:inline-block;isolation:isolate"><span id="{seg.id}-mk" style="position:absolute;left:-6px;right:-6px;top:18%;bottom:6%;background:#FFE45C;transform-origin:0 50%;z-index:-1"></span>{rich(key)}</span>{rich(b)}'
    else:
        hl_html = rich(hl)
    lines = "".join(f'<div style="font:400 34px/1.7 SR,serif;color:#3A3530">{rich(l)}</div>' for l in d.get("lines", []))
    fs = min(68, fit_fs(hl, 900, 68))
    body = bg + (f'<div id="{seg.id}-pf" class="fl" data-layout-allow-overflow style="left:-40px;top:300px;width:1160px;height:820px">'
                 f'<div id="{seg.id}-pp" class="paper" data-layout-allow-overlap style="left:0;top:0;width:1160px;height:820px;padding:90px 110px;isolation:isolate">'
                 f'<div style="font:600 22px/1 EN,Inter;letter-spacing:3px;color:#9A8F80;margin-bottom:40px">{rich(d.get("source", ""))}</div>'
                 f'<div style="font:400 {fs}px/1.3 SM;color:#16120E;position:relative;z-index:1">{hl_html}</div>'
                 f'<div style="height:2px;background:rgba(0,0,0,.12);margin:40px 0"></div>{lines}</div></div>')
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", W - 36 - 240, 162, 240, 240) if st.pip["shape"] != "rect" else ("rect", W - 40 - 220, 162, 220, 270)), 0.3)
    body += ph
    th = seg.at("t_hi", 1.0)
    s += (f'tl.set("#{seg.id}-pp",{{transformPerspective:1800,transformOrigin:"50% 0%"}},0);\n'
          f'tl.fromTo("#{seg.id}-pp",{{opacity:0,rotation:-2,rotationX:30,y:120}},{{opacity:1,rotation:-7,rotationX:14,y:0,duration:0.7,ease:"power3.out"}},0.05);\n'
          + floaty(f"#{seg.id}-pf", seg.d, 6, 4.4, 0.8) + ps)
    if key and key in hl:
        s += f'tl.fromTo("#{seg.id}-mk",{{scaleX:0}},{{scaleX:1,duration:0.45,ease:"power2.out"}},{th:.3f});\n'
        film.sfx_at(seg, th, "snap")
    film.sfx_at(seg, 0.05, "swoosh")
    seg.cap_y_set = 1330  # 纸面下沿约 1250，字幕不压在白纸上
    film.scene(seg.id, body, s)


# ================================================================ 13 两段对比（A vs B）
def _compare_side(film, seg):
    """data: title{zh,en}（可选）, a{label,value,icon,n}, b{label,value,icon,n}, t_a, t_b, mult{text,t}（倍数大字，可选）。"""
    d = seg.data
    st = film.st
    rng = film.rng(seg)
    bg, s = graphic_bg(film, seg)
    body = bg
    if d.get("title"):
        body += header(film, seg, d["title"]["zh"], d["title"]["en"], 150)
        s += head_in(film, seg)
    panels = ""
    for k, key in enumerate(("a", "b")):
        p = d[key]
        x = 40 + k * 520
        n = int(p.get("n", 3 if k == 0 else 12))
        per_row = 6
        size = 64
        icons = "".join(f'<div class="ab" style="left:{30 + (i % per_row) * 74}px;top:{240 + (i // per_row) * 70}px">{icon(p.get("icon", "package"), size, st.c["a"], 1.8)}</div>' for i in range(min(n, 18)))
        fsv = min(110, fit_fs(p["value"], 440, 110))
        panels += (f'<div id="{seg.id}-{key}f" class="fl" style="left:{x}px;top:{430 if not d.get("title") else 480}px;width:480px;height:520px">'
                   f'<div id="{seg.id}-{key}" class="card" style="left:0;top:0;width:480px;height:520px;opacity:0"><div class="dash"></div><div id="{seg.id}-{key}-g" class="glow"></div>'
                   f'<div class="ab" style="left:30px;top:34px;font:400 40px/1 SM;opacity:.8">{rich(p["label"])}</div>'
                   f'<div class="ab numt" style="left:26px;top:96px;font-size:{fsv}px">{rich(p["value"])}</div>{icons}</div></div>')
    body += panels
    if d.get("mult"):
        my = 1010 if st.key == "kuangshi" else 1040
        body += f'<div id="{seg.id}-m" class="ab T1" style="left:0;right:0;top:{my}px;text-align:center;font-size:{110 if st.key == "kuangshi" else 130}px;line-height:1;opacity:0">{rich(d["mult"]["text"])}</div>'
    ph, ps = put_pip(film, seg, pip_spec(film, seg, style_pip(film, seg) if st.key != "kuangshi" else ("squircle", (W - 240) / 2, 1190, 240, 240)))
    body += ph
    ta, tb = seg.at("t_a", 0.3), seg.at("t_b", seg.d * 0.45)
    s += st.card_in(f"#{seg.id}-a", ta, 0, rng, "left") + f'tl.fromTo("#{seg.id}-a-g",{{opacity:0}},{{opacity:1,duration:0.3}},{ta + 0.3:.3f});\n'
    s += st.card_in(f"#{seg.id}-b", tb, 1, rng, "right") + f'tl.fromTo("#{seg.id}-b-g",{{opacity:0}},{{opacity:1,duration:0.3}},{tb + 0.3:.3f});\n'
    s += f'tl.to("#{seg.id}-a-g",{{opacity:0,duration:0.3}},{tb:.3f});\n'
    s += floaty(f"#{seg.id}-af", seg.d, 8, 3.4, 0) + floaty(f"#{seg.id}-bf", seg.d, 8, 3.4, 1.1) + ps
    film.sfx_at(seg, ta, "swoosh"); film.sfx_at(seg, tb, "swoosh")
    if d.get("mult"):
        mt = seg.at_t(d["mult"], tb + 1.0)
        s += st.title_in(f"#{seg.id}-m", mt)
        film.sfx_at(seg, mt, "impact")
    seg.cap_y_set = 1330 if st.key != "kuangshi" else 1150
    film.scene(seg.id, body, s)


# ================================================================ 14 全屏大数字
def bignum(film, seg):
    """data: pre（数字上方一行）, from, to, prefix, suffix, decimals, sub（下方一行）, t, dur, light（true 时用浅色底，瓷蓝式产品白）。"""
    d = seg.data
    st = film.st
    light = d.get("light", st.key == "cilan")
    if light:
        body = '<div class="ab" style="inset:0;background:linear-gradient(160deg,#F4F6FA,#DCE2EC)"></div>'
        s = ""
        if seg.bg:
            body += f'<div id="{seg.id}-bg" class="ab" style="left:-60px;top:-60px;width:1200px;height:2040px;background:url(\'{film.a(seg.bg)}\') center/cover;opacity:.55"></div>'
            s += drift(f"#{seg.id}-bg", seg.d)
        body += BG_END
        col, pre_col = "#14285C", "#4A5675"
    else:
        body, s = graphic_bg(film, seg)
        col, pre_col = None, None
    to = float(d["to"]); fr = float(d.get("from", 0)); dec = int(d.get("decimals", 0))
    txt = f'{d.get("prefix", "")}{to:,.{dec}f}{d.get("suffix", "")}'
    fs = min(200, int(980 / (len(txt) * 0.5)))
    sid = seg.id.replace("-", "_")
    num_style = f"color:{col};text-shadow:0 10px 30px rgba(20,40,92,.25)" if light else ""
    body += (f'<div id="{seg.id}-pre" class="ab" style="left:0;right:0;top:{700 - fs / 2 - 80:.0f}px;text-align:center;font:400 44px/1 SM;color:{pre_col or "rgba(255,255,255,.8)"};opacity:0">{rich(d.get("pre", ""))}</div>'
             f'<div id="{seg.id}-n" class="ab numt" style="left:0;right:0;top:{700 - fs / 2:.0f}px;text-align:center;font-size:{fs}px;{num_style};opacity:0">'
             f'{rich(d.get("prefix", ""))}<span id="{seg.id}-v">{fr:,.{dec}f}</span>{rich(d.get("suffix", ""))}</div>'
             f'<div id="{seg.id}-sub" class="ab" style="left:0;right:0;top:{720 + fs / 2:.0f}px;text-align:center;font:400 40px/1 SM;color:{pre_col or "rgba(255,255,255,.75)"};opacity:0">{rich(d.get("sub", ""))}</div>')
    ph, ps = put_pip(film, seg, pip_spec(film, seg, style_pip(film, seg)))
    body += ph
    t = seg.at("t", 0.3)
    dur = float(d.get("dur", 1.3))
    s += (f'tl.fromTo("#{seg.id}-pre",{{opacity:0,y:16}},{{opacity:1,y:0,duration:0.4}},{max(0, t - 0.2):.3f});\n'
          f'tl.fromTo("#{seg.id}-n",{{opacity:0,scale:0.9}},{{opacity:1,scale:1,duration:0.4,ease:"power3.out"}},{t:.3f});\n'
          f'const {sid}_o={{v:{fr}}};const {sid}_e=document.getElementById("{seg.id}-v");\n'
          f'tl.fromTo({sid}_o,{{v:{fr}}},{{v:{to},duration:{dur},ease:"power2.out",onUpdate:()=>{{{sid}_e.textContent={sid}_o.v.toLocaleString("en-US",{{minimumFractionDigits:{dec},maximumFractionDigits:{dec}}});}}}},{t:.3f});\n'
          f'tl.fromTo("#{seg.id}-sub",{{opacity:0,y:16}},{{opacity:1,y:0,duration:0.4}},{t + dur:.3f});\n' + ps)
    film.sfx_at(seg, t, "whoosh")
    seg.cap_y_set = 1330
    film.scene(seg.id, body, s)


# ================================================================ 15 全屏环形关系图
def ring_full(film, seg):
    """data: center[中文,英文], tiles[[中文,英文]×4], t, tiles_t[…]。"""
    d = seg.data
    st = film.st
    a = st.c["a"]
    body, s = graphic_bg(film, seg)
    R, cx, cy = 300, 540, 760
    pos = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    tiles = ""
    for k, (zh, en) in enumerate(d["tiles"][:4]):
        tiles += (f'<div id="{seg.id}-t{k}" class="card" style="left:{cx + pos[k][0] * R * 0.95 - 110:.0f}px;top:{cy + pos[k][1] * R * 0.7 - 65:.0f}px;width:220px;height:130px;padding:24px 0;text-align:center;opacity:0">'
                  f'<div class="t" style="font-size:50px">{rich(zh)}</div><div class="e" style="margin-top:8px;font-size:14px">{rich(en)}</div></div>')
    body += (f'<div id="{seg.id}-r" class="ab" style="left:{cx - R}px;top:{cy - R}px;width:{2 * R}px;height:{2 * R}px;opacity:0">'
             f'<div class="ab" style="inset:0;border-radius:50%;border:4px solid {a};box-shadow:0 0 40px {a}AA,inset 0 0 40px {a}66"></div>'
             f'<svg id="{seg.id}-arc" class="ab" style="left:-30px;top:-30px" width="{2 * R + 60}" height="{2 * R + 60}"><circle cx="{R + 30}" cy="{R + 30}" r="{R + 18}" fill="none" stroke="{a}" stroke-width="5" stroke-dasharray="160 80 40 80" opacity=".7"/></svg>'
             f'<div class="card" style="left:{R - 160}px;top:{R - 160}px;width:320px;height:320px;border-radius:50%;text-align:center;padding-top:100px">'
             f'<div class="t" style="font-size:68px">{rich(d["center"][0])}</div><div class="e">{rich(d["center"][1])}</div></div></div>{tiles}')
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", 425, 166, 230, 230) if st.pip["shape"] != "rect" else ("rect", 425, 162, 230, 290)))
    body += ph
    t = seg.at("t", 0.3)
    s += (f'tl.fromTo("#{seg.id}-r",{{opacity:0,scale:0.6}},{{opacity:1,scale:1,duration:0.6,ease:"back.out(1.5)"}},{t:.3f});\n'
          f'tl.fromTo("#{seg.id}-arc",{{rotation:0}},{{rotation:160,duration:{seg.d:.2f},ease:"none"}},0);\n' + ps)
    tt = d.get("tiles_t") or [None] * 4
    for k in range(min(4, len(d["tiles"]))):
        tk = seg.L(tt[k]) if tt[k] is not None else t + 0.5 + k * 0.3
        s += st.card_in(f"#{seg.id}-t{k}", tk, k, film.rng(seg, k), "up")
        film.sfx_at(seg, tk, "snap")
    seg.cap_y_set = 1250
    film.scene(seg.id, body, s)


# ================================================================ 16 霓虹产品排
def product_row(film, seg):
    """data: title{zh,en}, items[{label,sub,icon,t}]（3–4，比如三代产品、三个阶段）。"""
    d = seg.data
    st = film.st
    a = st.c["a"]
    items = d["items"][:4]
    n = len(items)
    bg, s = graphic_bg(film, seg, pattern=True)
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
    w_ = 300 if n <= 3 else 230
    gap = (W - 92 - n * w_) / max(1, n - 1)  # 整排有 3D 倾斜，两边各留 46
    cards = ""
    for k, it in enumerate(items):
        x = 46 + k * (w_ + gap)
        cards += (f'<div id="{seg.id}-p{k}f" class="fl" style="left:{x:.0f}px;top:{560 + k * 30}px;width:{w_}px;height:420px">'
                  f'<div id="{seg.id}-p{k}" class="card" style="left:0;top:0;width:{w_}px;height:420px;opacity:0;text-align:center"><div class="dash"></div><div id="{seg.id}-p{k}-g" class="glow"></div>'
                  f'<div style="margin-top:60px">{icon(it.get("icon", "box"), 120, "#FFFFFF", 1.4)}</div>'
                  f'<div class="t" style="margin-top:40px;font-size:{min(60, fit_fs(it["label"], w_ - 40, 60))}px">{rich(it["label"])}</div>'
                  f'<div class="e">{rich(it.get("sub", ""))}</div></div></div>')
    body += f'<div id="{seg.id}-row" class="ab" style="left:0;top:0;width:1080px;height:1576px">{cards}</div>'
    body += f'<div class="ab" style="left:46px;right:46px;top:1060px;height:2px;background:linear-gradient(90deg,transparent,{a},transparent);box-shadow:0 0 12px {a}"></div>'
    ph, ps = put_pip(film, seg, pip_spec(film, seg, style_pip(film, seg) if st.key != "kuangshi" else ("squircle", (W - 260) / 2, 1110, 260, 260)))
    body += ph
    s += head_in(film, seg) + ps
    s += f'tl.set("#{seg.id}-row",{{transformPerspective:1600}},0);\ntl.fromTo("#{seg.id}-row",{{rotationY:-14}},{{rotationY:-6,duration:{seg.d:.2f},ease:"none"}},0);\n'
    times = seg.times(items, first=0.5)
    for k, t in enumerate(times):
        s += st.card_in(f"#{seg.id}-p{k}", t, k, film.rng(seg, k), "up") + f'tl.fromTo("#{seg.id}-p{k}-g",{{opacity:0}},{{opacity:1,duration:0.3}},{t + 0.1:.3f});\n'
        if k > 0:
            s += f'tl.to("#{seg.id}-p{k - 1}-g",{{opacity:0,duration:0.3}},{t:.3f});\n'
        s += floaty(f"#{seg.id}-p{k}f", seg.d, 7, 3.4, k * 0.7)
        film.sfx_at(seg, t, "snap")
    seg.cap_y_set = 1330 if st.pip["shape"] != "rect" else 1120
    film.scene(seg.id, body, s)


# ================================================================ 17 结尾
def ending(film, seg):
    """data: pre{zh,en}（引子，可选）, big1, t1, big2, t2, t_end（落版时间）, name[名, 后缀], tagline（英文一行）。按风格的金句做法出两行大字，最后落署名牌。"""
    d = seg.data
    st = film.st
    t1 = seg.at("t1", 0.5)
    t2 = seg.at("t2", seg.d * 0.5)
    te = seg.at("t_end", seg.d - 1.4)
    mode = st.quote if st.quote != "block" else "particles"
    css = ""
    if mode == "particles":
        argb = st.c.get("argb", "255,196,140")
        p1, c1 = pband(seg, 1, 540, 640, 380, 60, argb)
        p2, c2 = pband(seg, 2, 540, 1160, 380, 60, argb)
        css = c1 + c2
        body = f'<div class="bgbase"></div><div class="ab" style="inset:0;background:radial-gradient(circle at 50% 46%,rgba(0,0,0,0) 8%,rgba(0,0,0,.78) 72%)"></div>{BG_END}{p1}{p2}'
        s = (f'tl.fromTo("#{seg.id}-pb1",{{opacity:0,scale:0.9}},{{opacity:1,scale:1.06,duration:{seg.d:.2f},ease:"none"}},0);\n'
             f'tl.fromTo("#{seg.id}-pb2",{{opacity:0,scale:0.9}},{{opacity:1,scale:1.06,duration:{seg.d:.2f},ease:"none"}},0);\n')
    else:
        body, s = graphic_bg(film, seg, photo=seg.bg)
    cls1 = "TB" if mode == "brush" else "T2"
    cls2 = "TB" if mode == "brush" else "T1"
    fs1 = min(150 if mode == "brush" else 96, fit_fs(d["big1"], 960, 150 if mode == "brush" else 96))
    fs2 = min(200 if mode == "brush" else 176, fit_fs(d["big2"], 960, 200 if mode == "brush" else 176))
    if d.get("pre"):
        body += f'<div id="{seg.id}-pre" data-layout-allow-overlap class="head" style="top:640px"><h2 style="font-size:56px">{rich(d["pre"]["zh"])}</h2><p>{rich(d["pre"].get("en", ""))}</p></div>'
        s += f'tl.fromTo("#{seg.id}-pre",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.4,ease:"power3.out"}},0.05);\ntl.to("#{seg.id}-pre",{{opacity:0,duration:0.3}},{t1 - 0.2:.3f});\n'
    rv = d.get("reveal") == "chars"
    body += (f'<div id="{seg.id}-b1" class="ab {"" if rv else cls1}" style="left:0;right:0;top:{800 - fs1:.0f}px;text-align:center;font-size:{fs1}px;line-height:1.1;letter-spacing:6px;opacity:0">{chars(d["big1"], cls1) if rv else rich(d["big1"])}</div>'
             f'<div id="{seg.id}-b2" class="ab {"" if rv else cls2}" style="left:0;right:0;top:850px;text-align:center;font-size:{fs2}px;line-height:1.1;letter-spacing:10px;opacity:0">{chars(d["big2"], cls2) if rv else rich(d["big2"])}</div>')
    nm = d.get("name") or film.plan.get("host", {}).get("badge", ["", ""])
    body += (f'<div id="{seg.id}-end" class="ab" style="left:0;right:0;top:1300px;text-align:center;opacity:0">'
             f'<div class="badge" style="position:relative;left:auto;top:auto;transform:none;display:inline-block">{rich(nm[0])}<b>{rich(nm[1] if len(nm) > 1 else "")}</b></div>'
             f'<div class="EN" style="margin-top:22px">{rich(d.get("tagline", ""))}</div></div>')
    for bid, txt, tt in ((f"{seg.id}-b1", d["big1"], t1), (f"{seg.id}-b2", d["big2"], t2)):
        if rv:
            s += chars_in(f"#{bid}", tt, len(plain(txt)), d.get("per") or film.reveal_per(txt, seg, 0.08))
        else:
            s += brush_in(st, f"#{bid}", tt) if mode == "brush" else st.title_in(f"#{bid}", tt)
    ph, ps = put_pip(film, seg, pip_spec(film, seg, ("circle", 770, 250, 270, 270) if st.pip["shape"] != "rect" else ("rect", 810, 220, 230, 290)), 0.2, 10)
    body += ph
    s += ps + f'tl.to("#{seg.id}-pipw",{{opacity:0,scale:0.8,duration:0.3}},{te - 0.05:.3f});\n'
    s += f'tl.fromTo("#{seg.id}-end",{{opacity:0,y:20}},{{opacity:1,y:0,duration:0.5,ease:"power3.out"}},{te:.3f});\n'
    film.sfx_at(seg, t1, "impact", 0.22); film.sfx_at(seg, t2, "impact")
    seg.no_caption = d.get("no_caption", False)
    seg.cap_y_set = 1180
    css += ".badge{height:64px;padding:0 36px;font-size:42px;line-height:64px}"
    film.scene(seg.id, body, s, css)


# ================================================================ 版式变体（同一版式的不同排法，按内容自动选，data.variant 可指定）
def _variant(film, seg, auto, choices):
    v = seg.data.get("variant")
    if v in choices:
        return v
    return auto


def _pip_low(film, seg):
    """变体用的小窗：放在左下或居中下方，不挡主体。"""
    shp = film.st.pip["shape"]
    if shp == "rect":
        return ("rect", 30, 1040, 230, 290)
    if shp == "squircle":
        return ("squircle", (W - 260) / 2, 1080, 260, 260)
    return (shp, 30, 1050, 260, 260)


def chain(film, seg):
    """编号链两种排法：list 竖向透视面板（默认）／steps 横向步骤（条目 ≤3 且都很短时自动用）。"""
    items = seg.data["items"]
    auto = "steps" if len(items) <= 3 and all(tw(it["zh"]) <= 5 for it in items) else "list"
    if _variant(film, seg, auto, ("list", "steps")) == "list":
        return _chain_list(film, seg)
    d = seg.data
    st = film.st
    n = len(items)
    bg, s = graphic_bg(film, seg)
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
    gap = 44
    cw = (W - 80 - gap * (n - 1)) / n
    ch = 470
    y0 = 470
    times = seg.times(items, first=0.8)
    for k, it in enumerate(items):
        x = 40 + k * (cw + gap)
        img = asset_or_none(film, it.get("img"))
        ih = (f'<div class="ab grade" style="left:0;top:0;right:0;height:200px;background:url(\'{img}\') center/cover;'
              f'-webkit-mask:linear-gradient(180deg,#000 55%,transparent)"></div>') if img else ""
        fs = min(56, fit_fs(it["zh"], cw - 50, 56))
        body += (f'<div id="{seg.id}-s{k}f" class="fl" style="left:{x:.0f}px;top:{y0}px;width:{cw:.0f}px;height:{ch}px">'
                 f'<div id="{seg.id}-s{k}" class="card" style="left:0;top:0;width:{cw:.0f}px;height:{ch}px;opacity:0">{ih}<div class="dash"></div>'
                 f'<div id="{seg.id}-s{k}-g" class="glow"></div>'
                 f'<div class="ab k" style="left:26px;top:150px">{k + 1}</div>'
                 f'<div class="ab t" style="left:28px;right:20px;top:290px;font-size:{fs}px">{rich(it["zh"])}</div>'
                 f'<div class="ab e" style="left:30px;top:{300 + fs * 1.2:.0f}px;margin:0">{rich(it.get("en", ""))}</div></div></div>')
        if k < n - 1:
            ax = x + cw + 6
            body += (f'<svg id="{seg.id}-a{k}" class="ab" style="left:{ax:.0f}px;top:{y0 + ch / 2 - 22:.0f}px;opacity:0" width="32" height="44">'
                     f'<polyline points="4,4 26,22 4,40" fill="none" stroke="{st.c["a"]}" stroke-width="5" stroke-linecap="round"/></svg>')
    ph, ps = put_pip(film, seg, pip_spec(film, seg, _pip_low(film, seg)))
    body += ph
    s += head_in(film, seg) + ps
    for k, t in enumerate(times):
        s += st.card_in(f"#{seg.id}-s{k}", t, k, film.rng(seg, k), "up") + f'tl.fromTo("#{seg.id}-s{k}-g",{{opacity:0}},{{opacity:1,duration:0.3}},{t + 0.1:.3f});\n'
        if k > 0:
            s += (f'tl.to("#{seg.id}-s{k - 1}-g",{{opacity:0.3,duration:0.3}},{t:.3f});\n'
                  f'tl.fromTo("#{seg.id}-a{k - 1}",{{opacity:0,x:-14}},{{opacity:1,x:0,duration:0.3}},{t - 0.15:.3f});\n')
        s += floaty(f"#{seg.id}-s{k}f", seg.d, 7, 3.4, k * 0.6)
        film.sfx_at(seg, t, "snap")
    seg.cap_y_set = CAP_Y
    film.scene(seg.id, body, s)


def bars(film, seg):
    """柱状图两种排法：vertical 竖柱（默认）／horizontal 横向排名条（给了较长的类别名时自动用）。"""
    d = seg.data
    labels = d.get("labels") or []
    auto = "horizontal" if labels and max(tw(x) for x in labels) > 2 else "vertical"
    if _variant(film, seg, auto, ("vertical", "horizontal")) == "vertical":
        return _bars_main(film, seg)
    st = film.st
    vals = d["values"]
    n = len(vals)
    vmax = max(vals)
    bg, s = graphic_bg(film, seg)
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
    row = min(92, 640 / n)
    y0 = 420
    a = st.c["a"]
    rows = ""
    for k, v in enumerate(vals):
        y = y0 + k * row
        w = 600 * v / vmax
        hi = d.get("hi") and d["hi"][0] <= k <= d["hi"][1]
        lab = labels[k] if k < len(labels) else ""
        unit = d.get("unit", "")
        rows += (f'<div class="ab" style="left:40px;top:{y + row * 0.18:.0f}px;width:290px;text-align:right;font:400 {min(40, row * 0.5):.0f}px/1.2 SM;color:#F4F0EA">{rich(lab)}</div>'
                 f'<div id="{seg.id}-h{k}" class="ab" style="left:350px;top:{y + row * 0.12:.0f}px;width:{w:.0f}px;height:{row * 0.62:.0f}px;border-radius:0 8px 8px 0;transform-origin:0 50%;'
                 f'background:linear-gradient(90deg,{a}55,{a if hi else a + "AA"});box-shadow:{"0 0 24px " + a + "88" if hi else "none"}"></div>'
                 f'<div id="{seg.id}-v{k}" class="ab numt" style="left:{360 + w:.0f}px;top:{y + row * 0.16:.0f}px;font-size:{min(40, row * 0.5):.0f}px;opacity:0">{v:g}{esc(unit)}</div>')
    body += rows + f'<div class="note" style="right:60px;top:{y0 + n * row + 20:.0f}px">{esc(d.get("note", NOTE))}</div>'
    ph, ps = put_pip(film, seg, pip_spec(film, seg, _pip_low(film, seg)))
    body += ph
    s += head_in(film, seg) + ps
    bt0 = seg.at("bars_t", 0.6)
    for k in range(n):
        tk = bt0 + k * 0.14
        s += (f'tl.fromTo("#{seg.id}-h{k}",{{scaleX:0}},{{scaleX:1,duration:0.5,ease:"power3.out"}},{tk:.2f});\n'
              f'tl.fromTo("#{seg.id}-v{k}",{{opacity:0}},{{opacity:1,duration:0.3}},{tk + 0.35:.2f});\n')
    film.sfx_at(seg, bt0, "swoosh")
    seg.cap_y_set = CAP_Y
    film.scene(seg.id, body, s)


def compare(film, seg):
    """对比两种排法：side 左右两块（默认）／stacked 上下两块（数值文字较长时自动用）。"""
    d = seg.data
    auto = "stacked" if max(tw(d["a"]["value"]), tw(d["b"]["value"])) > 5 else "side"
    if _variant(film, seg, auto, ("side", "stacked")) == "side":
        return _compare_side(film, seg)
    st = film.st
    rng = film.rng(seg)
    bg, s = graphic_bg(film, seg)
    body = bg
    top = 380
    if d.get("title"):
        body += header(film, seg, d["title"]["zh"], d["title"]["en"], 150)
        s += head_in(film, seg)
    for k, key in enumerate(("a", "b")):
        p = d[key]
        y = top + k * 330
        n = int(p.get("n", 4 if k == 0 else 12))
        icons = "".join(f'<div class="ab" style="left:{40 + i * 64}px;top:210px">{icon(p.get("icon", "package"), 54, st.c["a"], 1.8)}</div>' for i in range(min(n, 14)))
        fsv = min(96, fit_fs(p["value"], 700, 96))
        body += (f'<div id="{seg.id}-{key}f" class="fl" style="left:40px;top:{y}px;width:1000px;height:300px">'
                 f'<div id="{seg.id}-{key}" class="card" style="left:0;top:0;width:1000px;height:300px;opacity:0"><div class="dash"></div><div id="{seg.id}-{key}-g" class="glow"></div>'
                 f'<div class="ab" style="left:40px;top:34px;font:400 38px/1 SM;opacity:.8">{rich(p["label"])}</div>'
                 f'<div class="ab numt" style="left:260px;top:{100 - fsv / 2:.0f}px;font-size:{fsv}px">{rich(p["value"])}</div>{icons}</div></div>')
    if d.get("mult"):
        body += f'<div id="{seg.id}-m" class="ab T1" style="left:0;right:0;top:1030px;text-align:center;font-size:110px;line-height:1;opacity:0">{rich(d["mult"]["text"])}</div>'
    shp = st.pip["shape"]
    low = {"rect": ("rect", 30, 1150, 210, 260), "squircle": ("squircle", (W - 200) / 2, 1216, 200, 200)}.get(shp, (shp, 36, 1170, 230, 230))
    ph, ps = put_pip(film, seg, pip_spec(film, seg, low))
    body += ph
    ta, tb = seg.at("t_a", 0.3), seg.at("t_b", seg.d * 0.45)
    s += st.card_in(f"#{seg.id}-a", ta, 0, rng, "left") + f'tl.fromTo("#{seg.id}-a-g",{{opacity:0}},{{opacity:1,duration:0.3}},{ta + 0.3:.3f});\n'
    s += st.card_in(f"#{seg.id}-b", tb, 1, rng, "right") + f'tl.fromTo("#{seg.id}-b-g",{{opacity:0}},{{opacity:1,duration:0.3}},{tb + 0.3:.3f});\n'
    s += f'tl.to("#{seg.id}-a-g",{{opacity:0,duration:0.3}},{tb:.3f});\n'
    s += floaty(f"#{seg.id}-af", seg.d, 7, 3.4, 0) + floaty(f"#{seg.id}-bf", seg.d, 7, 3.4, 1.1) + ps
    film.sfx_at(seg, ta, "swoosh"); film.sfx_at(seg, tb, "swoosh")
    if d.get("mult"):
        mt = seg.at_t(d["mult"], tb + 1.0)
        s += st.title_in(f"#{seg.id}-m", mt)
        film.sfx_at(seg, mt, "impact")
    seg.cap_y_set = 1330 if st.key != "kuangshi" else 1150
    film.scene(seg.id, body, s)


def grid4(film, seg):
    """宫格两种排法：grid 2×2（默认之一）／hero 一大三小（第一格是主画面）。没指定时按种子二选一。"""
    rng = film.rng(seg, "variant")
    auto = "hero" if (seg.data.get("tiles") and seg.data["tiles"][0].get("hero")) or rng.random() < 0.5 else "grid"
    if _variant(film, seg, auto, ("grid", "hero")) == "grid":
        return _grid_2x2(film, seg)
    d = seg.data
    bg, s = graphic_bg(film, seg)
    tiles = d["tiles"][:4]
    a = film.st.c["a"]
    boxes = [(20, 430, 1040, 520)] + [(20 + i * 352, 970, 336, 252) for i in range(3)]
    html = ""
    for k, tdef in enumerate(tiles):
        x, y, w, h = boxes[k]
        src = film.a(tdef["key"])
        media = (f'<video id="{seg.id}-v{k}" class="clip{grade_cls(film, seg)}" data-start="0" data-duration="{seg.d:.3f}" src="{src}" muted playsinline style="position:absolute;inset:0;width:{w}px;height:{h}px;object-fit:cover"></video>'
                 if src.lower().endswith((".mp4", ".mov", ".webm")) else f'<div class="ab grade" style="inset:0;background:url(\'{src}\') center/cover"></div>')
        html += (f'<div id="{seg.id}-t{k}" class="ab" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;border-radius:10px;overflow:hidden;border:1.5px solid rgba(255,255,255,.14)">{media}'
                 f'<div id="{seg.id}-d{k}" class="ab" style="inset:0;background:rgba(8,8,10,.6)"></div>'
                 f'<div id="{seg.id}-k{k}" class="ab" style="inset:-1px;border-radius:10px;border:3px solid {a};box-shadow:inset 0 0 30px {a}55;opacity:0"></div>'
                 f'<div id="{seg.id}-l{k}" class="card" style="left:16px;bottom:16px;height:{64 if k else 80}px;padding:{10 if k else 14}px 18px;border-radius:12px;opacity:0">'
                 f'<div class="t" style="font-size:{34 if k else 46}px;white-space:nowrap">{rich(tdef["label"])}</div></div></div>')
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"]) + html
    shp = film.st.pip["shape"]
    ph, ps = put_pip(film, seg, pip_spec(film, seg, (shp, 806, 250, 240, 240) if shp != "rect" else ("rect", 830, 220, 210, 260)))
    body += ph
    s += head_in(film, seg) + ps
    s += f'tl.fromTo([{",".join(chr(34) + "#" + seg.id + "-t" + str(k) + chr(34) for k in range(len(tiles)))}],{{opacity:0,y:30}},{{opacity:1,y:0,duration:0.45,stagger:0.1,ease:"power3.out"}},0.15);\n'
    for k, t in enumerate(seg.times(tiles, first=0.8)):
        s += (f'tl.to("#{seg.id}-d{k}",{{opacity:0,duration:0.3}},{t:.3f});\n'
              f'tl.fromTo("#{seg.id}-k{k}",{{opacity:0}},{{opacity:1,duration:0.25}},{t:.3f});\n'
              f'tl.fromTo("#{seg.id}-l{k}",{{opacity:0,y:16}},{{opacity:1,y:0,duration:0.3,ease:"back.out(1.8)"}},{t + 0.05:.3f});\n')
        if k > 0:
            s += f'tl.to("#{seg.id}-k{k - 1}",{{opacity:0.35,duration:0.3}},{t:.3f});\n'
        film.sfx_at(seg, t, "snap")
    seg.cap_y_set = CAP_Y
    film.scene(seg.id, body, s)


def cascade(film, seg):
    """层叠卡两种排法：diagonal 斜向一路落下（默认之一）／zigzag 左右交错、各自倾斜。没指定时按种子二选一。"""
    rng = film.rng(seg, "variant")
    auto = "zigzag" if rng.random() < 0.45 else "diagonal"
    if _variant(film, seg, auto, ("diagonal", "zigzag")) == "diagonal":
        return _cascade_diag(film, seg)
    d = seg.data
    st = film.st
    items = d["items"][:4]
    bg, s = graphic_bg(film, seg)
    body = bg + header(film, seg, d["title"]["zh"], d["title"]["en"])
    rots = [-5, 4, -3, 5]
    for k, it in enumerate(items):
        x = 56 if k % 2 == 0 else W - 56 - 640  # 卡片会斜 3–5°，角会伸出去
        body += card_img(f"{seg.id}-q{k}", x, 400 + k * 220, 640, 210, it["zh"], it.get("en", ""), asset_or_none(film, it.get("img")), num=f"0{k + 1}", fs=48)
    last_left = (len(items) - 1) % 2 == 0
    shp = st.pip["shape"]
    pw = 230 if shp == "rect" else 240
    px = W - 56 - pw if last_left else 56
    py = min(400 + len(items) * 220 + 20, 1430 - (290 if shp == "rect" else pw))  # 四张卡时放在最后一张卡旁边的空位
    ph, ps = put_pip(film, seg, pip_spec(film, seg, (shp, px, py, pw, 290 if shp == "rect" else pw)))
    body += ph
    s += head_in(film, seg) + ps
    for k, t in enumerate(seg.times(items, first=0.8)):
        r = rots[k % 4]
        dx = -160 if k % 2 == 0 else 160
        s += (f'tl.fromTo("#{seg.id}-q{k}",{{opacity:0,x:{dx},rotation:{r * 3}}},{{opacity:1,x:0,rotation:{r},duration:0.55,ease:"back.out(1.4)"}},{t - 0.1:.3f});\n'
              f'tl.fromTo("#{seg.id}-q{k}-g",{{opacity:0}},{{opacity:1,duration:0.25}},{t + 0.2:.3f});\n')
        if k > 0:
            s += f'tl.to("#{seg.id}-q{k - 1}-g",{{opacity:0,duration:0.3}},{t:.3f});\n'
        s += floaty(f"#{seg.id}-q{k}f", seg.d, 7, 3.2, k * 0.6)
        film.sfx_at(seg, t - 0.1, "swoosh")
    seg.cap_y_set = 1330
    film.scene(seg.id, body, s)


GRAPHIC_LAYOUTS = {
    "bigword_band": bigword_band, "band": band_scene, "bars": bars, "pip_cards": pip_cards, "grid4": grid4, "chain": chain,
    "cascade": cascade, "tilt_chart": tilt_chart, "quote": quote, "chapter": chapter, "logo_wall": logo_wall, "doc": doc,
    "compare": compare, "bignum": bignum, "ring_full": ring_full, "product_row": product_row, "ending": ending,
}
