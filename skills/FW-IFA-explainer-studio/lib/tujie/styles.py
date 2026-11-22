# -*- coding: utf-8 -*-
"""五套风格包。每套用同一套类名（版式代码只认这些类名），各自给材质、配色、字体和入场动作：

  .T1 主标题字  .T2 次标题字  .TR 警示字  .TB 大字报字（金句、收尾）  .EN 英文副题
  .head（h2＋p＋.orn）章节标题块
  .card 深色材质卡  .card .t/.e  .dash 内圈线  .glow 点亮框
  .paper 浅色材质（纸、瓷、珐琅）  .tag 小标签  .badge2 画面上的名称牌
  .ring 小窗边框  .numt 大数字
  底座：.dk .dkg .rule .badge .chap .upd   字幕：.cap

骨架（底座位置、字幕位置、人脸安全规则、缓动幅度）五套完全一样；差异只在这里和各风格的招牌版式。
"""
import json


class Style:
    key = ""
    name = ""
    en = ""
    accents = {}
    pip = {"shape": "circle", "size": 280}
    chart = "glass"        # 柱状图：glass 深色玻璃 / paper 白纸立体面板
    quote = "particles"    # 金句：particles 粒子光球 / banner 光带关键词 / brush 书法大字 / block 引号文字块
    chapter = "orn"        # 章节卡：orn 金属字＋纹饰 / marquee 母题图标滚动 / plaque 金框铭牌 / split 斜切分屏 / hud 环形
    signature = []         # 本风格招牌版式（每支片至少用一个）
    css_tpl = ""
    acc = ""

    def sub_color(self):
        """头顶副标题、引子用色：要在亮天空、白墙上也看得清。"""
        return {"cilan": self.c.get("lt", "#A9C2FF"), "kapai": self.c.get("fr", self.c["a"])}.get(self.key, self.c["a"])

    def __init__(self, accent=None):
        self.acc_key = accent if accent in self.accents else next(iter(self.accents))
        self.c = dict(self.accents[self.acc_key])
        self.css = ""

    def bind(self, film):
        """拿到素材路径后生成 CSS。"""
        c = dict(self.c)
        for k in ("tex_stone", "tex_archive"):
            c[k] = film.A.get(k, "")
        self.css = self.css_tpl % c
        return self

    # ---------------- 动作签名（入场）。默认用本风格的，段落层参数可以按内容换（见 set_mode）
    enter_default = "blur"
    card_default = "slide"

    def set_mode(self, data):
        """每段开始前调用：按这一段 data 里的 energy／enter／card_enter 调整动作。"""
        self.mode = {"energy": data.get("energy", "normal"), "enter": data.get("enter"), "card": data.get("card_enter")}

    def _k(self):
        return {"calm": 1.35, "punch": 0.72}.get(getattr(self, "mode", {}).get("energy"), 1.0)

    def _ease(self, default):
        return {"calm": "power2.out", "punch": "expo.out"}.get(getattr(self, "mode", {}).get("energy"), default)

    def title_in(self, sel, t, dur=None):
        name = (getattr(self, "mode", {}) or {}).get("enter") or self.enter_default
        fn = ENTER.get(name) or ENTER[self.enter_default]
        return fn(sel, t, (dur or ENTER_DUR[name if name in ENTER else self.enter_default]) * self._k(), self._ease)

    def sub_in(self, sel, t):
        return f'tl.fromTo("{sel}",{{opacity:0,y:16}},{{opacity:1,y:0,duration:{0.38 * self._k():.2f},ease:"{self._ease("power3.out")}"}},{t:.3f});\n'

    def card_in(self, sel, t, k=0, rng=None, frm="right"):
        name = (getattr(self, "mode", {}) or {}).get("card") or self.card_default
        fn = CARD.get(name) or CARD[self.card_default]
        return fn(sel, t, self._k(), self._ease, k, rng, frm)

    def stamp_in(self, sel, t):
        return f'tl.fromTo("{sel}",{{opacity:0,scale:2.2,rotation:-18}},{{opacity:1,scale:1,rotation:-8,duration:{0.28 * self._k():.2f},ease:"power4.in"}},{t:.3f});\n'

    def out(self, sel, t, dur=0.25):
        return f'tl.to("{sel}",{{opacity:0,y:-20,duration:{dur},ease:"power2.in"}},{t:.3f});\n'


# ---------------------------------------------------------------- 共用动作库
# 标题入场：每套风格有默认的一种（动作签名），段落可以按内容换成别的
def _blur(sel, t, dur, ease):
    return f'tl.fromTo("{sel}",{{opacity:0,scale:1.3,filter:"blur(12px)"}},{{opacity:1,scale:1,filter:"blur(0px)",duration:{dur:.2f},ease:"{ease("power4.out")}"}},{t:.3f});\n'


def _stretch(sel, t, dur, ease):  # 字距收拢的效果用横向缩放做（字距动画会按整像素跳，逐帧渲染时发抖）
    return f'tl.fromTo("{sel}",{{opacity:0,scaleX:1.45,filter:"blur(6px)"}},{{opacity:1,scaleX:1,filter:"blur(0px)",duration:{dur:.2f},ease:"{ease("power3.out")}"}},{t:.3f});\n'


def _wipe(sel, t, dur, ease):
    return (f'tl.fromTo("{sel}",{{opacity:0,clipPath:"inset(0% 100% 0% 0%)",y:10}},'
            f'{{opacity:1,clipPath:"inset(0% 0% 0% 0%)",y:0,duration:{dur:.2f},ease:"{ease("power2.inOut")}"}},{t:.3f});\n')


def _flip(sel, t, dur, ease):
    return (f'tl.set("{sel}",{{transformPerspective:900}},0);\n'
            f'tl.fromTo("{sel}",{{opacity:0,rotationX:-70,y:24}},{{opacity:1,rotationX:0,y:0,duration:{dur:.2f},ease:"{ease("power3.out")}"}},{t:.3f});\n')


def _flicker(sel, t, dur, ease):
    return (f'tl.set("{sel}",{{opacity:0}},0);\n'
            f'tl.to("{sel}",{{keyframes:[{{opacity:1,duration:0.04}},{{opacity:0.15,duration:0.05}},{{opacity:1,duration:0.05}},'
            f'{{opacity:0.35,duration:0.06}},{{opacity:1,duration:0.08}}]}},{t:.3f});\n')


def _rise(sel, t, dur, ease):
    return f'tl.fromTo("{sel}",{{opacity:0,y:46}},{{opacity:1,y:0,duration:{dur:.2f},ease:"{ease("power3.out")}"}},{t:.3f});\n'


def _zoom(sel, t, dur, ease):  # 冲击：从小放大并回弹，适合反问、转折、结论
    return f'tl.fromTo("{sel}",{{opacity:0,scale:0.4}},{{opacity:1,scale:1,duration:{dur:.2f},ease:"back.out(2.2)"}},{t:.3f});\n'


ENTER = {"blur": _blur, "stretch": _stretch, "wipe": _wipe, "flip": _flip, "flicker": _flicker, "rise": _rise, "zoom": _zoom}
ENTER_DUR = {"blur": 0.42, "stretch": 0.7, "wipe": 0.7, "flip": 0.55, "flicker": 0.3, "rise": 0.5, "zoom": 0.45}


