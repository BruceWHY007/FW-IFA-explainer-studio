# -*- coding: utf-8 -*-
"""卡牌、清单两套风格自己的做法：同一类内容换一套搭法，不是同一个版式换颜色。

  卡牌（取自星巴克、英伟达两条参考）：暗底大号品牌纹样平铺；金线黑卡（顶部纹饰、光扫）；渐变色按钮一格格亮起；
      左上分区小标签；圆环进度配大数字；光球关键词；人物胸前倾斜的数字面板；小窗挂在右上角。
  清单（取自免税那条参考）：黑底细点阵；对照表（先打问号、讲到哪格就打勾，底部红条写结论）；左右两色柱对比；
      波普半调大字；光环章节；人物胸前一行对照表；小窗挂在右上角。

炭金、档案、瓷蓝不走这里。这里没覆盖的版式，卡牌、清单也用通用做法（换本风格材质）。
build.py 按 FORMS[风格][版式] 找，找不到就用通用版式。
"""
import math
import re
from .core import W, rich, fit_fs, floaty, icon, sway, tw, stage_y, BLEED_W, BLEED_X
from .frame import band, graphic_bg
from . import layouts_graphic as lg


# ================================================================ 公共
def _chapter_no(film, seg):
    ch = film.plan.get("chapters") or []
    return max(1, sum(1 for c in ch if c[0] <= seg.start + 0.5))


def _num(v):
    m = re.search(r"\d+(?:\.\d+)?", str(v).replace(",", ""))
    return float(m.group()) if m else 0.0


def _pop(sel, t, dy=30, s0=0.84):
    return f'tl.fromTo("{sel}",{{opacity:0,scale:{s0},y:{dy}}},{{opacity:1,scale:1,y:0,duration:0.5,ease:"back.out(1.6)"}},{t:.3f});\n'


def _near_media(film, seg):
    """章节卡背景：本段没有素材时，借前后最近一段的实拍（虚化后做底）。"""
    if seg.bg:
        return seg.bg
    segs = film.segs
    i = segs.index(seg)
    for k in sorted(range(len(segs)), key=lambda j: abs(j - i)):
        d = segs[k].data
        key = d.get("band") or d.get("video") or segs[k].bg
        if key and film.has(key):
            return key
    return None


def _tall_band(film, seg, by, bh):
    """实拍铺满上半屏（参考片的做法），底部渐暗接字幕。"""
    d = seg.data
    body, s = graphic_bg(film, seg, photo=d.get("bg_photo"))
    body += band(film, seg, d["band"], by, h=bh)
    s += f'tl.fromTo("#{seg.id}-bandw",{{opacity:0,scale:1.04}},{{opacity:1,scale:1,duration:0.5,ease:"power3.out"}},0);\n'
    return body, s


# ================================================================ 卡牌
def kp_card(pid, x, y, w, h, inner=""):
    return (f'<div id="{pid}" class="kpcard" style="left:{x:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h:.0f}px">'
            f'<i id="{pid}-sw" class="kpsw"></i>{inner}</div>')


def kp_sweep(pid, t, dur=1.0):
    return f'tl.fromTo("#{pid}-sw",{{xPercent:-150}},{{xPercent:650,duration:{dur},ease:"power2.inOut"}},{t:.3f});\n'


def kp_orn(y):
    return f'<div class="ab kporn" style="left:0;right:0;top:{y:.0f}px"><i></i><s></s><i class="r"></i></div>'


def kp_chip(cid, zh, en="", x=40, y=172, extra=""):
    sm = f"<small>{rich(en)}</small>" if en else ""
    return f'<div id="{cid}" class="kpchip" style="left:{x}px;top:{y}px;{extra}">{rich(zh)}{sm}</div>'


def kp_btn(bid, x, y, w, h, zh, en, k, fs=46):
    """渐变按钮：底下一格暗槽，亮起时彩色按钮盖上来。"""
    sm = f"<small>{rich(en)}</small>" if en else ""
    zfs = min(fs, fit_fs(zh, w - 60, fs))
    return (f'<div id="{bid}-off" class="kpbtn off" style="left:{x:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h:.0f}px"></div>'
            f'<div id="{bid}" class="kpbtn kp{k % 5}" style="left:{x:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h:.0f}px;font-size:{zfs}px;opacity:0">{rich(zh)}{sm}</div>')


