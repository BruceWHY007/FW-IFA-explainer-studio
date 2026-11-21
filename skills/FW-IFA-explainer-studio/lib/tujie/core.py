# -*- coding: utf-8 -*-
"""公共骨架：画布分区、工程上下文、场景写出、人脸安全取景、缓动与入场工具。

画布 1080×1920：
  0–1576    人物画面区（图解场景也只在这一区排版）
  1576–1920 底座（章节进度条＋补充信息卡＋署名牌），全片常驻，五套风格都有
"""
import hashlib, json, math, os, random, re, statistics

W, H = 1080, 1920
HOST_H = 1576
CAP_Y = 1300          # 人物段字幕默认位置（字幕上沿）
ZOOM = 1.08           # 跳切推近倍率
MOTION = {"amp": 1.0}  # 当前段的缓动幅度倍数（段落层 energy 决定）
TONES = {"good": "#43D69A", "bad": "#FF6A63", "warn": "#F5B83D", "info": "#6E9BFF"}
SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class BuildError(Exception):
    pass


class Seg:
    """一段：人物段（kind=host，透明叠加层）或图解段（kind=graphic，盖住人物，小窗里放人物）。"""

    def __init__(self, d, film):
        self.raw = d
        self.id = d["id"]
        self.kind = d.get("kind", "graphic")
        self.layout = d["layout"]
        self.start = float(d["start"])
        self.end = float(d["end"])
        self.data = d.get("data", {})
        self.bg = d.get("bg")
        self.cap_y = d.get("cap_y")
        self.zoom = d.get("zoom", True)
        self.film = film
        self.sfx_on = d.get("sfx", True)

    @property
    def d(self):
        return self.end - self.start

    def L(self, t):
        """全片时间 → 本段局部时间。"""
        return round(float(t) - self.start, 3)

    def times(self, items, key="t", first=0.4, last_pad=0.6, gap=0.6):
        """列表项的出现时间（局部秒）。没写 t 的按段长均分。"""
        n = len(items)
        out = []
        for k, it in enumerate(items):
            if isinstance(it, dict) and isinstance(it.get(key), (int, float)):
                out.append(self.L(it[key]))
            else:
                span = max(0.1, self.d - first - last_pad)
                out.append(round(first + span * k / max(1, n), 3))
        for k in range(1, n):  # 说得快时顺延：相邻两项至少隔 0.6 秒，免得前一张还没进场就被压暗
            out[k] = round(min(max(out[k], out[k - 1] + gap), self.d - 0.3), 3)
        return out

    def at(self, key, default):
        """data 里的时间点（全片时间）→ 局部秒；没有就用默认局部秒。"""
        v = self.data.get(key)
        return self.L(v) if v is not None else default

    def at_t(self, obj, default):
        """某个子项里写的 t（全片时间）→ 局部秒。"""
        v = obj.get("t") if isinstance(obj, dict) else None
        return self.L(v) if v is not None else default