# 卡片入场
def _c_slide(sel, t, k, ease, i, rng, frm):
    dx = {"right": 80, "left": -80}.get(frm, 0)
    dy = {"up": 60, "down": -60}.get(frm, 0)
    return f'tl.fromTo("{sel}",{{opacity:0,x:{dx},y:{dy}}},{{opacity:1,x:0,y:0,duration:{0.5 * k:.2f},ease:"{ease("power3.out")}"}},{t:.3f});\n'


def _c_drop(sel, t, k, ease, i, rng, frm):
    r = rng.uniform(-3, 3) if rng else 0
    return f'tl.fromTo("{sel}",{{opacity:0,y:70,rotation:{r + 4:.1f}}},{{opacity:1,y:0,rotation:{r:.1f},duration:{0.55 * k:.2f},ease:"back.out(1.3)"}},{t:.3f});\n'


def _c_swing(sel, t, k, ease, i, rng, frm):
    ry = 28 if frm != "left" else -28
    return (f'tl.set("{sel}",{{transformPerspective:1400}},0);\n'
            f'tl.fromTo("{sel}",{{opacity:0,rotationY:{ry},x:{ry * 2}}},{{opacity:1,rotationY:0,x:0,duration:{0.6 * k:.2f},ease:"{ease("power3.out")}"}},{t:.3f});\n')


def _c_toss(sel, t, k, ease, i, rng, frm):
    r = rng.uniform(-16, 16) if rng else (-12 if i % 2 else 12)
    return f'tl.fromTo("{sel}",{{opacity:0,y:-260,rotation:{r:.1f}}},{{opacity:1,y:0,rotation:0,duration:{0.7 * k:.2f},ease:"back.out(1.2)"}},{t:.3f});\n'


def _c_pop(sel, t, k, ease, i, rng, frm):
    return (f'tl.fromTo("{sel}",{{opacity:0,scale:0.86}},{{opacity:1,scale:1,duration:{0.35 * k:.2f},ease:"back.out(2)"}},{t:.3f});\n'
            f'tl.fromTo("{sel}",{{filter:"brightness(2.2)"}},{{filter:"brightness(1)",duration:0.4,ease:"power2.out"}},{t + 0.05:.3f});\n')


def _c_rise(sel, t, k, ease, i, rng, frm):
    return f'tl.fromTo("{sel}",{{opacity:0,y:40}},{{opacity:1,y:0,duration:{0.45 * k:.2f},ease:"{ease("power3.out")}"}},{t:.3f});\n'


CARD = {"slide": _c_slide, "drop": _c_drop, "swing": _c_swing, "toss": _c_toss, "pop": _c_pop, "rise": _c_rise}


# ======================================================================== 1 炭金
class Tanjin(Style):
    key, name, en = "tanjin", "炭金", "Charcoal Gold"
    accents = {
        "copper": {"a": "#F2B27A", "argb": "242,178,122", "a2": "#E59A5E", "deep": "#8C4520", "hi": "#FFE1BE"},
        "gold": {"a": "#E9C46A", "argb": "233,196,106", "a2": "#D6A93F", "deep": "#7A5A12", "hi": "#FFF0C2"},
        "steel": {"a": "#9DB8FF", "argb": "157,184,255", "a2": "#6E8FE0", "deep": "#26386E", "hi": "#E6EEFF"},
    }
    pip = {"shape": "circle", "size": 290}
    chart, quote, chapter = "glass", "particles", "orn"
    signature = ["bigword_band", "chain", "quote"]
    enter_default, card_default = "blur", "slide"
    css_tpl = """
.T1{background:linear-gradient(180deg,#FFF8EE 0%%,%(hi)s 30%%,%(a2)s 50%%,%(deep)s 56%%,%(a2)s 74%%,%(hi)s 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 3px 0 rgba(30,12,4,.9)) drop-shadow(0 12px 22px rgba(0,0,0,.6));font-family:SM}
.T2{background:linear-gradient(180deg,#FFFFFF 0%%,#EEF0F4 32%%,#A9AFBA 50%%,#565C68 56%%,#C6CBD4 76%%,#FFFFFF 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 3px 0 #1d2027) drop-shadow(0 12px 22px rgba(0,0,0,.6));font-family:SM}
.TR{background:linear-gradient(180deg,#FFF1EE 0%%,#FFB4A8 30%%,#F04A3E 52%%,#7A1410 58%%,#E5574C 76%%,#FFD3CC 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 3px 0 #2a0604) drop-shadow(0 12px 22px rgba(0,0,0,.6));font-family:SM}
.TB{background:linear-gradient(180deg,#FFFFFF 0%%,#EEF0F4 32%%,#A9AFBA 50%%,#565C68 56%%,#C6CBD4 76%%,#FFFFFF 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 3px 0 #1d2027) drop-shadow(0 12px 22px rgba(0,0,0,.6));font-family:SM}
.EN{font:600 22px/1 EN,Inter,sans-serif;letter-spacing:6px;color:rgba(%(argb)s,.85);text-transform:uppercase}
.head{position:absolute;left:0;right:0;text-align:center}
.head .orn{display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:18px}
.head .orn i{display:block;width:120px;height:1px;background:linear-gradient(90deg,transparent,rgba(%(argb)s,.9))}
.head .orn i.r{background:linear-gradient(270deg,transparent,rgba(%(argb)s,.9))}
.head .orn s{display:block;width:12px;height:12px;border:1.5px solid %(a)s;transform:rotate(45deg)}
.head h2{font:400 84px/1.1 SM;letter-spacing:2px;color:#F3EEE8;text-shadow:0 4px 18px rgba(0,0,0,.5);margin:0}
.head p{font:600 24px/1 EN,Inter,sans-serif;letter-spacing:6px;color:rgba(%(argb)s,.85);margin:16px 0 0;text-transform:uppercase}
.card{position:absolute;border-radius:20px;background:linear-gradient(180deg,rgba(46,44,44,.84),rgba(14,13,14,.93));border:1.5px solid rgba(255,255,255,.14);box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 20px 40px rgba(0,0,0,.5);overflow:hidden;color:#F4EEE8}
.card .t{font:400 54px/1.12 SM;color:#F4EEE8}
.card .e{font:600 18px/1 EN,Inter,sans-serif;letter-spacing:4px;color:rgba(%(argb)s,.8);margin-top:12px;text-transform:uppercase}
.card .k{font:400 110px/1 SM;color:rgba(%(argb)s,.9)}
.dash{position:absolute;inset:10px;border:1.5px dashed rgba(255,255,255,.16);border-radius:14px;pointer-events:none}
.glow{position:absolute;inset:-2px;border-radius:21px;border:2px solid rgba(%(argb)s,.9);box-shadow:0 0 0 1px rgba(%(argb)s,.25),0 0 46px rgba(%(argb)s,.35);opacity:0;pointer-events:none}
.paper{position:absolute;border-radius:14px;background:linear-gradient(180deg,#F7F4EE,#E4DED3);color:#1E1A16;box-shadow:0 24px 50px rgba(0,0,0,.55)}
.tag{position:absolute;padding:8px 18px;border-radius:10px;font:400 30px/1 SM;color:#2B2116;background:linear-gradient(180deg,#FFF2DC,#E9C28F);box-shadow:0 6px 16px rgba(0,0,0,.4);white-space:nowrap}
.badge2{position:absolute;padding:12px 22px;border-radius:12px;font:400 36px/1 SM;color:#FFF4E8;background:linear-gradient(180deg,rgba(60,40,28,.92),rgba(20,14,10,.95));border:1.5px solid rgba(%(argb)s,.8);box-shadow:0 0 26px rgba(%(argb)s,.3);white-space:nowrap}
.ring{border:4px solid rgba(255,244,232,.95) !important;box-shadow:0 0 0 1px rgba(0,0,0,.35),0 0 30px rgba(255,214,180,.38),0 18px 40px rgba(0,0,0,.6)}
.numt{font:500 150px/1 NUM,EN,sans-serif;color:#FFF4E8;letter-spacing:2px;text-shadow:0 0 30px rgba(%(argb)s,.45),0 8px 24px rgba(0,0,0,.6)}
.bgbase{position:absolute;inset:0;background:#0B0B0D}
.motifc{color:rgba(%(argb)s,.10)}
.chip{color:%(a)s}
.hl{color:%(hi)s;-webkit-text-fill-color:%(hi)s;text-shadow:0 0 18px rgba(%(argb)s,.6)}
.grade{filter:contrast(1.06) saturate(.86) brightness(.95)}.gradeov{position:absolute;inset:0;pointer-events:none;background:linear-gradient(180deg,rgba(255,170,90,.14),rgba(20,10,0,.22));mix-blend-mode:soft-light}
/* 底座 */
.dk{position:absolute;left:0;right:0;top:1576px;bottom:0;background:linear-gradient(180deg,#141213 0%%,#0C0B0C 38%%,#070707 100%%)}
.dkg{position:absolute;left:290px;top:1576px;width:500px;height:170px;background:radial-gradient(ellipse at 50%% 0%%,rgba(%(argb)s,.20),transparent 70%%)}
.rule{position:absolute;left:0;right:0;top:1574px;height:2px;background:linear-gradient(90deg,transparent,rgba(255,236,214,.85) 30%%,rgba(255,236,214,.85) 70%%,transparent)}
.badge{position:absolute;left:50%%;top:1548px;transform:translateX(-50%%);height:54px;padding:0 30px;border-radius:12px;text-align:center;background:linear-gradient(180deg,#FDFBF7 0%%,#E6DED2 48%%,#BDB2A3 52%%,#EEE7DC 100%%);box-shadow:0 2px 0 #6f6658,0 6px 18px rgba(0,0,0,.5);font:400 36px/54px SM;color:#2B2622;letter-spacing:1px;white-space:nowrap}
.badge b{color:%(deep)s;font-weight:400}
.chap .n{font:400 26px/1 SM;color:rgba(%(argb)s,.5);letter-spacing:2px}
.chap .l{font:400 40px/1 SM;color:rgba(255,255,255,.36);margin-top:8px}
.chap .on .n{color:%(a)s}.chap .on .l{color:#FFF4E8}
.chap .u{background:rgba(255,255,255,.10)}
.chap .ud{background:linear-gradient(90deg,%(a2)s,%(hi)s);box-shadow:0 0 14px rgba(%(argb)s,.8)}
.upd{background:linear-gradient(180deg,rgba(40,20,20,.92),rgba(14,9,9,.96));border:1.5px solid rgba(255,110,100,.75);box-shadow:0 0 36px rgba(255,80,70,.25);border-radius:20px}
.upd .lab{color:#FF8A80}.upd .dot{background:#FF5A57;box-shadow:0 0 12px #FF5A57}
.upd .ti{color:#FFF4EC;font-family:SM}
.upd .st{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.12)}
.upd .sv{font-family:SM;color:#FFE1BE}
.cap{text-shadow:0 2px 4px rgba(0,0,0,.85),0 0 14px rgba(0,0,0,.75),0 0 30px rgba(0,0,0,.45)}
"""