def kp_chapter(film, seg):
    d = seg.data
    t = min(seg.at("t", 0.2), max(0.2, seg.d * 0.25))
    body, s = graphic_bg(film, seg)
    names = [c[1] for c in (film.plan.get("chapters") or [])][:6]
    cur = _chapter_no(film, seg) - 1
    zh = d["zh"]
    fs = min(104, fit_fs(zh, 500, 104))
    w, bh, gap = 600, 88, 18
    top0 = 150 + fs + 70
    h = top0 + len(names) * (bh + gap) + 40
    x, y = 240, max(172, min(760 - h / 2, 1290 - h))
    ic = icon((film.motif or ["star"])[0], 58, film.st.c["a"], 1.8)
    inner = (kp_orn(30) + f'<div class="ab" style="left:0;right:0;top:56px;text-align:center">{ic}</div>'
             f'<div id="{seg.id}-tt" class="ab T1" style="left:30px;right:30px;top:132px;text-align:center;font-size:{fs}px;line-height:1;white-space:nowrap">{rich(zh)}</div>'
             f'<div class="ab EN" style="left:30px;right:30px;top:{150 + fs}px;text-align:center">{rich(d.get("en", ""))}</div>')
    for k, nm in enumerate(names):
        inner += kp_btn(f"{seg.id}-b{k}", 50, top0 + k * (bh + gap), w - 100, bh, nm, f"{k + 1:02d}", k, 40)
    body += f'<div id="{seg.id}-cf" class="fl" style="left:{x}px;top:{y:.0f}px;width:{w}px;height:{h:.0f}px">' + kp_card(f"{seg.id}-cd", 0, 0, w, h, inner) + '</div>'
    s += _pop(f"#{seg.id}-cd", max(0, t - 0.15)) + kp_sweep(f"{seg.id}-cd", t + 0.35)
    for k in range(len(names)):
        tk = t + 0.25 + k * 0.08
        s += f'tl.fromTo("#{seg.id}-b{k}-off",{{opacity:0,x:-24}},{{opacity:1,x:0,duration:0.3}},{tk:.3f});\n'
        if k < cur:
            s += f'tl.to("#{seg.id}-b{k}",{{opacity:0.42,duration:0.3}},{tk + 0.1:.3f});\n'
        elif k == cur:
            s += (f'tl.fromTo("#{seg.id}-b{k}",{{opacity:0,scale:0.9}},{{opacity:1,scale:1.04,duration:0.45,ease:"back.out(2)"}},{t + 0.75:.3f});\n')
    s += floaty(f"#{seg.id}-cf", seg.d, 6, 3.8, t + 0.8)
    film.sfx_at(seg, t, "whoosh")
    film.sfx_at(seg, t + 0.75, "snap")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def kp_ring(rid, size, ratio, col):
    r = size / 2 - 18
    c = 2 * math.pi * r
    return (f'<svg class="ab" style="left:0;top:0" width="{size}" height="{size}">'
            f'<circle cx="{size / 2}" cy="{size / 2}" r="{r:.1f}" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="22"/>'
            f'<circle id="{rid}" cx="{size / 2}" cy="{size / 2}" r="{r:.1f}" fill="none" stroke="{col}" stroke-width="22" stroke-linecap="round" '
            f'stroke-dasharray="{c:.1f}" stroke-dashoffset="{c:.1f}" transform="rotate(-90 {size / 2} {size / 2})" style="filter:drop-shadow(0 0 10px {col})"/></svg>'), c * (1 - max(0.02, min(1, ratio)))