class Film:
    def __init__(self, plan, assets, geom, out):
        from . import styles
        self.plan = plan
        self.A = assets
        self.geom = geom
        self.out = out
        self.title = plan["title"]
        self.seed = int(plan.get("seed") or int(hashlib.md5(self.title.encode()).hexdigest()[:8], 16))
        self.st = styles.get(plan["style"], plan.get("accent"))
        self.dur = float(plan["duration"])
        self.aroll_dur = float(plan.get("aroll_duration", self.dur))
        self.segs = [Seg(d, self) for d in plan["segments"]]
        self.sfx = []
        self.zones = []
        self.cap_slots = []
        self.warnings = []
        self.motif = plan.get("motif", [])
        self.cur = None
        os.makedirs(os.path.join(out, "compositions"), exist_ok=True)

    # ------------------------------------------------------------ 说话时间（让动画对齐本人说话）
    def _speech_index(self):
        if not hasattr(self, "_ct"):
            ct = self.plan.get("_chartimes") or []
            self._ct = ("".join(c[0] for c in ct).lower(), ct)
        return self._ct

    def speech_find(self, word, t0=0.0, t1=None):
        """在 t0–t1 之间找这个词第一次被说出来的起止时间（全片秒）。先查字级时间，再按字幕位置估算。找不到返回 None。"""
        import re as _re
        t1 = self.dur if t1 is None else t1
        w = _re.sub(r"[\s，。、！？,.!?：:“”\"'*|]", "", str(word)).lower()
        if not w:
            return None
        text, ct = self._speech_index()
        i = text.find(w)
        while i >= 0:
            s, e = ct[i][1], ct[i + len(w) - 1][2]
            if t0 - 0.3 <= s <= t1:
                return s, e
            i = text.find(w, i + 1)
        for c in self.plan.get("_captions", []):
            tx = _re.sub(r"[\s，。、！？,.!?：:“”\"']", "", c["text"]).lower()
            j = tx.find(w)
            if j >= 0 and len(tx):
                s = c["start"] + (c["end"] - c["start"]) * j / len(tx)
                e = c["start"] + (c["end"] - c["start"]) * (j + len(w)) / len(tx)
                if t0 - 0.3 <= s <= t1:
                    return round(s, 3), round(e, 3)
        return None

    def reveal_per(self, text, seg, default=0.07):
        """逐字展开的间隔：这句话在原声里说了多久，就用多久展开（每字 0.03–0.12 秒）。找不到就用默认。"""
        n = len(plain(text).replace("|", "").replace(" ", ""))
        hit = self.speech_find(plain(text), seg.start, seg.end) if n else None
        if hit and n:
            return max(0.03, min(0.12, (hit[1] - hit[0]) / n))
        return default

    def prepare(self, seg):
        """进入一段之前调用：按这一段的段落层参数（energy／enter／card_enter／tone）设置动作和色调。seg=None 时恢复默认。"""
        self.cur = seg
        data = seg.data if seg else {}
        self.st.set_mode(data)
        MOTION["amp"] = {"calm": 0.7, "punch": 1.15}.get(data.get("energy"), 1.0)

    # ------------------------------------------------------------ 素材
    def a(self, key):
        if key in self.A:
            return self.A[key]
        raise BuildError(f"assets.json 里没有素材「{key}」")

    def has(self, key):
        return key in self.A

    def rng(self, seg, salt=""):
        h = int(hashlib.md5(f"{self.seed}:{seg.id}:{salt}".encode()).hexdigest()[:8], 16)
        return random.Random(h)

    # ------------------------------------------------------------ 写场景
    def base_css(self):
        f = []
        for fam, key in (("SM", "font_sm"), ("EN", "font_en"), ("NUM", "font_num"), ("SR", "font_sr"), ("BR", "font_br")):
            if self.has(key):
                f.append(f"@font-face{{font-family:{fam};src:url('{self.a(key)}')}}")
        return "\n".join(f) + """
*{box-sizing:border-box}
#root{position:absolute;inset:0;overflow:hidden}
.ab,.fl{position:absolute}
.pipc{position:absolute;overflow:hidden;background:#1a1a1a}
.pipc video{position:absolute;max-width:none}
.vig{position:absolute;inset:0;background:radial-gradient(120% 80% at 50% 40%,rgba(0,0,0,0) 30%,rgba(0,0,0,.78) 100%)}
.grain{position:absolute;inset:0;opacity:.08;background-image:radial-gradient(rgba(255,255,255,.7) .6px,transparent .8px);background-size:5px 5px}
.note{position:absolute;font:600 18px/1 EN,Inter,sans-serif;letter-spacing:4px;color:rgba(255,255,255,.42)}
"""

    def tone_css(self):
        """段落层 tone：这一段的点亮框、小标签、重点词、英文副题换成情绪色（好消息绿、风险红、提醒黄、说明蓝）。"""
        tone = self.cur.data.get("tone") if self.cur else None
        c = TONES.get(tone)
        if not c:
            return ""
        return (f".glow{{border-color:{c} !important;box-shadow:0 0 0 1px {c}40,0 0 40px {c}77 !important}}"
                f".tag{{background:linear-gradient(180deg,{c},{c}BB) !important;color:#fff !important}}"
                f".hl{{color:{c} !important;-webkit-text-fill-color:{c} !important}}"
                f".EN,.head p{{color:{c} !important}}.badge2{{border-color:{c} !important}}")

    def scene(self, cid, body, script, css=""):
        html = f"""<template>
<style>{self.base_css()}{self.st.css}{self.tone_css()}{css}</style>
<div id="root" data-composition-id="{cid}" data-width="1080" data-height="1920">
{body}
</div>
<script>
(function(){{
const tl = gsap.timeline({{paused:true}});
{script}
window.__timelines = window.__timelines || {{}};
window.__timelines["{cid}"] = tl;
}})();
</script>
</template>
"""
        open(os.path.join(self.out, "compositions", cid + ".html"), "w", encoding="utf-8").write(stamp_ids(html, cid))

    # ------------------------------------------------------------ 人物几何（来自 measure.py）
    def _frames(self, t0, t1):
        fr = [f for f in self.geom.get("frames", []) if t0 - 0.01 <= f["t"] <= t1 + 0.01 and f.get("face")]
        if not fr:
            fr = [f for f in self.geom.get("frames", []) if f.get("face")]
        if not fr:
            raise BuildError("geom.json 里没有人脸数据，先跑 scripts/measure.py")
        return fr

    def face_box(self, t0, t1, zoom=False):
        """时间段内人脸框的并集（像素，人物画面坐标）。zoom=True 时按跳切推近放大后的位置算。"""
        fr = self._frames(t0, t1)
        x0 = min(f["face"][0] for f in fr); y0 = min(f["face"][1] for f in fr)
        x1 = max(f["face"][0] + f["face"][2] for f in fr); y1 = max(f["face"][1] + f["face"][3] for f in fr)
        if zoom:
            cx, cy = self.zoom_origin()
            x0, x1 = cx + (x0 - cx) * ZOOM, cx + (x1 - cx) * ZOOM
            y0, y1 = cy + (y0 - cy) * ZOOM, cy + (y1 - cy) * ZOOM
        return [round(x0), round(y0), round(x1 - x0), round(y1 - y0)]

    def face_med(self, t0, t1):
        fr = self._frames(t0, t1)
        cx = statistics.median(f["face"][0] + f["face"][2] / 2 for f in fr)
        cy = statistics.median(f["face"][1] + f["face"][3] / 2 for f in fr)
        fh = statistics.median(f["face"][3] for f in fr)
        return cx, cy, fh

    def head_top(self, t0, t1, zoom=False):
        fr = self._frames(t0, t1)
        tops = [f["head_top"] for f in fr if f.get("head_top") is not None]
        top = min(tops) if tops else min(f["face"][1] - 0.6 * f["face"][3] for f in fr)
        if zoom:
            cx, cy = self.zoom_origin()
            top = cy + (top - cy) * ZOOM
        return round(top)

    def body_span(self, t0, t1, y):
        """某一行人物身体的左右边界（取时间段内最宽）。"""
        fr = self._frames(t0, t1)
        ls, rs = [], []
        for f in fr:
            ext = f.get("extents") or []
            if not ext:
                continue
            row = min(ext, key=lambda e: abs(e[0] - y))
            if row[1] >= 0:
                ls.append(row[1]); rs.append(row[2])
        if not ls:
            x, _, w, _ = self.face_box(t0, t1)
            return x - w * 0.6, x + w * 1.6
        return min(ls), max(rs)

    def zoom_origin(self):
        if not hasattr(self, "_zo"):
            cx, cy, _ = self.face_med(0, self.aroll_dur)
            self._zo = (round(cx), round(cy))
        return self._zo

    def zone(self, seg, name, x, y, w, h):
        """登记压在人物画面上的元素范围，build 结束时统一查是否碰脸。"""
        self.zones.append((seg.id, name, [round(x), round(y), round(w), round(h)], seg.start, seg.end, seg.zoom))

    # ------------------------------------------------------------ 音效
    def sfx_at(self, seg, t_local, kind, vol=None):
        if seg.sfx_on:
            self.sfx.append((round(seg.start + t_local, 3), kind, vol))


