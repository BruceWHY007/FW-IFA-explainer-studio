# -*- coding: utf-8 -*-
"""人物段版式（透明叠加层，盖在人物画面上）。
共同规则：位置全部从 geom.json 的人脸框、头顶和身体边界算出来；每个元素都登记到 film.zone，build 结束时查是否碰到头部范围。
  头顶标题  → 头顶以上的空间（自动关掉这一段的跳切推近，免得推近时头顶顶到标题）
  两侧标签  → 脸两侧、下巴高度，宽度按脸外侧剩余空间算
  身前元素  → 下巴以下
"""
from .core import W, HOST_H, BuildError, chars, chars_in, esc, plain, rich, fit_fs, floaty, icon, tw, SAFE_X, SAFE_TEXT, TITLE_TOP, SAFE_TOP, SAFE_BOTTOM
from .styles import brush_in
from .room import TITLE_MIN_FS, SIDE_MIN

TONES = {
    "info": ("#6E9BFF", "linear-gradient(180deg,rgba(28,42,78,.9),rgba(10,16,34,.95))"),
    "good": ("#43D69A", "linear-gradient(180deg,rgba(16,60,44,.9),rgba(6,22,16,.95))"),
    "bad": ("#FF6A63", "linear-gradient(180deg,rgba(80,22,20,.9),rgba(28,8,8,.95))"),
    "warn": ("#F5B83D", "linear-gradient(180deg,rgba(78,56,14,.9),rgba(30,20,4,.95))"),
}


def tone(film, name):
    if name in TONES:
        return TONES[name]
    a = film.st.c["a"]
    return a, "linear-gradient(180deg,rgba(60,44,30,.9),rgba(20,14,10,.95))"


def head_box(film, seg):
    fx, fy, fw, fh = film.face_box(seg.start, seg.end, zoom=seg.zoom)
    top = film.head_top(seg.start, seg.end, zoom=seg.zoom)
    # 人脸框本身已经接近整个头宽（含两侧头发），横向只再留 5%
    return [fx - fw * 0.05, top, fw * 1.10, fy + fh - top]


def chin(film, seg):
    fx, fy, fw, fh = film.face_box(seg.start, seg.end, zoom=seg.zoom)
    return fy + fh, fh


def span_html(sp):
    if isinstance(sp, str):
        return rich(sp)
    return "".join(f'<span class="{c}" style="display:inline-block">{rich(t)}</span>' for t, c in sp)


def _line_text(ln):
    sp = ln.get("spans") or [[ln.get("text", ""), ln.get("cls", "T1")]]
    return "".join(t for t, _ in sp), sp


# ---------------------------------------------------------------- 头顶标题
def topshade(film, seg, y, fs):
    """头顶标题的压暗：整条从画面顶边往下，标题区够深（亮窗、天空前面字也看得清），往下渐隐到额头。
    深度：顶边 0.86、标题中线 0.74（比最早的 0.92／0.80 略浅），标题下沿约 0.70。
    接缝：从标题中线开始用 smootherstep 曲线淡到 0，两头斜率都是 0，看不出压暗在哪里结束；
    渐隐段尽量拉长（最多 340px，最低到额头、不压眼睛）。最早只有 90px，在头发上方断成一道硬边。
    CSS 渐变在色标之间是直线，排 24 个色标贴近曲线。纯中性黑，不加色调、不磨砂、不垫暗晕（会发灰发脏）。"""
    fx, fy, fw, fh = film.face_box(seg.start, seg.end)
    mid = y + fs * 0.5
    end = max(mid + 120, min(mid + 340, fy + fh * 0.1))
    stops = [(0, 0.86), (mid, 0.74)]
    for k in range(1, 25):
        t = k / 24
        e = t * t * t * (t * (t * 6 - 15) + 10)  # smootherstep
        stops.append((mid + (end - mid) * t, 0.74 * (1 - e)))
    grad = ",".join(f"rgba(6,8,12,{a_:.3f}) {yy:.0f}px" for yy, a_ in stops)
    return (f'<div id="{seg.id}-shade" class="ab" data-safe-bleed data-layout-ignore style="left:0;top:0;width:1080px;height:{end + 2:.0f}px;opacity:0;'
            f'background:linear-gradient(180deg,{grad})"></div>')