def kp_compare(film, seg):
    d = seg.data
    st = film.st
    a = st.c["a"]
    body, s = graphic_bg(film, seg)
    if d.get("title"):
        body += kp_chip(f"{seg.id}-tc", d["title"]["zh"], d["title"].get("en", ""))
        s += f'tl.fromTo("#{seg.id}-tc",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.4,ease:"power3.out"}},0.05);\n'
    va, vb = _num(d["a"]["value"]), _num(d["b"]["value"])
    mx = max(va, vb, 1e-9)
    ta, tb = seg.at("t_a", 0.3), seg.at("t_b", seg.d * 0.45)
    cw, ch, top = 440, 660, 380
    for k, key in enumerate(("a", "b")):
        p = d[key]
        v = va if key == "a" else vb
        x = 60 + k * 520
        ring, off = kp_ring(f"{seg.id}-{key}r", 340, v / mx, a if k == 0 else st.c["m"])
        fsv = min(104, fit_fs(p["value"], 230, 104))
        inner = (kp_orn(28) + f'<div class="ab" style="left:20px;right:20px;top:58px;text-align:center;font:400 40px/1.1 HB,SM;color:#fff;white-space:nowrap">{rich(p["label"])}</div>'
                 f'<div class="ab" style="left:{(cw - 340) / 2:.0f}px;top:150px;width:340px;height:340px">{ring}'
                 f'<div id="{seg.id}-{key}v" class="ab" style="left:0;right:0;top:{170 - fsv / 2:.0f}px;text-align:center;font:400 {fsv}px/1 HB,SM;color:#fff;text-shadow:0 0 24px rgba(255,255,255,.25)">{rich(p["value"])}</div></div>'
                 + kp_orn(ch - 60))
        body += f'<div id="{seg.id}-{key}f" class="fl" style="left:{x}px;top:{top}px;width:{cw}px;height:{ch}px">' + kp_card(f"{seg.id}-{key}", 0, 0, cw, ch, inner) + '</div>'
        t0 = ta if key == "a" else tb
        rot = 12 if k == 0 else -12
        s += (f'tl.set("#{seg.id}-{key}",{{transformPerspective:1500,rotationY:{rot}}},0);\n' + _pop(f"#{seg.id}-{key}", t0)
              + kp_sweep(f"{seg.id}-{key}", t0 + 0.4)
              + f'tl.to("#{seg.id}-{key}r",{{attr:{{"stroke-dashoffset":{off:.1f}}},duration:1.0,ease:"power2.out"}},{t0 + 0.3:.3f});\n'
              + f'tl.fromTo("#{seg.id}-{key}v",{{opacity:0,scale:0.6}},{{opacity:1,scale:1,duration:0.45,ease:"back.out(2)"}},{t0 + 0.35:.3f});\n')
        film.sfx_at(seg, t0, "swoosh")
    s += floaty(f"#{seg.id}-af", seg.d, 7, 3.6, 0) + floaty(f"#{seg.id}-bf", seg.d, 7, 3.6, 1.2)
    if d.get("mult"):
        mfs = min(100, fit_fs(d["mult"]["text"], 900, 100))
        body += f'<div id="{seg.id}-m" class="ab T2" style="left:0;right:0;top:{top + ch + 50}px;text-align:center;font-size:{mfs}px;line-height:1;opacity:0">{rich(d["mult"]["text"])}</div>'
        mt = seg.at_t(d["mult"], tb + 1.0)
        s += st.title_in(f"#{seg.id}-m", mt)
        film.sfx_at(seg, mt, "impact")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def kp_chain(film, seg):
    d = seg.data
    st = film.st
    items = d["items"][:6]
    n = len(items)
    body, s = graphic_bg(film, seg)
    tz, te = d["title"]["zh"], d["title"].get("en", "")
    fs = min(64, fit_fs(tz, 520, 64))
    w = 640
    top0 = 140 + fs + 40
    room = 1270 - 172 - top0 - 40 - (110 if d.get("stamp") else 0)
    bh = min(118, room / n - 20)
    h = top0 + n * (bh + 20) + 30
    x, y = 150, 172
    inner = (kp_orn(30) + f'<div class="ab T1" style="left:30px;right:30px;top:62px;text-align:center;font-size:{fs}px;line-height:1.05;white-space:nowrap">{rich(tz)}</div>'
             f'<div class="ab EN" style="left:30px;right:30px;top:{78 + fs}px;text-align:center">{rich(te)}</div>')
    for k, it in enumerate(items):
        inner += kp_btn(f"{seg.id}-b{k}", 46, top0 + k * (bh + 20), w - 92, bh, it["zh"], it.get("en", ""), k)
    body += f'<div id="{seg.id}-cf" class="fl" style="left:{x}px;top:{y}px;width:{w}px;height:{h:.0f}px">' + kp_card(f"{seg.id}-cd", 0, 0, w, h, inner) + '</div>'
    s += (f'tl.set("#{seg.id}-cd",{{transformPerspective:1600,rotationY:-8}},0);\n' + _pop(f"#{seg.id}-cd", 0.05) + kp_sweep(f"{seg.id}-cd", 0.5))
    for k in range(n):
        s += f'tl.fromTo("#{seg.id}-b{k}-off",{{opacity:0,x:-20}},{{opacity:1,x:0,duration:0.3}},{0.3 + k * 0.07:.3f});\n'
    for k, t in enumerate([max(0.5, t) for t in seg.times(items, first=0.9)]):
        s += f'tl.fromTo("#{seg.id}-b{k}",{{opacity:0,scaleX:0.6}},{{opacity:1,scaleX:1,duration:0.4,ease:"power3.out"}},{t:.3f});\n'
        film.sfx_at(seg, t, "snap")
    s += sway(f"#{seg.id}-cf", seg.d, 2.5, 5.4, 0.8)
    if d.get("stamp"):
        sp = d["stamp"]
        body += kp_chip(f"{seg.id}-st", sp["text"], sp.get("en", ""), x + w - 330, int(y + h - 30),
                        "background:linear-gradient(180deg,#E0475B,#8A1830);transform:rotate(-5deg);font-size:46px;padding:16px 28px 12px")
        stt = seg.at_t(sp, seg.d - 1.5)
        s += st.stamp_in(f"#{seg.id}-st", stt)
        film.sfx_at(seg, stt, "impact")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def kp_quote(film, seg):
    d = seg.data
    st = film.st
    t1 = seg.at("t1", 0.4)
    body, s = graphic_bg(film, seg, photo=d.get("video"))
    D = 700
    ox, oy = (W - D) / 2, 420

    def orb(k, lab, en, big, red, op):
        fsb = min(150, fit_fs(big, D - 160, 150))
        nl = str(big).count("|") + 1
        ty = oy + D / 2 - (nl * fsb * 1.05 + 46) / 2
        bg = (";background:radial-gradient(circle at 50% 42%,rgba(224,71,91,.95),rgba(224,71,91,.55) 45%,rgba(40,8,14,.92) 72%);"
              "box-shadow:0 0 0 3px rgba(224,71,91,.6),0 0 80px rgba(224,71,91,.6),inset 0 0 60px rgba(0,0,0,.5)") if red else ""
        return (kp_chip(f"{seg.id}-c{k}", lab, en, extra=f"opacity:{op}")
                + f'<div id="{seg.id}-o{k}" class="kporb" style="left:{ox:.0f}px;top:{oy}px;width:{D}px;height:{D}px;opacity:0{bg}"></div>'
                f'<div id="{seg.id}-t{k}" class="ab" style="left:{ox:.0f}px;top:{ty:.0f}px;width:{D}px;text-align:center;opacity:0">'
                f'<div class="T1" style="font-size:{fsb}px;line-height:1.05;letter-spacing:4px">{rich(big)}</div>'
                f'<div class="EN" style="margin-top:22px;color:rgba(255,255,255,.7)">{rich(en)}</div></div>')
    warn = d.get("tone") in ("bad", "warn")
    body += orb(1, d.get("lab1", ""), d.get("en1", ""), d["big1"], False, 1)
    s += (f'tl.fromTo("#{seg.id}-c1",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.4}},0.05);\n'
          f'tl.fromTo("#{seg.id}-o1",{{opacity:0,scale:0.5,rotation:-30}},{{opacity:1,scale:1,rotation:0,duration:0.7,ease:"back.out(1.4)"}},{max(0, t1 - 0.2):.3f});\n'
          + st.title_in(f"#{seg.id}-t1", t1))
    film.sfx_at(seg, t1, "impact")
    if d.get("big2"):
        t2 = seg.at("t2", seg.d * 0.55)
        body += orb(2, d.get("lab2", ""), d.get("en2", ""), d["big2"], warn, 0)
        s += (f'tl.to(["#{seg.id}-c1","#{seg.id}-t1"],{{opacity:0,duration:0.25}},{t2 - 0.2:.3f});\n'
              f'tl.to("#{seg.id}-o1",{{opacity:0,scale:1.15,duration:0.35}},{t2 - 0.2:.3f});\n'
              f'tl.fromTo("#{seg.id}-c2",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.4}},{t2:.3f});\n'
              f'tl.fromTo("#{seg.id}-o2",{{opacity:0,scale:0.5,rotation:30}},{{opacity:1,scale:1,rotation:0,duration:0.7,ease:"back.out(1.4)"}},{t2 - 0.05:.3f});\n'
              + st.title_in(f"#{seg.id}-t2", t2 + 0.25))
        film.sfx_at(seg, t2 + 0.25, "impact", 0.2)
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)), 0.2, 9)
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def kp_band(film, seg):
    d = seg.data
    if any(d.get(k) for k in ("band2", "person", "stamp", "dots", "ruler")):
        return lg.band_scene(film, seg)
    by, bh = 172, 860
    body, s = _tall_band(film, seg, by, bh)
    chip = d.get("title") or d.get("corner_tag")
    if chip:
        body += kp_chip(f"{seg.id}-tc", chip["zh"], chip.get("en", ""), 40, by + 26)
        s += f'tl.fromTo("#{seg.id}-tc",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.4,ease:"power3.out"}},0.2);\n'
    if d.get("badge"):
        b = d["badge"]
        bfs = min(56, fit_fs(b["zh"], 460, 56))
        bw, bh_ = tw(b["zh"]) * bfs + 110, bfs + 76
        bx = min(max(60, b.get("x", 560)), W - 60 - bw)
        byy = min(max(by + 150, b.get("y", by + 300)), by + bh - bh_ - 40)
        inner = kp_orn(10) + f'<div class="ab" style="left:0;right:0;top:38px;text-align:center;font:400 {bfs}px/1 HB,SM;color:#fff;white-space:nowrap">{rich(b["zh"])}</div>'
        body += f'<div id="{seg.id}-bdf" class="fl" style="left:{bx:.0f}px;top:{byy:.0f}px;width:{bw:.0f}px;height:{bh_:.0f}px">' + kp_card(f"{seg.id}-bd", 0, 0, bw, bh_, inner) + '</div>'
        bt = seg.at_t(b, 0.5)
        s += _pop(f"#{seg.id}-bd", bt) + kp_sweep(f"{seg.id}-bd", bt + 0.3, 0.8) + floaty(f"#{seg.id}-bdf", seg.d, 6, 3.4, bt + 0.5)
        film.sfx_at(seg, bt, "snap")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = by + bh + 30
    film.scene(seg.id, body + ph, s + ps)