# ---------------------------------------------------------------- 工具函数
def stamp_ids(html, pfx):
    """给每个标签补 data-hf-id，Studio 里才能逐个选中编辑。"""
    n = [0]

    def rep(m):
        tag, rest = m.group(1), m.group(2) or ""
        if tag.lower() in ("template", "style", "script", "html", "head", "meta", "title", "body", "br", "defs", "stop") or "data-hf-id" in rest:
            return m.group(0)
        n[0] += 1
        return f'<{tag} data-hf-id="{pfx}-x{n[0]}"{rest}>'

    head, sep, tail = html.partition("<script>")
    return re.sub(r"<([a-zA-Z][a-zA-Z0-9]*)(\s[^<>]*?)?>", rep, head) + sep + tail


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rich(s):
    """显示用文字：转义，| 换成换行，*重点词* 换成本风格（或本段色调）的强调色。"""
    out = esc(s).replace("|", "<br>")
    return re.sub(r"\*(.+?)\*", r'<span class="hl">\1</span>', out)


br = rich


def plain(s):
    """去掉强调标记，用于量宽度、逐字展开。"""
    return str(s).replace("*", "")


def chars(text, cls):
    """逐字展开用：每个字一个 span，渐变类挂在每个字上（父级不能再挂渐变类）。*重点词* 里的字加强调色。"""
    parts, em = [], False
    for ch in str(text):
        if ch == "*":
            em = not em
            continue
        if ch == "|":
            parts.append("<br>")
        elif ch == " ":
            parts.append('<span class="ch" style="display:inline-block">&nbsp;</span>')
        else:
            parts.append(f'<span class="ch {cls}{" hl" if em else ""}" style="display:inline-block">{esc(ch)}</span>')
    return "".join(parts)