def head_title(film, seg, ln, out=None):
    """头顶一行标题＋整条压暗，返回 (body, script)。title_top 和 chest_cards 的头顶标题共用。"""
    seg.zoom = False
    st = film.st
    txt, sp = _line_text(ln)
    head = film.head_top(seg.start, seg.end)
    bottom = head - 22
    avail = bottom - TITLE_TOP
    fs = min(ln.get("size", 112), fit_fs(txt, W - 2 * SAFE_TEXT, 112, 30), int(avail))
    if fs < TITLE_MIN_FS:
        raise BuildError(f"{seg.id} 头顶只有 {avail:.0f}px，标题放不下（字号 {fs}px 太小）。缩短标题，或换成身前卡片 chest_cards")
    y = TITLE_TOP + (avail - fs) / 2
    lid = f"{seg.id}-l0"
    rv = (ln.get("reveal") or seg.data.get("reveal")) == "chars"
    inner = "".join(chars(t_, c_) for t_, c_ in sp) if rv else span_html(sp)
    body = topshade(film, seg, y, fs)
    body += (f'<div id="{lid}" class="ab" style="left:{SAFE_TEXT}px;right:{SAFE_TEXT}px;top:{y:.0f}px;text-align:center;white-space:nowrap;'
             f'font:400 {fs}px/1 SM;letter-spacing:4px;opacity:0">{inner}</div>')
    t_in = seg.at_t(ln, 0.05)
    script = f'tl.fromTo("#{seg.id}-shade",{{opacity:0}},{{opacity:1,duration:0.4,ease:"power2.out"}},{max(0, t_in - 0.2):.3f});\n'
    script += chars_in(f"#{lid}", t_in, len(plain(txt)), ln.get("per") or film.reveal_per(txt, seg, 0.06)) if rv else st.title_in(f"#{lid}", t_in)
    film.sfx_at(seg, t_in, "swoosh")
    film.zone(seg, "title", SAFE_TEXT, y, W - 2 * SAFE_TEXT, fs)
    if out is not None:
        script += st.out(f"#{lid}", seg.L(out))
        script += f'tl.to("#{seg.id}-shade",{{opacity:0,duration:0.4,ease:"power2.in"}},{seg.L(out):.3f});\n'
    return body, script


def title_top(film, seg):
    """头顶只放一行核心信息（话题＋数字，或一组对比）。问句、口播原话交给字幕。
    data.lines: [{spans:[[文字,类名],...] 或 text＋cls, t, reveal, size}]，只认一行；cls 可用 T1/T2/TR/TB。"""
    raw = seg.data.get("lines", [])
    lines = [ln for ln in raw if ln.get("cls") != "sub"]
    dropped = [ln.get("text") or "".join(t for t, _ in ln.get("spans", [])) for ln in raw if ln.get("cls") == "sub"]
    if dropped:
        film.warnings.append(f"{seg.id} 头顶只放一行：副标题「{'／'.join(dropped)}」没有上屏，这句交给字幕；要补充说明改用身前卡片")
    if not lines:
        raise BuildError(f"{seg.id} title_top 没有标题行")
    if len(lines) > 1:
        raise BuildError(f"{seg.id} 头顶只放一行核心信息（现在 {len(lines)} 行）：合成一行，或把后半句交给字幕、身前卡片")
    body, script = head_title(film, seg, lines[0], seg.data.get("out"))
    film.scene(seg.id, body, script)