# ======================================================================== 2 档案
class Dangan(Style):
    key, name, en = "dangan", "档案", "Archive"
    accents = {
        "brass": {"a": "#D8B26E", "argb": "216,178,110", "m": "#E8487E", "mrgb": "232,72,126"},
        "crimson": {"a": "#E0A15A", "argb": "224,161,90", "m": "#E2363F", "mrgb": "226,54,63"},
        "teal": {"a": "#C9B48A", "argb": "201,180,138", "m": "#2FB7A6", "mrgb": "47,183,166"},
    }
    pip = {"shape": "circle", "size": 250}
    chart, quote, chapter = "glass", "banner", "marquee"
    signature = ["logo_wall", "doc", "chapter"]
    enter_default, card_default = "stretch", "drop"
    css_tpl = """
.T1{background:linear-gradient(180deg,#FFFFFF 0%%,#ECECEC 36%%,#8C8C8C 50%%,#F4F4F4 63%%,#B9B9B9 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 2px 0 rgba(0,0,0,.8)) drop-shadow(0 10px 20px rgba(0,0,0,.65));font-family:SR}
.T2{color:%(a)s;font-family:SR;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.TR{color:#E2363F;font-family:SR;text-shadow:0 0 18px rgba(226,54,63,.45),0 4px 14px rgba(0,0,0,.6)}
.TB{background:linear-gradient(180deg,#FFFFFF 0%%,#ECECEC 36%%,#8C8C8C 50%%,#F4F4F4 63%%,#B9B9B9 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 2px 0 rgba(0,0,0,.8)) drop-shadow(0 10px 20px rgba(0,0,0,.65));font-family:SR}
.EN{font:500 24px/1 EN,Inter,sans-serif;letter-spacing:5px;color:rgba(255,255,255,.72)}
.head{position:absolute;left:0;right:0;text-align:center}
.head .orn{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:20px}
.head .orn i{display:block;width:160px;height:1px;background:rgba(%(argb)s,.7)}
.head .orn i.r{background:rgba(%(argb)s,.7)}
.head .orn s{display:block;width:8px;height:8px;border-radius:50%%;background:%(a)s}
.head h2{font:400 82px/1.12 SR;letter-spacing:6px;color:#F2EDE4;text-shadow:0 4px 18px rgba(0,0,0,.6);margin:0}
.head p{font:500 24px/1 EN,Inter,sans-serif;letter-spacing:6px;color:rgba(%(argb)s,.9);margin:18px 0 0}
.card{position:absolute;border-radius:10px;background:linear-gradient(180deg,#FBF8F2,#E9E3D7);border:1px solid rgba(255,255,255,.6);box-shadow:0 20px 44px rgba(0,0,0,.6);overflow:hidden;color:#2A231C}
.card .t{font:400 52px/1.14 SR;color:#231C15;letter-spacing:2px}
.card .e{font:600 17px/1 EN,Inter,sans-serif;letter-spacing:4px;color:#8B6B3E;margin-top:12px;text-transform:uppercase}
.card .k{font:400 104px/1 SR;color:rgba(139,107,62,.85)}
.dash{position:absolute;inset:9px;border:1px solid rgba(139,107,62,.28);border-radius:6px;pointer-events:none}
.glow{position:absolute;inset:-3px;border-radius:12px;border:3px solid %(a)s;box-shadow:0 0 34px rgba(%(argb)s,.55);opacity:0;pointer-events:none}
.paper{position:absolute;border-radius:6px;background:linear-gradient(180deg,#FBF8F2,#EDE7DC);color:#1E1A16;box-shadow:0 26px 60px rgba(0,0,0,.6)}
.tag{position:absolute;padding:9px 18px 9px 16px;border-radius:4px;font:400 30px/1 SR;color:#2A1F12;background:linear-gradient(180deg,#F3DCA6,#C9A15C);box-shadow:0 6px 16px rgba(0,0,0,.45);white-space:nowrap;letter-spacing:2px}
.badge2{position:absolute;padding:12px 24px;border-radius:6px;font:400 34px/1 SR;color:#F4EEE2;background:rgba(18,13,11,.9);border:1.5px solid %(a)s;letter-spacing:3px;white-space:nowrap}
.ring{border:7px solid #F4F1EA !important;box-shadow:0 0 0 1px rgba(0,0,0,.5),0 16px 36px rgba(0,0,0,.65)}
.numt{font:500 150px/1 NUM,EN,sans-serif;color:#F4EEE2;letter-spacing:2px;text-shadow:0 8px 24px rgba(0,0,0,.6)}
.bgbase{position:absolute;inset:0;background:#120D0B url('%(tex_archive)s') center/cover}
.motifc{color:rgba(%(argb)s,.85)}
.chip{color:%(a)s}
.seal{position:absolute;width:150px;height:150px;border-radius:50%%;background:radial-gradient(circle at 38%% 32%%,#F07A3A,#C2361A 55%%,#8E220E);box-shadow:0 6px 14px rgba(0,0,0,.5),inset 0 -6px 12px rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;font:400 46px/1 SR;color:rgba(255,236,220,.92);letter-spacing:2px}
.streak{position:absolute;left:0;right:0;overflow:hidden;background:linear-gradient(90deg,#1A0610,#3A0C22 30%%,#2A0818 70%%,#12040A)}
.hl{color:%(m)s;-webkit-text-fill-color:%(m)s}
.grade{filter:sepia(.3) saturate(.72) contrast(1.08) brightness(.9)}.gradeov{position:absolute;inset:0;pointer-events:none;background:rgba(120,70,30,.2);mix-blend-mode:multiply}
/* 底座 */
.dk{position:absolute;left:0;right:0;top:1576px;bottom:0;background:linear-gradient(180deg,#17110E,#0D0907)}
.dkg{position:absolute;left:240px;top:1576px;width:600px;height:150px;background:radial-gradient(ellipse at 50%% 0%%,rgba(%(argb)s,.16),transparent 70%%)}
.rule{position:absolute;left:0;right:0;top:1574px;height:2px;background:linear-gradient(90deg,transparent,rgba(%(argb)s,.9) 25%%,rgba(%(argb)s,.9) 75%%,transparent)}
.badge{position:absolute;left:50%%;top:1548px;transform:translateX(-50%%);height:54px;padding:0 30px;border-radius:6px;text-align:center;background:linear-gradient(180deg,#FBF8F2,#E2DACB);border:1px solid %(a)s;box-shadow:0 6px 18px rgba(0,0,0,.55);font:400 34px/54px SR;color:#231C15;letter-spacing:3px;white-space:nowrap}
.badge b{color:#8B5A2B;font-weight:400}
.chap .n{font:400 26px/1 SR;color:rgba(%(argb)s,.55);letter-spacing:2px}
.chap .l{font:400 40px/1 SR;color:rgba(255,255,255,.34);margin-top:8px;letter-spacing:3px}
.chap .on .n{color:%(a)s}.chap .on .l{color:#F4EEE2}
.chap .u{background:rgba(255,255,255,.08)}
.chap .ud{background:linear-gradient(90deg,%(m)s,%(a)s);box-shadow:0 0 14px rgba(%(mrgb)s,.6)}
.upd{background:linear-gradient(180deg,#FBF8F2,#E6DFD2);border:1px solid %(a)s;box-shadow:0 10px 30px rgba(0,0,0,.6);border-radius:8px}
.upd .lab{color:#B0302F;font-family:SR}.upd .dot{background:#C2361A;box-shadow:none}
.upd .ti{color:#231C15;font-family:SR}
.upd .nt{color:rgba(35,28,21,.5) !important}
.upd .st{background:rgba(139,107,62,.08);border:1px solid rgba(139,107,62,.35)}
.upd .sl{color:rgba(35,28,21,.6) !important}.upd .sv{font-family:SR;color:#231C15}
.cap{text-shadow:0 2px 4px rgba(0,0,0,.9),0 0 14px rgba(0,0,0,.8),0 0 30px rgba(0,0,0,.5)}
"""