def chars_in(sel, t, n, per=0.06):
    """逐字出现：每个字从下方带模糊浮上来，按字数错开。"""
    per = max(0.03, min(0.1, per))
    return (f'tl.set("{sel}",{{opacity:1}},{t:.3f});\n'
            f'tl.fromTo("{sel} .ch",{{opacity:0,y:26,filter:"blur(8px)"}},{{opacity:1,y:0,filter:"blur(0px)",duration:0.36,stagger:{per:.3f},ease:"power3.out"}},{t:.3f});\n')


def tw(s):
    """估算文字宽度（以一个汉字为 1）。"""
    w = 0.0
    for ch in str(s):
        if ch in "|*":
            continue
        w += 0.55 if re.match(r"[A-Za-z0-9 .,%$+\-:/·]", ch) else 1.0
    return w


def fit_fs(text, width, fs_max, fs_min=28, ratio=1.0):
    lines = str(text).split("|")
    m = max(tw(l) for l in lines) or 1
    return int(max(fs_min, min(fs_max, width / (m * ratio))))


def floaty(sel, dur, amp=9, period=3.6, phase=0.0, rot=0.0):
    """持续上下缓动（参考片里卡片、小窗、标签一直在轻微浮动）。"""
    amp = round(amp * MOTION["amp"], 1)
    half = period / 2
    n = max(1, int((dur - phase) / half))
    s = f'tl.fromTo("{sel}",{{y:{-amp}}},{{y:{amp},duration:{half:.2f},ease:"sine.inOut",yoyo:true,repeat:{n}}},{phase:.2f});\n'
    if rot:
        h2 = half * 1.3
        s += f'tl.fromTo("{sel}",{{rotation:{-rot}}},{{rotation:{rot},duration:{h2:.2f},ease:"sine.inOut",yoyo:true,repeat:{max(1, int((dur - phase) / h2))}}},{phase:.2f});\n'
    return s