# ---------------------------------------------------------------- 两侧对立标签
def side_tags(film, seg):
    """data: left/right: [中文, 英文], tones: [左色, 右色]（info/good/bad/warn/accent），tl/tr: 出现时间，push: 两边再推开的时间。"""
    st = film.st
    d = seg.data
    hb = head_box(film, seg)
    c_y, fh = chin(film, seg)
    tag_h = 168
    room_l = hb[0] - SAFE_X - 16
    room_r = W - (hb[0] + hb[2]) - SAFE_X - 16
    tw_ = min(300, room_l, room_r)
    if tw_ < SIDE_MIN:
        raise BuildError(f"{seg.id} 脸两侧只剩 {tw_:.0f}px，放不下对立标签（至少 {SIDE_MIN}px）。换成身前卡片 chest_cards")
    y_l = c_y - tag_h + 10
    y_r = c_y - tag_h - 50
    lc, lbg = tone(film, d.get("tones", ["info", "accent"])[0])
    rc, rbg = tone(film, d.get("tones", ["info", "accent"])[1])

    def chev(col):
        return "".join(f"<polyline points='0,{y} 70,{y + 70} 0,{y + 140}' fill='none' stroke='{col}' stroke-width='7' "
                       f"opacity='{0.15 + 0.7 * (1 - abs(k - 5) / 6):.2f}'/>" for k, y in enumerate(range(-140, 1700, 130)))
    fs = min(48, fit_fs(max(d["left"][0], d["right"][0], key=tw), tw_ - 44, 48, 30))
    card = lambda side, x_css, y, col, bg, zh, en: (
        f'<div id="{seg.id}-{side}" class="card" style="{x_css};top:{y:.0f}px;width:{tw_:.0f}px;height:{tag_h}px;padding:30px 22px;'
        f'border-color:{col};box-shadow:0 0 40px {col}55;background:{bg};border-radius:18px">'
        f'<div class="t" style="font-size:{fs}px;color:#fff;font-family:SM">{rich(zh)}</div>'
        f'<div class="e" style="color:{col}">{rich(en)}</div></div>')
    body = (f'<div id="{seg.id}-cl" class="ab" data-layout-ignore style="left:0;top:0;width:110px;height:{HOST_H}px;overflow:hidden"><svg id="{seg.id}-cls" width="110" height="1840" style="position:absolute;left:0;top:0">{chev(lc)}</svg></div>'
            f'<div id="{seg.id}-cr" class="ab" data-layout-ignore style="right:0;top:0;width:110px;height:{HOST_H}px;overflow:hidden"><svg id="{seg.id}-crs" width="110" height="1840" style="position:absolute;left:0;top:0;transform:scaleX(-1)">{chev(rc)}</svg></div>'
            + card("l", f"left:{SAFE_X}px", y_l, lc, lbg, *d["left"]) + card("r", f"right:{SAFE_X}px", y_r, rc, rbg, *d["right"]))
    tl_, tr_ = seg.at("tl", 0.1), seg.at("tr", 0.8)
    s = (f'tl.fromTo("#{seg.id}-cls",{{y:-130}},{{y:0,duration:{seg.d:.2f},ease:"none"}},0);\n'
         f'tl.fromTo("#{seg.id}-crs",{{y:0}},{{y:-130,duration:{seg.d:.2f},ease:"none"}},0);\n'
         f'tl.fromTo("#{seg.id}-cl",{{opacity:0,x:-40}},{{opacity:1,x:0,duration:0.4,ease:"power3.out"}},{tl_});\n'
         f'tl.fromTo("#{seg.id}-l",{{opacity:0,x:-80}},{{opacity:1,x:0,duration:0.4,ease:"back.out(1.6)"}},{tl_});\n'
         f'tl.fromTo("#{seg.id}-cr",{{opacity:0,x:40}},{{opacity:1,x:0,duration:0.4,ease:"power3.out"}},{tr_});\n'
         f'tl.fromTo("#{seg.id}-r",{{opacity:0,x:80}},{{opacity:1,x:0,duration:0.4,ease:"back.out(1.6)"}},{tr_});\n')
    s += floaty(f"#{seg.id}-l", seg.d, 9, 3.4, tl_ + 0.4) + floaty(f"#{seg.id}-r", seg.d, 9, 3.4, tr_ + 0.4)
    if d.get("push") is not None:
        s += (f'tl.to("#{seg.id}-cl",{{x:-22,duration:0.6,ease:"power2.out"}},{seg.L(d["push"])});\n'
              f'tl.to("#{seg.id}-cr",{{x:22,duration:0.6,ease:"power2.out"}},{seg.L(d["push"])});\n')
    film.zone(seg, "left", SAFE_X, y_l - 10, tw_, tag_h + 20)
    film.zone(seg, "right", W - SAFE_X - tw_, y_r - 10, tw_, tag_h + 20)
    film.sfx_at(seg, tl_, "swoosh"); film.sfx_at(seg, tr_, "swoosh")
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 身前一排卡片（可带头顶标题）
def chest_cards(film, seg):
    """data: title: {text 或 spans, cls}（可选，放头顶）, cards: [{zh, tag, en, t}]（2–3 张）, all_on: 全部点亮的时间。"""
    st = film.st
    d = seg.data
    cards = d["cards"]
    n = len(cards)
    c_y, fh = chin(film, seg)
    top = max(c_y + fh * 0.42, 1000)
    ch = 180
    if top + ch > 1290:
        top = 1290 - ch
    gap = 12
    cw = (W - 2 * SAFE_X - gap * (n - 1)) / n
    body, s = "", ""
    if d.get("title"):
        b_, s_ = head_title(film, seg, d["title"])
        body += b_
        s += s_
    times = seg.times(cards, first=0.6)
    fs = min(52, fit_fs(max((c["zh"] for c in cards), key=tw), cw - 40, 52, 30))
    for k, c in enumerate(cards):
        x = SAFE_X + k * (cw + gap)
        tag = f'<div id="{seg.id}-t{k}" class="tag" style="left:22px;top:-30px;opacity:0">{rich(c["tag"])}</div>' if c.get("tag") else ""
        body += (f'<div id="{seg.id}-c{k}f" class="fl" style="left:{x:.0f}px;top:{top:.0f}px;width:{cw:.0f}px;height:{ch}px">'
                 f'<div id="{seg.id}-c{k}" class="card" style="left:0;top:0;width:{cw:.0f}px;height:{ch}px;padding:{(ch - fs - 30) / 2:.0f}px 0 0;text-align:center;opacity:0">'
                 f'<div class="dash"></div><div id="{seg.id}-c{k}-g" class="glow"></div><div class="t" style="font-size:{fs}px">{rich(c["zh"])}</div>'
                 f'<div class="e">{rich(c.get("en", f"{k + 1:02d}"))}</div></div>{tag}</div>')
    s += f'tl.fromTo([{",".join(chr(34) + "#" + seg.id + "-c" + str(k) + chr(34) for k in range(n))}],{{opacity:0,y:40}},{{opacity:0.45,y:0,duration:0.4,stagger:0.08,ease:"power3.out"}},0.4);\n'
    for k, t in enumerate(times):
        s += (f'tl.to("#{seg.id}-c{k}",{{opacity:1,duration:0.25}},{t:.3f});\n'
              f'tl.fromTo("#{seg.id}-c{k}-g",{{opacity:0}},{{opacity:1,duration:0.25}},{t:.3f});\n')
        if cards[k].get("tag"):
            s += f'tl.fromTo("#{seg.id}-t{k}",{{opacity:0,y:10}},{{opacity:1,y:0,duration:0.3,ease:"back.out(2)"}},{t + 0.05:.3f});\n'
        if k > 0:
            s += f'tl.to("#{seg.id}-c{k - 1}-g",{{opacity:0.3,duration:0.25}},{t:.3f});\n'
        film.sfx_at(seg, t, "snap")
        s += floaty(f"#{seg.id}-c{k}f", seg.d, 7, 3.2, k * 0.7)
    if d.get("all_on"):
        s += f'tl.to([{",".join(chr(34) + "#" + seg.id + "-c" + str(k) + "-g" + chr(34) for k in range(n))}],{{opacity:1,duration:0.3}},{seg.L(d["all_on"])});\n'
    film.zone(seg, "cards", SAFE_X, top - 34, W - 2 * SAFE_X, ch + 34)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 身前名牌（人物介绍）