def kp_counter(film, seg):
    """人物段：胸前一块向后倾斜的金线黑面板，数字滚到目标值（参考片的「最新持股比例 100%」）。"""
    from .layouts_host import chin
    d = seg.data
    st = film.st
    c_y, fh = chin(film, seg)
    w_, h_ = 820, 330
    top = min(max(c_y + fh * 0.30, 960), 1290 - h_)
    x = (W - w_) / 2
    to, fr = float(d["to"]), float(d.get("from", 0))
    dec = int(d.get("decimals", 0))
    pre, suf = rich(d.get("prefix", "")), rich(d.get("suffix", ""))
    txt = f"{d.get('prefix', '')}{to:,.{dec}f}{d.get('suffix', '')}"
    fs = min(170, int((w_ - 120) / max(1, tw(txt) * 0.62)))
    inner = (kp_orn(26) + f'<div class="ab" style="left:20px;right:20px;top:50px;text-align:center;font:400 40px/1 HB,SM;color:#fff;white-space:nowrap">{rich(d.get("label", ""))}</div>'
             f'<div class="ab" style="left:0;right:0;top:{h_ - fs - 46:.0f}px;text-align:center;font:400 {fs}px/1 HB,SM;color:{st.c["a"]};text-shadow:0 0 30px rgba({st.c["argb"]},.55)">'
             f'{pre}<span id="{seg.id}-n">{fr:,.{dec}f}</span>{suf}</div>')
    body = f'<div id="{seg.id}-f" class="fl" style="left:{x:.0f}px;top:{top:.0f}px;width:{w_}px;height:{h_}px">' + kp_card(f"{seg.id}-c", 0, 0, w_, h_, inner) + '</div>'
    t = seg.at("t", 0.3)
    dur = float(d.get("dur", 1.1))
    v = seg.id.replace("-", "_")
    s = (f'tl.set("#{seg.id}-c",{{transformPerspective:900,transformOrigin:"50% 100%"}},0);\n'
         f'tl.fromTo("#{seg.id}-c",{{opacity:0,rotationX:75,y:40}},{{opacity:1,rotationX:24,y:0,duration:0.6,ease:"power3.out"}},{t:.3f});\n'
         + kp_sweep(f"{seg.id}-c", t + 0.5)
         + f'const {v}_o={{v:{fr}}};const {v}_e=document.getElementById("{seg.id}-n");\n'
         f'tl.fromTo({v}_o,{{v:{fr}}},{{v:{to},duration:{dur},ease:"power2.out",onUpdate:()=>{{{v}_e.textContent={v}_o.v.toLocaleString("en-US",{{minimumFractionDigits:{dec},maximumFractionDigits:{dec}}});}}}},{t + 0.2:.3f});\n'
         + floaty(f"#{seg.id}-f", seg.d, 6, 3.6, t + 0.6))
    film.sfx_at(seg, t, "whoosh")
    film.zone(seg, "counter", x, top, w_, h_)
    film.scene(seg.id, body, s)