# ======================================================================== 3 卡牌（取自星巴克、英伟达两条参考：讲公司和资本）
class Kapai(Style):
    key, name, en = "kapai", "卡牌", "Showcase"
    accents = {
        "green": {"a": "#2FD07A", "argb": "47,208,122", "fr": "#EDE39A", "frgb": "237,227,154", "m": "#8B5CF6", "mrgb": "139,92,246", "navy": "#14402A"},
        "amber": {"a": "#F5B83D", "argb": "245,184,61", "fr": "#F3E2B0", "frgb": "243,226,176", "m": "#E0475B", "mrgb": "224,71,91", "navy": "#4A3410"},
        "cyan": {"a": "#33C9E8", "argb": "51,201,232", "fr": "#DDE9F2", "frgb": "221,233,242", "m": "#8B5CF6", "mrgb": "139,92,246", "navy": "#123A4A"},
    }
    pip = {"shape": "circle", "size": 180}
    chart, quote, chapter = "paper", "particles", "orn"
    signature = ["chain", "compare", "quote"]
    enter_default, card_default = "zoom", "toss"
    css_tpl = """
.T1{color:#FFFFFF;font-family:HB,SM;text-shadow:0 2px 0 rgba(0,0,0,.55),0 10px 26px rgba(0,0,0,.6)}
.T2{color:%(a)s;font-family:HB,SM;text-shadow:0 0 18px rgba(%(argb)s,.45),0 6px 18px rgba(0,0,0,.6)}
.TR{color:#FF5A5F;font-family:HB,SM;text-shadow:0 0 18px rgba(255,90,95,.45),0 6px 18px rgba(0,0,0,.6)}
.TB{color:#FFFFFF;font-family:HB,SM;text-shadow:0 0 30px rgba(%(argb)s,.35),0 10px 28px rgba(0,0,0,.65)}
.EN{font:600 22px/1 EN,Inter,sans-serif;letter-spacing:4px;color:rgba(%(frgb)s,.78)}
.head{position:absolute;left:0;right:0;text-align:center}
.head .orn{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:16px}
.head .orn i{display:block;width:120px;height:2px;background:linear-gradient(90deg,transparent,%(fr)s)}
.head .orn i.r{background:linear-gradient(270deg,transparent,%(fr)s)}
.head .orn s{display:block;width:10px;height:10px;border-radius:50%%;background:%(fr)s;box-shadow:0 0 10px %(fr)s}
.head h2{font:400 84px/1.1 HB,SM;letter-spacing:3px;color:#fff;margin:0;text-shadow:0 8px 24px rgba(0,0,0,.6)}
.head p{font:600 22px/1 EN,Inter,sans-serif;letter-spacing:5px;color:rgba(%(frgb)s,.8);margin:16px 0 0}
.card{position:absolute;border-radius:26px;background:linear-gradient(170deg,#191C1B,#070807 62%%,#101211);border:2px solid %(fr)s;
box-shadow:0 0 0 1px rgba(0,0,0,.6),0 0 22px rgba(%(frgb)s,.38),inset 0 1px 0 rgba(255,255,255,.12),0 24px 50px rgba(0,0,0,.65);overflow:hidden;color:#fff}
.card .t{font:400 54px/1.12 HB,SM;color:#FFFFFF}
.card .e{font:600 17px/1 EN,Inter,sans-serif;letter-spacing:3px;color:rgba(%(frgb)s,.75);margin-top:12px;text-transform:uppercase}
.card .k{font:400 104px/1 HB,SM;color:%(a)s}
.dash{position:absolute;inset:10px;border:1px solid rgba(%(frgb)s,.22);border-radius:18px;pointer-events:none}
.glow{position:absolute;inset:-3px;border-radius:27px;border:3px solid %(a)s;box-shadow:0 0 30px rgba(%(argb)s,.65);opacity:0;pointer-events:none}
.paper{position:absolute;border-radius:16px;background:linear-gradient(180deg,#FFFFFF,#EEF0EE);color:#13201A;box-shadow:0 26px 56px rgba(0,0,0,.6)}
.tag{position:absolute;padding:9px 18px;border-radius:10px;font:400 30px/1 HM,SM;color:#fff;background:linear-gradient(180deg,%(a)s,rgba(%(argb)s,.7));box-shadow:0 6px 16px rgba(0,0,0,.45);white-space:nowrap}
.badge2{position:absolute;padding:14px 26px;border-radius:16px;font:400 36px/1 HM,SM;color:#fff;background:linear-gradient(180deg,#191C1B,#070807);border:2px solid %(fr)s;box-shadow:0 0 18px rgba(%(frgb)s,.4),0 12px 26px rgba(0,0,0,.55);white-space:nowrap}
.ring{border:4px solid #FFFFFF !important;box-shadow:0 0 0 2px rgba(%(argb)s,.6),0 14px 30px rgba(0,0,0,.6)}
.numt{font:500 150px/1 NUM,EN,sans-serif;color:#FFFFFF;letter-spacing:1px;text-shadow:0 0 26px rgba(%(argb)s,.4),0 8px 24px rgba(0,0,0,.65)}
.bgbase{position:absolute;inset:0;background:radial-gradient(80%% 50%% at 50%% 30%%,#141A16,#070908 70%%)}
.motifc{color:rgba(%(argb)s,.10)}
.chip{color:%(a)s}
.hl{color:%(a)s;-webkit-text-fill-color:%(a)s;text-shadow:0 0 16px rgba(%(argb)s,.5)}
.paper .hl{color:#0F6B3C !important;-webkit-text-fill-color:#0F6B3C !important;text-shadow:none !important}
.grade{filter:saturate(.9) contrast(1.08) brightness(.9)}.gradeov{position:absolute;inset:0;pointer-events:none;background:linear-gradient(180deg,rgba(%(argb)s,.10),rgba(0,0,0,.25));mix-blend-mode:soft-light}
/* 底座 */
.dk{position:absolute;left:0;right:0;top:1576px;bottom:0;background:linear-gradient(180deg,#0E110F,#050605)}
.dkg{position:absolute;left:240px;top:1576px;width:600px;height:150px;background:radial-gradient(ellipse at 50%% 0%%,rgba(%(argb)s,.18),transparent 70%%)}
.rule{position:absolute;left:0;right:0;top:1574px;height:2px;background:linear-gradient(90deg,transparent,%(fr)s 25%%,%(fr)s 75%%,transparent);box-shadow:0 0 10px rgba(%(frgb)s,.6)}
.badge{position:absolute;left:50%%;top:1548px;transform:translateX(-50%%);height:54px;padding:0 30px;border-radius:14px;text-align:center;background:linear-gradient(180deg,#191C1B,#070807);border:2px solid %(fr)s;box-shadow:0 0 16px rgba(%(frgb)s,.45);font:400 34px/50px HM,SM;color:#fff;white-space:nowrap}
.badge b{color:%(a)s;font-weight:400}
.chap .n{font:400 26px/1 HM,SM;color:rgba(%(frgb)s,.75);letter-spacing:2px}
.chap .l{font:400 38px/1 HM,SM;color:rgba(255,255,255,.45);margin-top:8px}
.chap .on .n{color:%(a)s}.chap .on .l{color:#FFFFFF}
.chap .u{background:rgba(255,255,255,.08)}
.chap .ud{background:linear-gradient(90deg,%(a)s,%(fr)s);box-shadow:0 0 14px rgba(%(argb)s,.8)}
.upd{background:linear-gradient(180deg,#191C1B,#070807);border:2px solid %(fr)s;box-shadow:0 0 22px rgba(%(frgb)s,.35);border-radius:20px}
.upd .lab{color:%(a)s}.upd .dot{background:%(a)s;box-shadow:0 0 12px %(a)s}
.upd .ti{color:#FFFFFF;font-family:HB,SM}
.upd .st{background:rgba(255,255,255,.05);border:1px solid rgba(%(frgb)s,.35)}
.upd .sv{font-family:HB,SM;color:%(a)s}
.cap{font-family:HM,SM;text-shadow:0 2px 4px rgba(0,0,0,.9),0 0 16px rgba(0,0,0,.8),0 0 32px rgba(0,0,0,.5)}
/* 卡牌的做法（forms.py）：金线黑卡、渐变按钮、分区小标签、圆环进度、光球关键词 */
.kpcard{position:absolute;border-radius:34px;background:linear-gradient(170deg,#1A1D1C,#060706 58%%,#0F1110);border:2.5px solid %(fr)s;
box-shadow:0 0 26px rgba(%(frgb)s,.5),0 0 0 1px rgba(0,0,0,.7),inset 0 1px 0 rgba(255,255,255,.16),0 30px 60px rgba(0,0,0,.7);overflow:hidden}
.kpsw{position:absolute;left:0;top:-10%%;width:18%%;height:120%%;background:linear-gradient(90deg,transparent,rgba(255,255,240,.18),transparent);transform:skewX(-18deg);pointer-events:none}
.kporn{display:flex;align-items:center;justify-content:center;gap:8px}
.kporn i{display:block;width:70px;height:1.5px;background:linear-gradient(90deg,transparent,%(fr)s)}.kporn i.r{background:linear-gradient(270deg,transparent,%(fr)s)}
.kporn s{display:block;width:8px;height:8px;transform:rotate(45deg);background:%(fr)s}
.kpbtn{position:absolute;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:18px;color:#fff;font:400 46px/1 HB,SM;white-space:nowrap;
border:1.5px solid rgba(255,255,255,.4);box-shadow:inset 0 2px 0 rgba(255,255,255,.35),inset 0 -12px 24px rgba(0,0,0,.35),0 10px 24px rgba(0,0,0,.5)}
.kpbtn small{display:block;margin-top:8px;font:600 14px/1 EN,Inter,sans-serif;letter-spacing:3px;opacity:.75;text-transform:uppercase}
.kpbtn.off{background:linear-gradient(180deg,#1E2120,#0D0F0E);border-color:rgba(255,255,255,.12);box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
.kp0{background:linear-gradient(170deg,#36C27E,#1A6E8A)}.kp1{background:linear-gradient(170deg,#8E5CF0,#3A2C8F)}.kp2{background:linear-gradient(170deg,#E0475B,#7A1630)}
.kp3{background:linear-gradient(170deg,#3E8EF0,#1E3C8F)}.kp4{background:linear-gradient(170deg,#E9A83A,#8A4A12)}
.kpchip{position:absolute;padding:12px 22px 10px;border-radius:12px;background:linear-gradient(180deg,%(a)s,rgba(%(argb)s,.72));color:#fff;font:400 34px/1 HB,SM;white-space:nowrap;
box-shadow:0 0 18px rgba(%(argb)s,.45),0 8px 18px rgba(0,0,0,.45)}
.kpchip small{display:block;margin-top:6px;font:600 18px/1 EN,Inter,sans-serif;letter-spacing:3px;opacity:.85;text-transform:uppercase}
.kporb{position:absolute;border-radius:50%%;background:radial-gradient(circle at 50%% 42%%,rgba(%(mrgb)s,.95),rgba(%(mrgb)s,.55) 45%%,rgba(20,10,40,.92) 72%%);
box-shadow:0 0 0 3px rgba(%(mrgb)s,.6),0 0 80px rgba(%(mrgb)s,.6),inset 0 0 60px rgba(0,0,0,.5)}
"""