def namecard(film, seg):
    """data: name, role, en（可选）, photo（素材键，可选）, t, tag（可选）。"""
    d = seg.data
    c_y, fh = chin(film, seg)
    w_, h_ = 780, 200
    top = min(max(c_y + fh * 0.38, 980), 1300 - h_)
    x = (W - w_) / 2
    photo = (f'<div class="ab" style="right:0;top:0;width:{w_ * 0.42:.0f}px;height:100%;background:url(\'{film.a(d["photo"])}\') center/cover;'
             f'-webkit-mask:linear-gradient(90deg,transparent,#000 45%)"></div>') if d.get("photo") else ""
    tag = f'<div id="{seg.id}-tg" class="tag" style="left:26px;top:-28px;opacity:0">{rich(d["tag"])}</div>' if d.get("tag") else ""
    fs = min(64, fit_fs(d["name"], w_ * (0.5 if photo else 0.8), 64))
    body = (f'<div id="{seg.id}-f" class="fl" style="left:{x:.0f}px;top:{top:.0f}px;width:{w_}px;height:{h_}px">'
            f'<div id="{seg.id}-c" class="card" style="left:0;top:0;width:{w_}px;height:{h_}px;opacity:0">{photo}<div class="dash"></div>'
            f'<div class="ab" style="left:44px;top:42px"><div class="t" style="font-size:{fs}px;letter-spacing:4px">{rich(d["name"])}</div>'
            f'<div class="ab" style="left:2px;top:{fs + 18}px;white-space:nowrap;font:400 34px/1 SM;opacity:.82">{rich(d.get("role", ""))}</div></div>'
            f'</div>{tag}</div>')
    t = seg.at("t", 0.3)
    s = film.st.card_in(f"#{seg.id}-c", t, 0, film.rng(seg), "up")
    if d.get("tag"):
        s += f'tl.fromTo("#{seg.id}-tg",{{opacity:0,y:10}},{{opacity:1,y:0,duration:0.3,ease:"back.out(2)"}},{t + 0.2:.3f});\n'
    s += floaty(f"#{seg.id}-f", seg.d, 7, 3.4, t + 0.5)
    film.sfx_at(seg, t, "swoosh")
    film.zone(seg, "namecard", x, top - 30, w_, h_ + 30)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 身前滚动数字