# ================================================================ 清单
def qd_tick(seg_id, k, t):
    return (f'tl.to("#{seg_id}-q{k}",{{opacity:0,scale:0.5,duration:0.2}},{t:.3f});\n'
            f'tl.fromTo("#{seg_id}-ok{k}",{{opacity:0,scale:0.3,rotation:-40}},{{opacity:1,scale:1,rotation:0,duration:0.45,ease:"back.out(2.4)"}},{t + 0.05:.3f});\n')


def qd_table(seg, x, y, w, rows, cols=None, red=None, rh=120, lab_w=None):
    """对照表：rows=[(中文, 英文, [每格内容])]，格子先是问号、讲到时换成打勾；cols=[(中文, 英文)] 是表头。返回 (html, 表高)。"""
    hh = 96 if cols else 0
    lab_w = lab_w or (360 if cols else w - 140)
    ncol = len(cols) if cols else 1
    html = ""
    if cols:
        heads = "".join(f'<div>{rich(c)}<small>{rich(e)}</small></div>' for c, e in cols)
        html += f'<div class="qdhead" style="height:{hh}px;padding-left:{lab_w + 14}px">{heads}</div>'
    cw = (w - 28 - lab_w) / ncol
    for k, (zh, en, vals) in enumerate(rows):
        ry = hh + 14 + k * (rh + 12)
        cells = ""
        for j, v in enumerate(vals[:ncol]):
            cx = lab_w + cw * j + cw / 2
            cells += (f'<div id="{seg.id}-q{k}_{j}" class="qdq" style="left:{cx - 32:.0f}px;top:{rh / 2 - 32:.0f}px">?</div>'
                      f'<div id="{seg.id}-ok{k}_{j}" class="qdok" style="left:{cx - 36:.0f}px;top:{rh / 2 - 36:.0f}px;opacity:0">{rich(v)}</div>')
        lab = ""
        if lab_w > 40:
            zfs = min(44, fit_fs(zh, lab_w - 50, 44))
            lab = f'<div class="qdlab qdr{k % 5}" style="width:{lab_w}px;font-size:{zfs}px">{rich(zh)}<small>{rich(en)}</small></div>'
        html += f'<div id="{seg.id}-row{k}" class="qdrow" style="top:{ry:.0f}px;height:{rh:.0f}px">{lab}{cells}</div>'
    h = hh + 14 + len(rows) * (rh + 12) + 6
    if red:
        html += f'<div id="{seg.id}-red" class="qdred" style="top:{h + 4:.0f}px;opacity:0">{red}</div>'
        h += 90
    return (f'<div id="{seg.id}-tbl" class="qdpanel" style="left:{x:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h + 14:.0f}px">{html}</div>'), h + 14