def sway(sel, dur, deg=3.0, period=4.8, start=0.0, persp=1800, axis="rotationY"):
    """透视面板轻摆。"""
    half = period / 2
    return (f'tl.set("{sel}",{{transformPerspective:{persp}}},0);\n'
            f'tl.fromTo("{sel}",{{{axis}:{-deg}}},{{{axis}:{deg},duration:{half:.2f},ease:"sine.inOut",yoyo:true,repeat:{max(1, int((dur - start) / half))}}},{start:.2f});\n')


def drift(sel, dur, frm=1.0, to=1.08):
    return f'tl.fromTo("{sel}",{{scale:{frm}}},{{scale:{to},duration:{dur:.2f},ease:"none"}},0);\n'


def lcg(seed):
    s = seed
    while True:
        s = (s * 9301 + 49297) % 233280
        yield s / 233280.0


# ---------------------------------------------------------------- 小窗（人脸安全取景）
def pip(film, seg, shape, x, y, w, h=None, sfx="", ring=True):
    """人物小窗。shape: circle 圆窗 / rect 竖窗 / squircle 圆角方窗。
    按这一段的人脸位置取景：脸完整、头顶留空，画面始终铺满窗口。"""
    h = h or w
    cx, cy, fh = film.face_med(seg.start, seg.end)
    fb = film.face_box(seg.start, seg.end)
    if shape == "rect":
        k_face, fy = 0.24, 0.36
    elif shape == "squircle":
        k_face, fy = 0.36, 0.46
    else:
        k_face, fy = 0.40, 0.48
    s = (k_face * h) / max(fh, 1)
    s = max(s, w / 1080, h / 1920)            # 画面要铺满窗口
    s = min(s, (0.86 * min(w, h)) / max(fb[2], fb[3]))  # 脸的活动范围要装得下
    s = max(s, w / 1080, h / 1920)
    vw, vh = 1080 * s, 1920 * s
    left = w / 2 - cx * s
    top = h * fy - cy * s
    left = min(0, max(w - vw, left))
    top = min(0, max(h - vh, top))
    radius = {"circle": "50%", "rect": "18px", "squircle": "34%"}.get(shape, "18px")
    wid = f"{seg.id}-pipw{sfx}"
    dur = min(seg.d, max(0.1, film.aroll_dur - seg.start))
    cls = "pipc ring" if ring else "pipc"
    return (f'<div id="{wid}f" class="fl" style="left:{x:.0f}px;top:{y:.0f}px;width:{w:.0f}px;height:{h:.0f}px">'
            f'<div id="{wid}" class="{cls} pip-{shape}" style="left:0;top:0;width:{w:.0f}px;height:{h:.0f}px;border-radius:{radius}">'
            f'<video id="{seg.id}-pip{sfx}" class="clip" data-start="0" data-duration="{dur:.3f}" data-media-start="{seg.start:.3f}" '
            f'src="{film.a("aroll")}" muted playsinline style="width:{vw:.0f}px;height:{vh:.0f}px;left:{left:.0f}px;top:{top:.0f}px"></video>'
            f'</div></div>')


def pip_in(seg, t=0.2, sfx=""):
    return f'tl.fromTo("#{seg.id}-pipw{sfx}",{{opacity:0,scale:0.6}},{{opacity:1,scale:1,duration:0.45,ease:"back.out(1.7)"}},{t});\n'


# ---------------------------------------------------------------- 图标
_ICON_CACHE = {}


def icon(name, size=48, color="currentColor", stroke=1.8, extra=""):
    """Lucide 图标（ISC 许可）内联 SVG。"""
    if name not in _ICON_CACHE:
        p = os.path.join(SKILL_ROOT, "assets", "icons", "lucide", f"{name}.svg")
        if not os.path.exists(p):
            raise BuildError(f"没有图标 {name}（在 assets/icons/lucide 里找名字，或用 scripts/icons.py 按关键词搜）")
        svg = open(p, encoding="utf-8").read()
        inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
        inner = re.sub(r"<!--.*?-->", "", inner, flags=re.S)
        inner = re.sub(r"\s*\n\s*", "", inner).strip()
        _ICON_CACHE[name] = inner
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
            f'stroke-linecap="round" stroke-linejoin="round" {extra}>{_ICON_CACHE[name]}</svg>')