def counter(film, seg):
    """data: label, from, to, prefix, suffix, plus(true 时末尾加 ⁺), t, dur, note。数字在面板里滚到目标值。"""
    d = seg.data
    c_y, fh = chin(film, seg)
    w_, h_ = 960, 240
    top = min(max(c_y + fh * 0.30, 960), 1290 - h_)
    x = (W - w_) / 2
    to = float(d["to"]); fr = float(d.get("from", 0))
    dec = int(d.get("decimals", 0))
    fmt = lambda v: f"{v:,.{dec}f}"
    pre, suf = rich(d.get("prefix", "")), rich(d.get("suffix", ""))
    fs = min(150, int((w_ - 80) / (len(pre + fmt(to) + suf) * 0.52)))
    plus = '<span style="font-size:.5em;vertical-align:top;margin-left:4px">+</span>' if d.get("plus") else ""
    body = (f'<div id="{seg.id}-f" class="fl" style="left:{x:.0f}px;top:{top:.0f}px;width:{w_}px;height:{h_}px">'
            f'<div id="{seg.id}-c" class="card" style="left:0;top:0;width:{w_}px;height:{h_}px;opacity:0;text-align:center"><div class="dash"></div>'
            f'<div class="numt" style="position:absolute;left:0;right:0;top:{(h_ - fs) / 2 + 12:.0f}px;font-size:{fs}px">{pre}<span id="{seg.id}-n">{fmt(fr)}</span>{suf}{plus}</div></div>'
            f'<div id="{seg.id}-lb" class="tag" style="left:50%;top:-26px;transform:translateX(-50%);opacity:0">{rich(d.get("label", ""))}</div></div>')
    t = seg.at("t", 0.3)
    dur = float(d.get("dur", 1.1))
    s = film.st.card_in(f"#{seg.id}-c", t, 0, film.rng(seg), "up")
    s += f'tl.fromTo("#{seg.id}-lb",{{opacity:0,y:10}},{{opacity:1,y:0,duration:0.3}},{t + 0.15:.3f});\n'
    s += (f'const {seg.id.replace("-", "_")}_o={{v:{fr}}};const {seg.id.replace("-", "_")}_e=document.getElementById("{seg.id}-n");\n'
          f'tl.fromTo({seg.id.replace("-", "_")}_o,{{v:{fr}}},{{v:{to},duration:{dur},ease:"power2.out",onUpdate:()=>{{{seg.id.replace("-", "_")}_e.textContent='
          f'{seg.id.replace("-", "_")}_o.v.toLocaleString("en-US",{{minimumFractionDigits:{dec},maximumFractionDigits:{dec}}});}}}},{t + 0.2:.3f});\n')
    s += floaty(f"#{seg.id}-f", seg.d, 6, 3.6, t + 0.6)
    film.sfx_at(seg, t, "whoosh")
    film.zone(seg, "counter", x, top - 30, w_, h_ + 30)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 身前关键词贴纸（可依次替换）