def qd_chapter(film, seg):
    d = seg.data
    st = film.st
    t = min(seg.at("t", 0.2), max(0.2, seg.d * 0.25))
    media = _near_media(film, seg)
    body, s = graphic_bg(film, seg, photo=media, dim=0.55)
    if media:
        body += '<div class="ab" data-layout-ignore style="left:0;top:0;right:0;bottom:0;-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px)"></div>'
    zh = d["zh"]
    fs = min(140, fit_fs(zh, 560, 140))
    R = 330
    body += (f'<div id="{seg.id}-r1" class="qdring" style="left:{540 - R}px;top:{720 - R}px;width:{2 * R}px;height:{2 * R}px"></div>'
             f'<div id="{seg.id}-r2" class="ab" style="left:{540 - R - 28}px;top:{720 - R - 28}px;width:{2 * R + 56}px;height:{2 * R + 56}px;border-radius:50%;border:2px dashed rgba({st.c["argb"]},.45)"></div>'
             f'<div id="{seg.id}-no" class="ab EN" style="left:0;right:0;top:{720 - fs / 2 - 70:.0f}px;text-align:center;opacity:0">CHAPTER {_chapter_no(film, seg):02d}</div>'
             f'<div id="{seg.id}-tt" class="ab T1" style="left:60px;right:60px;top:{720 - fs / 2:.0f}px;text-align:center;font-size:{fs}px;line-height:1;white-space:nowrap;opacity:0">{rich(zh)}</div>'
             f'<div id="{seg.id}-en" class="ab EN" style="left:0;right:0;top:{720 + fs / 2 + 30:.0f}px;text-align:center;opacity:0">{rich(d.get("en", ""))}</div>')
    s += (f'tl.fromTo("#{seg.id}-r1",{{opacity:0,scale:0.6}},{{opacity:1,scale:1,duration:0.7,ease:"power3.out"}},{max(0, t - 0.2):.3f});\n'
          f'tl.fromTo("#{seg.id}-r2",{{opacity:0,rotation:0,scale:0.8}},{{opacity:1,rotation:90,scale:1,duration:{seg.d:.2f},ease:"none"}},0);\n'
          + st.title_in(f"#{seg.id}-tt", t) + f'tl.fromTo(["#{seg.id}-no","#{seg.id}-en"],{{opacity:0,y:14}},{{opacity:1,y:0,duration:0.4}},{t + 0.35:.3f});\n')
    film.sfx_at(seg, t, "whoosh")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def qd_compare(film, seg):
    """左右两色铺满，各自一摞横线柱从下往上长，柱顶是数字（参考片「官方 ¥3395／免税店 ¥1669」）。"""
    d = seg.data
    st = film.st
    body, s = graphic_bg(film, seg, pattern=False)
    pa, pb = st.c["pa"], st.c["pb"]
    body += (f'<div id="{seg.id}-ha" class="ab" data-safe-bleed style="left:{BLEED_X:.0f}px;top:-40px;width:{540 - BLEED_X:.0f}px;height:1700px;background:{pa}"></div>'
             f'<div id="{seg.id}-hb" class="ab" data-safe-bleed style="left:540px;top:-40px;width:{540 - BLEED_X:.0f}px;height:1700px;background:{pb}"></div>')
    va, vb = _num(d["a"]["value"]), _num(d["b"]["value"])
    mx = max(va, vb, 1e-9)
    ta, tb = seg.at("t_a", 0.3), seg.at("t_b", seg.d * 0.45)
    base, line, gapl, nmax = 1130, 14, 9, 22
    s += (f'tl.fromTo("#{seg.id}-ha",{{xPercent:-100}},{{xPercent:0,duration:0.5,ease:"power3.out"}},0);\n'
          f'tl.fromTo("#{seg.id}-hb",{{xPercent:100}},{{xPercent:0,duration:0.5,ease:"power3.out"}},0);\n')
    for k, key in enumerate(("a", "b")):
        p = d[key]
        v = va if key == "a" else vb
        n = max(1, round(nmax * v / mx))
        cx = 270 + k * 540
        col = "rgba(205,210,255,.9)" if k == 0 else "rgba(150,245,190,.9)"
        lines = "".join(f'<div class="ab" style="left:0;top:{-(i + 1) * (line + gapl)}px;width:300px;height:{line}px;border-radius:3px;background:{col}"></div>' for i in range(n))
        topv = base - n * (line + gapl) - 30
        fsv = min(120, fit_fs(p["value"], 400, 120))
        t0 = ta if key == "a" else tb
        body += (f'<div id="{seg.id}-{key}b" class="ab" style="left:{cx - 150}px;top:{base}px;width:300px;height:1px">{lines}</div>'
                 f'<div id="{seg.id}-{key}v" class="ab" style="left:{cx - 230}px;width:460px;top:{topv - fsv:.0f}px;text-align:center;font:400 {fsv}px/1 HB,SM;color:#fff;opacity:0;'
                 f'text-shadow:0 6px 18px rgba(0,0,0,.4)">{rich(p["value"])}</div>'
                 f'<div class="ab" style="left:{cx - 250}px;width:500px;top:{base + 30}px;text-align:center;font:400 54px/1 HB,SM;color:#fff">{rich(p["label"])}</div>')
        s += (f'tl.from("#{seg.id}-{key}b > div",{{scaleX:0,opacity:0,transformOrigin:"0% 50%",duration:0.25,stagger:0.03}},{t0:.3f});\n'
              f'tl.fromTo("#{seg.id}-{key}v",{{opacity:0,y:30}},{{opacity:1,y:0,duration:0.45,ease:"back.out(1.8)"}},{t0 + 0.03 * n:.3f});\n')
        film.sfx_at(seg, t0, "swoosh")
    if d.get("title"):
        body += (f'<div id="{seg.id}-tc" class="ab" style="left:60px;top:190px"><div class="T1" style="font-size:64px;line-height:1">{rich(d["title"]["zh"])}</div>'
                 f'<div class="EN" style="margin-top:12px">{rich(d["title"].get("en", ""))}</div></div>')
        s += f'tl.fromTo("#{seg.id}-tc",{{opacity:0,y:-20}},{{opacity:1,y:0,duration:0.4}},0.2);\n'
    if d.get("mult"):
        mfs = min(90, fit_fs(d["mult"]["text"], 860, 90))
        body += (f'<div id="{seg.id}-m" class="ab" style="left:60px;right:60px;top:318px;text-align:center;opacity:0">'
                 f'<span style="display:inline-block;padding:16px 34px;border-radius:14px;background:{st.c["m"]};font:400 {mfs}px/1 HB,SM;color:#fff;box-shadow:0 14px 30px rgba(0,0,0,.4)">{rich(d["mult"]["text"])}</span></div>')
        mt = seg.at_t(d["mult"], tb + 1.0)
        s += _pop(f"#{seg.id}-m", mt, 20, 0.6)
        film.sfx_at(seg, mt, "impact")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def qd_chain(film, seg):
    d = seg.data
    st = film.st
    items = d["items"][:6]
    n = len(items)
    body, s = graphic_bg(film, seg)
    tz, te = d["title"]["zh"], d["title"].get("en", "")
    fs = min(76, fit_fs(tz, 700, 76))
    body += (f'<div id="{seg.id}-head" class="ab" style="left:60px;right:260px;top:186px"><div class="T1" style="font-size:{fs}px;line-height:1.05;white-space:nowrap">{rich(tz)}</div>'
             f'<div class="EN" style="margin-top:14px">{rich(te)}</div></div>')
    cols = [((c.get("zh", ""), c.get("en", "")) if isinstance(c, dict) else (c, "")) for c in d.get("cols", [])]
    sp = d.get("stamp")
    top = 186 + fs + 90
    room = 1270 - top - (100 if sp else 0) - (96 if cols else 0) - 30
    rh = min(150, room / n - 12)
    rows = [(it["zh"], it.get("en", ""), it.get("vals") or ["✓"] * max(1, len(cols))) for it in items]
    red = (f'{rich(sp["text"])}<span style="font:500 18px/1 EN,Inter;letter-spacing:3px;opacity:.85">{rich(sp.get("en", ""))}</span>') if sp else None
    html, h = qd_table(seg, 50, top, 980, rows, cols or None, red=red, rh=rh, lab_w=None if cols else 640)
    body += f'<div id="{seg.id}-tf" class="fl" style="left:0;top:0;width:1080px;height:1500px">{html}</div>'
    s += (lg.head_in(film, seg)
          + f'tl.set("#{seg.id}-tbl",{{transformPerspective:1800}},0);\n'
          f'tl.fromTo("#{seg.id}-tbl",{{opacity:0,rotationX:30,rotationY:-6,y:60}},{{opacity:1,rotationX:8,rotationY:-6,y:0,duration:0.6,ease:"power3.out"}},0.1);\n')
    for k in range(n):
        s += f'tl.fromTo("#{seg.id}-row{k}",{{opacity:0,x:-30}},{{opacity:1,x:0,duration:0.3}},{0.35 + k * 0.08:.3f});\n'
    for k, t in enumerate([max(0.6, t) for t in seg.times(items, first=0.9)]):
        for j in range(len(rows[k][2][:max(1, len(cols))])):
            s += qd_tick(seg.id, f"{k}_{j}", t + j * 0.15)
        film.sfx_at(seg, t, "snap")
    if sp:
        stt = seg.at_t(sp, seg.d - 1.5)
        s += f'tl.fromTo("#{seg.id}-red",{{opacity:0,scaleX:0.4}},{{opacity:1,scaleX:1,duration:0.4,ease:"back.out(1.6)"}},{stt:.3f});\n'
        film.sfx_at(seg, stt, "impact")
    s += floaty(f"#{seg.id}-tf", seg.d, 5, 4.0, 0.8)
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def qd_quote(film, seg):
    """波普半调：米色网点纸、红色爆炸星、描黑边的大字（参考片「法拍」）。"""
    d = seg.data
    st = film.st
    t1 = seg.at("t1", 0.4)
    body, s = graphic_bg(film, seg, pattern=False)
    body += (f'<div id="{seg.id}-pop" class="qdpop" data-safe-bleed style="left:{BLEED_X:.0f}px;top:-40px;width:{BLEED_W:.0f}px;height:1700px"></div>'
             f'<div id="{seg.id}-capbar" class="ab" data-safe-bleed style="left:{BLEED_X:.0f}px;top:{stage_y(1330) - 22:.0f}px;width:{BLEED_W:.0f}px;height:118px;background:#1A1414"></div>')
    pts = []
    for i in range(36):
        r = 430 if i % 2 == 0 else 300 + (i * 37 % 60)
        ang = i * math.pi / 18
        pts.append(f"{540 + r * math.cos(ang):.0f},{760 + r * 0.82 * math.sin(ang):.0f}")
    poly = " ".join(pts)
    body += (f'<div id="{seg.id}-burst" class="ab" data-layout-ignore style="left:0;top:0;width:1080px;height:1500px">'
             f'<svg width="1080" height="1500"><polygon points="{poly}" fill="none" stroke="#1A1414" stroke-width="5" transform="translate(10 12)" opacity=".35"/>'
             f'<polygon points="{poly}" fill="{st.c["m"]}" opacity=".92"/></svg></div>')

    def block(k, lab, en, big, op):
        fsb = min(200, fit_fs(big, 900, 200))
        nl = str(big).count("|") + 1
        ty = 760 - nl * fsb * 1.02 / 2
        return (f'<div id="{seg.id}-l{k}" class="ab" style="left:0;right:0;top:232px;text-align:center;opacity:{op}">'
                f'<div style="font:600 30px/1 EN,Inter;letter-spacing:6px;color:{st.c["m"]};text-transform:uppercase">{rich(en)}</div>'
                f'<div style="margin-top:14px;font:400 40px/1 HB,SM;color:#1A1414">{rich(lab)}</div></div>'
                f'<div id="{seg.id}-b{k}" class="ab" style="left:0;right:0;top:{ty:.0f}px;text-align:center;font:400 {fsb}px/1.02 HB,SM;color:#FFF6E8;letter-spacing:6px;opacity:0;'
                f'text-shadow:6px 7px 0 #1A1414,-2px -2px 0 #1A1414,2px -2px 0 #1A1414,-2px 2px 0 #1A1414">{rich(big)}</div>')
    body += block(1, d.get("lab1", ""), d.get("en1", ""), d["big1"], 1)
    s += (f'tl.fromTo("#{seg.id}-pop",{{opacity:0}},{{opacity:1,duration:0.3}},0);\n'
          f'tl.set("#{seg.id}-burst",{{transformOrigin:"540px 760px"}},0);\n'
          f'tl.fromTo("#{seg.id}-burst",{{opacity:0,scale:0.3,rotation:-20}},{{opacity:1,scale:1,rotation:0,duration:0.5,ease:"back.out(2)"}},{max(0, t1 - 0.15):.3f});\n'
          f'tl.fromTo("#{seg.id}-l1",{{opacity:0,y:-16}},{{opacity:1,y:0,duration:0.35}},0.1);\n'
          f'tl.fromTo("#{seg.id}-b1",{{opacity:0,scale:1.8}},{{opacity:1,scale:1,duration:0.35,ease:"power4.in"}},{t1:.3f});\n')
    film.sfx_at(seg, t1, "impact")
    if d.get("big2"):
        t2 = seg.at("t2", seg.d * 0.55)
        body += block(2, d.get("lab2", ""), d.get("en2", ""), d["big2"], 0)
        s += (f'tl.to(["#{seg.id}-l1","#{seg.id}-b1"],{{opacity:0,duration:0.2}},{t2 - 0.15:.3f});\n'
              f'tl.to("#{seg.id}-burst",{{rotation:18,scale:1.08,duration:0.4,ease:"back.out(2)"}},{t2:.3f});\n'
              f'tl.fromTo("#{seg.id}-l2",{{opacity:0,y:-16}},{{opacity:1,y:0,duration:0.35}},{t2:.3f});\n'
              f'tl.fromTo("#{seg.id}-b2",{{opacity:0,scale:1.8}},{{opacity:1,scale:1,duration:0.35,ease:"power4.in"}},{t2 + 0.2:.3f});\n')
        film.sfx_at(seg, t2 + 0.2, "impact", 0.2)
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)), 0.2, 9)
    seg.cap_y_set = 1330
    film.scene(seg.id, body + ph, s + ps)