# ======================================================================== 4 瓷蓝
class Cilan(Style):
    key, name, en = "cilan", "瓷蓝", "Porcelain Blue"
    accents = {
        "cobalt": {"a": "#5B86FF", "argb": "91,134,255", "lt": "#A9C2FF", "navy": "#14285C", "li": "#B9A6FF", "deep": "#2F55D9"},
        "teal": {"a": "#2FB5A8", "argb": "47,181,168", "lt": "#9EE6DD", "navy": "#0F3B3A", "li": "#9FD8FF", "deep": "#1B7A71"},
        "violet": {"a": "#8B7BFF", "argb": "139,123,255", "lt": "#C9C1FF", "navy": "#26206A", "li": "#FFB3D9", "deep": "#5543D1"},
    }
    pip = {"shape": "circle", "size": 230}
    chart, quote, chapter = "paper", "block", "hud"
    signature = ["counter", "bars", "ring"]
    enter_default, card_default = "flip", "toss"
    css_tpl = """
.T1{background:linear-gradient(180deg,#FFFFFF 0%%,#EEF3FF 45%%,%(lt)s 100%%);-webkit-background-clip:text;background-clip:text;color:transparent;filter:drop-shadow(0 2px 0 rgba(10,20,50,.8)) drop-shadow(0 0 20px rgba(%(argb)s,.35));font-family:SM}
.T2{color:%(lt)s;font-family:SM;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.TR{color:#FF6B6B;font-family:SM;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.TB{color:#F4F7FF;font-family:SM;text-shadow:0 2px 0 rgba(10,20,50,.8),0 8px 24px rgba(0,0,0,.5)}
.EN{font:600 22px/1 EN,Inter,sans-serif;letter-spacing:5px;color:rgba(%(argb)s,.95);text-transform:uppercase}
.head{position:absolute;left:0;right:0;text-align:center}
.head .orn{display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:16px}
.head .orn i{display:block;width:90px;height:2px;border-radius:2px;background:rgba(%(argb)s,.8)}
.head .orn i.r{background:rgba(%(argb)s,.8)}
.head .orn s{display:block;width:10px;height:10px;border-radius:50%%;border:2px solid %(lt)s}
.head h2{font:400 84px/1.1 SM;letter-spacing:2px;color:#F4F7FF;text-shadow:0 4px 18px rgba(0,0,0,.45);margin:0}
.head p{font:600 22px/1 EN,Inter,sans-serif;letter-spacing:6px;color:%(lt)s;margin:16px 0 0;text-transform:uppercase}
.card{position:absolute;border-radius:18px;background:linear-gradient(180deg,rgba(40,62,128,.80),rgba(16,26,62,.90));border:1.5px solid rgba(170,195,255,.45);box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 22px 44px rgba(0,0,0,.45);overflow:hidden;color:#F4F7FF}
.card .t{font:400 54px/1.12 SM;color:#FFFFFF}
.card .e{font:600 17px/1 EN,Inter,sans-serif;letter-spacing:4px;color:%(lt)s;margin-top:12px;text-transform:uppercase}
.card .k{font:500 104px/1 NUM,SM;color:%(lt)s}
.dash{position:absolute;inset:9px;border:1px dashed rgba(190,210,255,.28);border-radius:12px;pointer-events:none}
.glow{position:absolute;inset:-2px;border-radius:19px;border:2px solid #CFE0FF;box-shadow:0 0 0 4px rgba(%(argb)s,.25),0 0 40px rgba(%(argb)s,.55);opacity:0;pointer-events:none}
.paper{position:absolute;border-radius:20px;background:linear-gradient(180deg,#FFFFFF,#F1EEE6);color:%(navy)s;box-shadow:0 30px 60px rgba(0,0,0,.45)}
.tag{position:absolute;padding:8px 16px;border-radius:8px;font:400 28px/1 SM;color:#FFFFFF;background:linear-gradient(180deg,%(a)s,#2F55D9);box-shadow:0 6px 16px rgba(0,0,0,.35);white-space:nowrap}
.badge2{position:absolute;padding:12px 22px;border-radius:12px;font:400 34px/1 SM;color:#FFFFFF;background:linear-gradient(180deg,rgba(40,62,128,.92),rgba(16,26,62,.95));border:1.5px solid rgba(170,195,255,.6);white-space:nowrap}
.ring{border:4px solid #FFFFFF !important;box-shadow:0 0 0 1px rgba(0,0,0,.3),0 14px 34px rgba(0,0,0,.45)}
.numt{font:500 150px/1 NUM,EN,sans-serif;color:#FFFFFF;letter-spacing:1px;text-shadow:0 0 30px rgba(%(argb)s,.55),0 6px 20px rgba(0,0,0,.45)}
.bgbase{position:absolute;inset:0;background:radial-gradient(120%% 70%% at 50%% 30%%,#2A3442,#1A212B 60%%,#12171E)}
.motifc{color:rgba(190,205,230,.07)}
.chip{color:%(lt)s}
.hud{position:absolute;border-radius:50%%;border:3px solid rgba(%(argb)s,.85);box-shadow:0 0 30px rgba(%(argb)s,.6),inset 0 0 30px rgba(%(argb)s,.35)}
.hl{color:%(li)s;-webkit-text-fill-color:%(li)s}
.paper .hl{color:%(deep)s !important;-webkit-text-fill-color:%(deep)s !important}
.grade{filter:saturate(.8) contrast(.96) brightness(1.05)}.gradeov{position:absolute;inset:0;pointer-events:none;background:rgba(110,145,255,.18);mix-blend-mode:soft-light}
/* 底座 */
.dk{position:absolute;left:0;right:0;top:1576px;bottom:0;background:linear-gradient(180deg,#18202B,#0E131A)}
.dkg{position:absolute;left:290px;top:1576px;width:500px;height:150px;background:radial-gradient(ellipse at 50%% 0%%,rgba(%(argb)s,.22),transparent 70%%)}
.rule{position:absolute;left:0;right:0;top:1574px;height:2px;background:linear-gradient(90deg,transparent,rgba(200,215,255,.9) 30%%,rgba(200,215,255,.9) 70%%,transparent)}
.badge{position:absolute;left:50%%;top:1548px;transform:translateX(-50%%);height:54px;padding:0 30px;border-radius:12px;text-align:center;background:linear-gradient(180deg,#FFFFFF,#E8E3D8);box-shadow:0 6px 18px rgba(0,0,0,.45);font:400 36px/54px SM;color:%(navy)s;white-space:nowrap}
.badge b{color:%(deep)s;font-weight:400}
.chap .n{font:500 26px/1 NUM,SM;color:%(a)s;letter-spacing:2px}
.chap .l{font:400 40px/1 SM;color:rgba(255,255,255,.34);margin-top:8px}
.chap .on .n{color:%(lt)s}.chap .on .l{color:#FFFFFF}
.chap .u{background:rgba(255,255,255,.08)}
.chap .ud{background:linear-gradient(90deg,%(a)s,#CFE0FF);box-shadow:0 0 14px rgba(%(argb)s,.85)}
.upd{background:linear-gradient(180deg,rgba(40,62,128,.92),rgba(16,26,62,.96));border:1.5px solid rgba(170,195,255,.6);box-shadow:0 0 30px rgba(%(argb)s,.25);border-radius:18px}
.upd .lab{color:%(lt)s}.upd .dot{background:#FF6B6B;box-shadow:0 0 12px #FF6B6B}
.upd .ti{color:#FFFFFF;font-family:SM}
.upd .st{background:rgba(255,255,255,.06);border:1px solid rgba(170,195,255,.3)}
.upd .sv{font-family:NUM,SM;color:#FFFFFF}
.cap{text-shadow:0 2px 4px rgba(5,10,25,.85),0 0 14px rgba(5,10,25,.75),0 0 30px rgba(5,10,25,.45)}
"""