def sticker(film, seg):
    """data: words: [{zh, en, t}]，后一个替换前一个。"""
    st = film.st
    words = seg.data["words"]
    c_y, fh = chin(film, seg)
    top = min(max(c_y + fh * 0.30, 960), 1180)
    a = st.c.get("a")
    body, s = "", ""
    times = seg.times(words, first=0.2)
    for k, w_ in enumerate(words):
        fs = min(120, fit_fs(w_["zh"], 760, 120))
        body += (f'<div id="{seg.id}-w{k}" class="ab" data-layout-allow-overlap style="left:0;right:0;top:{top:.0f}px;text-align:center;opacity:0">'
                 f'<div class="EN" style="margin-bottom:6px;color:#fff;text-shadow:0 2px 6px rgba(0,0,0,.6)">{rich(w_.get("en", ""))}</div>'
                 f'<div style="display:inline-block;font:400 {fs}px/1 SM;letter-spacing:6px;color:{a};-webkit-text-stroke:3px #fff;paint-order:stroke fill;'
                 f'filter:drop-shadow(0 6px 14px rgba(0,0,0,.5))">{rich(w_["zh"])}</div></div>')
        t = times[k]
        s += f'tl.fromTo("#{seg.id}-w{k}",{{opacity:0,scale:1.5,rotation:-6}},{{opacity:1,scale:1,rotation:0,duration:0.35,ease:"back.out(2.2)"}},{t:.3f});\n'
        if k + 1 < len(words):
            s += f'tl.to("#{seg.id}-w{k}",{{opacity:0,scale:0.8,duration:0.15}},{times[k + 1] - 0.08:.3f});\n'
        film.sfx_at(seg, t, "snap")
    s += floaty(f"#{seg.id}-w0", seg.d, 5, 3.0, 0.5)
    film.zone(seg, "sticker", 120, top, W - 240, 170)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 侧边量表