def qd_band(film, seg):
    d = seg.data
    if any(d.get(k) for k in ("band2", "person", "stamp", "dots", "ruler")):
        return lg.band_scene(film, seg)
    by, bh = 172, 860
    body, s = _tall_band(film, seg, by, bh)
    chip = d.get("title") or d.get("corner_tag")
    if chip:
        body += (f'<div id="{seg.id}-tc" class="ab" style="left:44px;top:{by + 30}px;padding:14px 22px;border-radius:14px;background:rgba(12,12,16,.82);border:2px solid rgba(255,255,255,.28)">'
                 f'<div style="font:400 40px/1 HB,SM;color:#fff;white-space:nowrap">{rich(chip["zh"])}</div>'
                 f'<div class="EN" style="margin-top:8px;font-size:18px">{rich(chip.get("en", ""))}</div></div>')
        s += f'tl.fromTo("#{seg.id}-tc",{{opacity:0,y:-20}},{{opacity:1,y:0,duration:0.4,ease:"power3.out"}},0.2);\n'
    if d.get("badge"):
        b = d["badge"]
        bfs = min(50, fit_fs(b["zh"], 300, 50))
        D = max(260, min(360, tw(b["zh"]) * bfs / 1.6 + 120))
        bx = min(max(60, b.get("x", 560)), W - 60 - D)
        byy = min(max(by + 140, b.get("y", by + 300)), by + bh - D - 30)
        argb = film.st.c["argb"]
        body += (f'<div id="{seg.id}-bdf" class="fl" style="left:{bx:.0f}px;top:{byy:.0f}px;width:{D:.0f}px;height:{D:.0f}px">'
                 f'<div id="{seg.id}-bd" class="qdbub" style="left:0;top:0;width:{D:.0f}px;height:{D:.0f}px;font-size:{bfs}px;'
                 f'background:radial-gradient(circle at 40% 30%,rgba({argb},.75),rgba({argb},.35) 60%,rgba(0,0,0,.25))">{rich(b["zh"].replace(" ", "|"))}</div></div>')
        bt = seg.at_t(b, 0.5)
        s += _pop(f"#{seg.id}-bd", bt, 0, 0.3) + floaty(f"#{seg.id}-bdf", seg.d, 8, 3.6, bt + 0.5)
        film.sfx_at(seg, bt, "snap")
    ph, ps = lg.put_pip(film, seg, lg.pip_spec(film, seg, lg.style_pip(film, seg)))
    seg.cap_y_set = by + bh + 30
    film.scene(seg.id, body + ph, s + ps)