# ======================================================================== 5 清单（取自免税那条参考：讲规则、条件和选择）
class Qingdan(Style):
    key, name, en = "qingdan", "清单", "Checklist"
    accents = {
        "jade": {"a": "#3BB273", "argb": "59,178,115", "m": "#C8323C", "mrgb": "200,50,60", "pa": "#2B2E7A", "pb": "#1F6B4A", "navy": "#1F3D2E"},
        "violet": {"a": "#8E6BFF", "argb": "142,107,255", "m": "#E0475B", "mrgb": "224,71,91", "pa": "#3A2370", "pb": "#1F4F6B", "navy": "#2A2160"},
        "blue": {"a": "#4C8DFF", "argb": "76,141,255", "m": "#F5A524", "mrgb": "245,165,36", "pa": "#1E3A7A", "pb": "#6B3A1F", "navy": "#1A2E5C"},
    }
    pip = {"shape": "circle", "size": 180}
    chart, quote, chapter = "paper", "block", "orn"
    signature = ["chain", "compare", "quote"]
    enter_default, card_default = "rise", "pop"
    css_tpl = """
.T1{color:#FFFFFF;font-family:HB,SM;text-shadow:0 2px 0 rgba(0,0,0,.5),0 10px 26px rgba(0,0,0,.55)}
.T2{color:%(a)s;font-family:HB,SM;text-shadow:0 6px 18px rgba(0,0,0,.55)}
.TR{color:#E0333F;font-family:HB,SM;text-shadow:0 6px 18px rgba(0,0,0,.45)}
.TB{color:#FFFFFF;font-family:HB,SM;text-shadow:0 10px 28px rgba(0,0,0,.6)}
.EN{font:500 22px/1 EN,Inter,sans-serif;letter-spacing:4px;color:rgba(255,255,255,.62)}
.head{position:absolute;left:0;right:0;text-align:center}
.head .orn{display:none}
.head h2{font:400 80px/1.1 HB,SM;letter-spacing:2px;color:#fff;margin:0;text-shadow:0 8px 24px rgba(0,0,0,.6)}
.head p{font:500 22px/1 EN,Inter,sans-serif;letter-spacing:5px;color:rgba(255,255,255,.6);margin:14px 0 0}
.card{position:absolute;border-radius:20px;background:linear-gradient(180deg,rgba(32,32,40,.94),rgba(14,14,18,.96));border:2px solid rgba(255,255,255,.26);
box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 22px 46px rgba(0,0,0,.6);overflow:hidden;color:#fff}
.card .t{font:400 52px/1.12 HB,SM;color:#FFFFFF}
.card .e{font:500 16px/1 EN,Inter,sans-serif;letter-spacing:3px;color:rgba(255,255,255,.6);margin-top:12px}
.card .k{font:400 100px/1 HB,SM;color:%(a)s}
.dash{position:absolute;inset:9px;border:1px solid rgba(255,255,255,.08);border-radius:13px;pointer-events:none}
.glow{position:absolute;inset:-3px;border-radius:21px;border:3px solid %(a)s;box-shadow:0 0 26px rgba(%(argb)s,.6);opacity:0;pointer-events:none}
.paper{position:absolute;border-radius:8px;background:#F2ECE0;color:#191512;box-shadow:0 24px 50px rgba(0,0,0,.55)}
.tag{position:absolute;padding:9px 18px;border-radius:999px;font:400 30px/1 HM,SM;color:#fff;background:%(a)s;box-shadow:0 6px 16px rgba(0,0,0,.45);white-space:nowrap}
.badge2{position:absolute;padding:14px 24px;border-radius:14px;font:400 36px/1 HM,SM;color:#fff;background:rgba(20,20,26,.92);border:2px solid rgba(255,255,255,.3);box-shadow:0 12px 26px rgba(0,0,0,.55);white-space:nowrap}
.ring{border:4px solid #FFFFFF !important;box-shadow:0 14px 30px rgba(0,0,0,.6)}
.numt{font:500 150px/1 NUM,EN,sans-serif;color:#FFFFFF;letter-spacing:1px;text-shadow:0 8px 24px rgba(0,0,0,.6)}
.bgbase{position:absolute;inset:0;background:#09090B}
.motifc{color:rgba(255,255,255,.05)}
.chip{color:%(a)s}
.hl{color:%(a)s;-webkit-text-fill-color:%(a)s}
.paper .hl{color:#14603A !important;-webkit-text-fill-color:#14603A !important;text-shadow:none !important}
.grade{filter:saturate(.92) contrast(1.06) brightness(.88)}.gradeov{position:absolute;inset:0;pointer-events:none;background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.3))}
/* 底座 */
.dk{position:absolute;left:0;right:0;top:1576px;bottom:0;background:linear-gradient(180deg,#0E0E12,#050507)}
.dkg{position:absolute;left:240px;top:1576px;width:600px;height:150px;background:radial-gradient(ellipse at 50%% 0%%,rgba(%(argb)s,.14),transparent 70%%)}
.rule{position:absolute;left:0;right:0;top:1574px;height:2px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.7) 25%%,rgba(255,255,255,.7) 75%%,transparent)}
.badge{position:absolute;left:50%%;top:1548px;transform:translateX(-50%%);height:54px;padding:0 30px;border-radius:12px;text-align:center;background:#F2ECE0;border:2px solid rgba(0,0,0,.4);box-shadow:0 6px 18px rgba(0,0,0,.5);font:400 34px/50px HM,SM;color:#191512;white-space:nowrap}
.badge b{color:%(m)s;font-weight:400}
.chap .n{font:400 26px/1 HM,SM;color:rgba(255,255,255,.62);letter-spacing:2px}
.chap .l{font:400 38px/1 HM,SM;color:rgba(255,255,255,.45);margin-top:8px}
.chap .on .n{color:%(a)s}.chap .on .l{color:#FFFFFF}
.chap .u{background:rgba(255,255,255,.08)}
.chap .ud{background:%(a)s;box-shadow:0 0 12px rgba(%(argb)s,.7)}
.upd{background:rgba(20,20,26,.95);border:2px solid rgba(255,255,255,.28);border-radius:18px}
.upd .lab{color:%(a)s}.upd .dot{background:%(m)s;box-shadow:0 0 12px %(m)s}
.upd .ti{color:#FFFFFF;font-family:HB,SM}
.upd .st{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.18)}
.upd .sv{font-family:HB,SM;color:%(a)s}
.cap{font-family:HM,SM;text-shadow:0 2px 4px rgba(0,0,0,.9),0 0 16px rgba(0,0,0,.8),0 0 32px rgba(0,0,0,.5)}
/* 清单的做法（forms.py）：对照表（打问号、逐格打勾）、气泡、左右两色柱、波普半调、光环标题 */
.qddots{position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.07) 1.2px,transparent 1.6px);background-size:26px 26px}
.qdpanel{position:absolute;border-radius:24px;background:linear-gradient(180deg,rgba(28,28,34,.96),rgba(12,12,16,.97));border:2.5px solid rgba(255,255,255,.3);
box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 30px 60px rgba(0,0,0,.65);overflow:hidden}
.qdhead{position:absolute;left:0;right:0;top:0;display:flex;align-items:flex-end;padding-bottom:14px;border-bottom:1.5px solid rgba(255,255,255,.12)}
.qdhead div{flex:1;text-align:center;font:400 38px/1 HB,SM;color:#fff}.qdhead small{display:block;margin-top:6px;font:500 13px/1 EN,Inter;letter-spacing:2px;color:rgba(255,255,255,.55)}
.qdrow{position:absolute;left:14px;right:14px;border-radius:16px;overflow:hidden;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)}
.qdlab{position:absolute;left:0;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center;padding-left:26px;font:400 44px/1.1 HB,SM;color:#fff;white-space:nowrap}
.qdlab small{display:block;margin-top:8px;font:500 15px/1 EN,Inter;letter-spacing:2px;color:rgba(255,255,255,.62)}
.qdr0{background:linear-gradient(90deg,#2E6B5E,#1C4A40)}.qdr1{background:linear-gradient(90deg,#4B2E6B,#33204A)}.qdr2{background:linear-gradient(90deg,#2C3E6B,#1D2A4A)}
.qdr3{background:linear-gradient(90deg,#7A2E5E,#521F40)}.qdr4{background:linear-gradient(90deg,#6B5A2E,#4A3E1F)}
.qdq{position:absolute;width:64px;height:64px;border-radius:50%%;display:flex;align-items:center;justify-content:center;font:400 34px/1 HB,SM;color:rgba(255,255,255,.4);border:2px solid rgba(255,255,255,.16);background:rgba(255,255,255,.04)}
.qdok{position:absolute;width:72px;height:72px;border-radius:50%%;display:flex;align-items:center;justify-content:center;font:400 38px/1 HB,SM;color:#fff;
background:radial-gradient(circle at 38%% 30%%,#7BE3A4,%(a)s 55%%,#1E7A4A);border:3px solid rgba(255,255,255,.75);box-shadow:0 0 18px rgba(%(argb)s,.7),0 6px 14px rgba(0,0,0,.45)}
.qdred{position:absolute;left:14px;right:14px;height:70px;border-radius:12px;background:linear-gradient(90deg,%(m)s,rgba(%(mrgb)s,.75));display:flex;align-items:center;justify-content:center;gap:16px;font:400 40px/1 HB,SM;color:#fff;white-space:nowrap}
.qdbub{position:absolute;border-radius:50%%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#fff;font:400 44px/1.1 HB,SM;
border:2px solid rgba(255,255,255,.38);box-shadow:inset 0 0 40px rgba(255,255,255,.12),0 16px 34px rgba(0,0,0,.45);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
.qdbub small{display:block;margin-top:8px;font:500 14px/1 EN,Inter;letter-spacing:2px;opacity:.7}
.qdpop{position:absolute;background:#EFE6D6;background-image:radial-gradient(rgba(0,0,0,.10) 1.4px,transparent 1.8px);background-size:9px 9px}
.qdring{position:absolute;border-radius:50%%;border:3px solid rgba(%(argb)s,.85);box-shadow:0 0 22px rgba(%(argb)s,.7),inset 0 0 22px rgba(%(argb)s,.35)}
"""


STYLES = {s.key: s for s in (Tanjin, Dangan, Kapai, Cilan, Qingdan)}
NAMES = {s.name: s.key for s in (Tanjin, Dangan, Kapai, Cilan, Qingdan)}


def get(key, accent=None):
    key = NAMES.get(key, key)
    if key not in STYLES:
        raise KeyError(f"没有风格 {key}，可选：{', '.join(f'{k}（{v.name}）' for k, v in STYLES.items())}")
    return STYLES[key](accent)


def brush_in(st, sel, t, dur=0.7):
    """书法大字入场：从左往右写出来（各风格通用）。"""
    return (f'tl.fromTo("{sel}",{{opacity:1,clipPath:"inset(-20% 100% -20% 0%)"}},'
            f'{{opacity:1,clipPath:"inset(-20% 0% -20% 0%)",duration:{dur},ease:"power2.out"}},{t:.3f});\n')