def gauge(film, seg):
    """data: title, sub, top_label, bottom_label, marks: [{label, pos(0底–1顶)}], fill(0–1), t。放在离脸更远的一侧。"""
    d = seg.data
    hb = head_box(film, seg)
    face_cx = hb[0] + hb[2] / 2
    side = d.get("side") or ("left" if face_cx > W / 2 else "right")
    w_ = 230
    room = hb[0] - SAFE_X if side == "left" else W - (hb[0] + hb[2]) - SAFE_X
    if room < w_ + 30:
        raise BuildError(f"{seg.id} 侧边只剩 {room:.0f}px，放不下量表")
    x = SAFE_X if side == "left" else W - SAFE_X - w_  # 左右、顶部都留在平台安全区里
    y0, hh = SAFE_TOP + 10, 760
    marks = "".join(
        f'<div class="ab" style="left:0;right:0;top:{hh * (1 - m["pos"]):.0f}px;border-top:3px dashed rgba(255,255,255,.9)">'
        f'<span class="tag" style="left:6px;top:-50px;font-size:30px">{rich(m["label"])}</span></div>' for m in d.get("marks", []))
    body = (f'<div id="{seg.id}-f" class="fl" style="left:{x}px;top:{y0}px;width:{w_}px;height:{hh + 220}px">'
            f'<div id="{seg.id}-g" class="ab" style="left:0;top:0;width:{w_}px;height:{hh + 220}px;opacity:0">'
            f'<div class="card" style="left:0;top:0;width:{w_}px;height:104px;padding:18px 0;text-align:center"><div class="t" style="font-size:40px">{rich(d.get("title", ""))}</div>'
            f'<div class="e" style="margin-top:8px">{rich(d.get("sub", ""))}</div></div>'
            f'<div class="ab" style="left:14px;top:110px;width:{w_ - 28}px;height:{hh}px;border-radius:8px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.25)">'
            f'<div id="{seg.id}-fill" class="ab" style="left:0;right:0;bottom:0;height:100%;transform-origin:50% 100%;'
            f'background:linear-gradient(180deg,rgba(214,80,90,.85),rgba(70,160,120,.75) 60%,rgba(60,110,200,.75))"></div>{marks}</div>'
            f'<div class="card" style="left:0;top:{hh + 124}px;width:{w_}px;height:96px;padding:22px 0;text-align:center"><div class="t" style="font-size:40px">{rich(d.get("bottom_label", ""))}</div></div>'
            f'</div></div>')
    t = seg.at("t", 0.3)
    s = (f'tl.fromTo("#{seg.id}-g",{{opacity:0,x:{-60 if side == "left" else 60}}},{{opacity:1,x:0,duration:0.45,ease:"power3.out"}},{t:.3f});\n'
         f'tl.fromTo("#{seg.id}-fill",{{scaleY:0}},{{scaleY:{d.get("fill", 1)},duration:1.2,ease:"power2.out"}},{t + 0.3:.3f});\n')
    s += floaty(f"#{seg.id}-f", seg.d, 6, 3.8, t + 0.6)
    film.sfx_at(seg, t, "swoosh")
    film.zone(seg, "gauge", x, y0, w_, hh + 220)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 下方铭牌（关键词＋配图）
def plaque(film, seg):
    """data: zh, en, img（素材键，可选）, t。放在下方、底座上沿，字幕挪到铭牌上面。"""
    d = seg.data
    w_, h_ = 620, 220
    top = SAFE_BOTTOM - h_ - 24  # 底边留在平台安全区里（1483 以下是账号名和标题文案），算上缓动 ±6 和卡片阴影也不越线
    x = (W - w_) / 2
    img = (f'<div class="ab" style="left:0;top:0;width:{w_ * 0.42:.0f}px;height:100%;background:url(\'{film.a(d["img"])}\') center/cover;'
           f'-webkit-mask:linear-gradient(270deg,transparent,#000 50%)"></div>') if d.get("img") else ""
    tx = w_ * 0.40 if img else 0
    fs = min(96, fit_fs(d["zh"], w_ - tx - 60, 96))
    body = (f'<div id="{seg.id}-f" class="fl" style="left:{x:.0f}px;top:{top}px;width:{w_}px;height:{h_}px">'
            f'<div id="{seg.id}-c" class="card" style="left:0;top:0;width:{w_}px;height:{h_}px;opacity:0">{img}<div class="dash"></div>'
            f'<div id="{seg.id}-g" class="glow"></div>'
            f'<div class="ab" style="left:{tx:.0f}px;right:0;top:{(h_ - fs) / 2 - 16:.0f}px;text-align:center"><div class="T1" style="font-size:{fs}px;letter-spacing:8px">{rich(d["zh"])}</div>'
            f'<div class="EN" style="margin-top:12px">{rich(d.get("en", ""))}</div></div></div></div>')
    t = seg.at("t", 0.3)
    s = film.st.card_in(f"#{seg.id}-c", t, 0, film.rng(seg), "up") + f'tl.fromTo("#{seg.id}-g",{{opacity:0}},{{opacity:1,duration:0.3}},{t + 0.4:.3f});\n'
    s += floaty(f"#{seg.id}-f", seg.d, 6, 3.6, t + 0.6)
    seg.cap_y_set = top - 96
    film.sfx_at(seg, t, "impact", 0.2)
    film.zone(seg, "plaque", x, top, w_, h_)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 身前环形关系图