def qd_chest(film, seg):
    """人物段：胸前一行对照表，卡片名做表头，讲到哪格就打勾（参考片人物胸前的「增值税／消费税／关税」表）。"""
    from .layouts_host import chin, head_title
    d = seg.data
    cards = d["cards"][:4]
    c_y, fh = chin(film, seg)
    w = 920
    lab = d.get("label")
    cols = [(c["zh"], c.get("en", "")) for c in cards]
    vals = [c.get("mark", "✓") for c in cards]
    html, h = qd_table(seg, (W - w) / 2, 0, w, [(lab or "", "", vals)], cols, rh=104, lab_w=260 if lab else 1)
    top = min(max(c_y + fh * 0.40, 980), 1290 - h)
    body, s = "", ""
    if d.get("title"):
        b_, s_ = head_title(film, seg, d["title"])
        body += b_
        s += s_
    body += f'<div id="{seg.id}-tf" class="fl" style="left:0;top:{top:.0f}px;width:1080px;height:{h:.0f}px">{html}</div>'
    s += f'tl.fromTo("#{seg.id}-tbl",{{opacity:0,y:40}},{{opacity:1,y:0,duration:0.5,ease:"power3.out"}},0.3);\n'
    for k, t in enumerate(seg.times(cards, first=0.6)):
        s += qd_tick(seg.id, f"0_{k}", t)
        film.sfx_at(seg, t, "snap")
    s += floaty(f"#{seg.id}-tf", seg.d, 5, 3.8, 0.8)
    film.zone(seg, "cards", (W - w) / 2, top, w, h)
    film.scene(seg.id, body, s)


FORMS = {
    "kapai": {"chapter": kp_chapter, "compare": kp_compare, "chain": kp_chain, "quote": kp_quote, "band": kp_band, "counter": kp_counter},
    "qingdan": {"chapter": qd_chapter, "compare": qd_compare, "chain": qd_chain, "quote": qd_quote, "band": qd_band, "chest_cards": qd_chest},
}