def ring(film, seg):
    """data: center: [中文, 英文], tiles: [[中文, 英文]×4], t, tiles_t: [t…]。环放在胸前，字幕挪到头顶。"""
    d = seg.data
    c_y, fh = chin(film, seg)
    R = 230
    cy = min(max(c_y + 320, 1150), HOST_H - R - 70)
    cx = W / 2
    tiles = d["tiles"][:4]
    pos = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    tl_html = ""
    for k, (zh, en) in enumerate(tiles):
        px, py = cx + pos[k][0] * R * 0.92 - 85, cy + pos[k][1] * R * 0.62 - 50
        tl_html += (f'<div id="{seg.id}-t{k}" class="card" style="left:{px:.0f}px;top:{py:.0f}px;width:170px;height:100px;padding:18px 0;text-align:center;opacity:0">'
                    f'<div class="t" style="font-size:40px">{rich(zh)}</div><div class="e" style="margin-top:6px;font-size:13px">{rich(en)}</div></div>')
    body = (f'<div id="{seg.id}-r" class="ab" style="left:{cx - R:.0f}px;top:{cy - R:.0f}px;width:{R * 2}px;height:{R * 2}px;opacity:0">'
            f'<div class="hud ab" style="inset:0;border-radius:50%;border:3px solid {film.st.c["a"]};box-shadow:0 0 30px {film.st.c["a"]}99,inset 0 0 30px {film.st.c["a"]}55"></div>'
            f'<svg id="{seg.id}-arc" class="ab" style="left:-24px;top:-24px" width="{R * 2 + 48}" height="{R * 2 + 48}"><circle cx="{R + 24}" cy="{R + 24}" r="{R + 14}" fill="none" stroke="{film.st.c["a"]}" stroke-width="4" stroke-dasharray="120 60 30 60" opacity=".75"/></svg>'
            f'<div class="card" style="left:{R - 130}px;top:{R - 130}px;width:260px;height:260px;border-radius:50%;text-align:center;padding-top:84px">'
            f'<div class="t" style="font-size:52px">{rich(d["center"][0])}</div><div class="e">{rich(d["center"][1])}</div></div></div>' + tl_html)
    t = seg.at("t", 0.3)
    s = (f'tl.fromTo("#{seg.id}-r",{{opacity:0,scale:0.6}},{{opacity:1,scale:1,duration:0.6,ease:"back.out(1.5)"}},{t:.3f});\n'
         f'tl.fromTo("#{seg.id}-arc",{{rotation:0}},{{rotation:200,duration:{seg.d:.2f},ease:"none"}},0);\n')
    tt = d.get("tiles_t") or [None] * len(tiles)
    for k in range(len(tiles)):
        tk = seg.L(tt[k]) if tt[k] is not None else t + 0.4 + k * 0.25
        s += film.st.card_in(f"#{seg.id}-t{k}", tk, k, film.rng(seg, k), "up")
        film.sfx_at(seg, tk, "snap")
    s += floaty(f"#{seg.id}-r", seg.d, 6, 4.0, t + 0.7)
    seg.cap_y_set = 150
    film.zone(seg, "ring", cx - R - 110, cy - R - 30, R * 2 + 220, R * 2 + 60)
    film.scene(seg.id, body, s)


# ---------------------------------------------------------------- 不加包装
def plain_layout(film, seg):
    """只留人物和字幕：让人物说话、给观众喘口气的段落。全片人物段里留几段 plain，节奏才有松有紧。"""
    film.scene(seg.id, "", "")


HOST_LAYOUTS = {
    "plain": plain_layout,
    "title_top": title_top, "side_tags": side_tags, "chest_cards": chest_cards, "namecard": namecard,
    "counter": counter, "sticker": sticker, "gauge": gauge, "plaque": plaque, "ring": ring,
}
