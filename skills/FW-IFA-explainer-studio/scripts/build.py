# -*- coding: utf-8 -*-
"""分镜表 plan.json → OpenMotion（HyperFrames）工程源码：index.html＋compositions/*.html。

用法：python build.py plan.json --assets assets.json --geom geom.json --out 输出目录 [--strict] [--register]
  plan.json 写法见 references/03-分镜表.md；captions、cuts 两个文件路径写在 plan 里（相对 plan 所在目录）。
构建时自动查三件事（写进 输出目录/build_report.json）：
  1. 碰脸：人物段里任何元素和头部范围（头顶到下巴、脸宽外扩 5%，按跳切推近后的位置）有重叠 → 报错，不出工程
  2. 差异：同一版式连用、超次数、没用本风格招牌版式、图解版式种类太少 → 警告（--strict 时当错误）
  3. 账号登记：--register 时把本片的风格、版式序列记进 data/registry.json，下一支同账号的片子会被提醒避开同样的开场和收尾
"""
import argparse, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))

from tujie.core import Film, BuildError  # noqa: E402
from tujie import frame  # noqa: E402
from tujie.layouts_host import HOST_LAYOUTS, head_box  # noqa: E402
from tujie.layouts_graphic import GRAPHIC_LAYOUTS  # noqa: E402

LIMITS = {"band": 4, "quote": 3, "chapter": 4, "ending": 1}
DEFAULT_LIMIT = 2
PARA_KEYS = ("tone", "energy", "enter", "card_enter", "reveal")
BAD_WORDS = ("风险", "亏", "跌", "泡沫", "危机", "破产", "陷阱", "损失", "警惕", "暴雷", "爆雷", "贵", "坑", "崩", "代价")
GOOD_WORDS = ("增长", "涨", "赚", "收益", "机会", "利好", "回报", "翻倍", "红利", "上升")
HEADLINE_FIELDS = ("word", "big1", "big2", "zh", "text")


def texts(v, keys=None):
    out = []
    if isinstance(v, str):
        out.append(v)
    elif isinstance(v, dict):
        for k, x in v.items():
            if keys is None or k in keys or isinstance(x, (dict, list)):
                out += texts(x, keys)
    elif isinstance(v, list):
        for x in v:
            out += texts(x, keys)
    return out


TIME_KEYS = {"t", "t1", "t2", "tl", "tr", "push", "hi_t", "bars_t", "q_t", "line_t", "t_a", "t_b", "t_end", "t_hi", "all_on", "all_t", "out"}


def resolve_times(film):
    """把分镜表里写成「@关键词」「@关键词+0.3」的时间，换成这个词被说出来的秒数（在本段时间里找）。"""
    import re
    errs = []

    def conv(v, t0, t1, where):
        m = re.match(r"^@(.+?)([+-]\d+(?:\.\d+)?)?$", v.strip())
        if not m:
            errs.append(f"{where}：时间「{v}」写法不对，应该是 @关键词 或 @关键词+0.3")
            return t0
        hit = film.speech_find(m.group(1), t0, t1)
        if not hit:
            errs.append(f"{where}：在 {t0:.1f}–{t1:.1f} 秒的原声里找不到「{m.group(1)}」（换一个本人原话里的词，或直接写秒数）")
            return t0
        return round(hit[0] + float(m.group(2) or 0), 3)

    def walk(obj, t0, t1, where):
        if isinstance(obj, dict):
            for k, v in list(obj.items()):
                if isinstance(v, str) and v.startswith("@") and k in TIME_KEYS:
                    obj[k] = conv(v, t0, t1, f"{where}.{k}")
                elif k == "tiles_t" and isinstance(v, list):
                    obj[k] = [conv(x, t0, t1, f"{where}.tiles_t") if isinstance(x, str) and x.startswith("@") else x for x in v]
                else:
                    walk(v, t0, t1, where)
        elif isinstance(obj, list):
            for x in obj:
                walk(x, t0, t1, where)
    for s in film.segs:
        walk(s.data, s.start, s.end, s.id)
    for u in film.plan.get("updates", []):
        for k in ("start", "end"):
            if isinstance(u.get(k), str):
                u[k] = conv(u[k], 0, film.dur, f"updates.{k}")
    for ch in film.plan.get("chapters", []):
        if isinstance(ch[0], str):
            ch[0] = conv(ch[0], 0, film.dur, "chapters")
    return errs


def auto_params(seg, state):
    """分镜表没写段落层参数时，按这一段的文字自动推断，让同风格的片子各段表现不一样。写了的参数优先。
    克制：只动图解段；「有力＋放大冲击」全片最多 2 次、不相邻，否则会变成新的千篇一律。"""
    d = seg.data
    got = []
    state["idx"] += 1
    if seg.kind != "graphic":
        return got
    heads = " ".join(texts(d, HEADLINE_FIELDS + ("title", "lines", "spans", "intro")))
    if ("energy" not in d and "enter" not in d and ("？" in heads or "?" in heads)
            and state["punch"] < 2 and state["idx"] - state["last"] >= 3 and seg.layout not in ("chapter", "ending")):
        d["energy"], d["enter"] = "punch", "zoom"
        state["punch"] += 1
        state["last"] = state["idx"]
        got.append("问句→有力＋放大冲击")
    if "tone" not in d:
        ts = texts(d)
        bad = any(w in t for t in ts for w in BAD_WORDS)
        good = any(w in t for t in ts if "？" not in t and "?" not in t for w in GOOD_WORDS)
        if bad != good:
            d["tone"] = "bad" if bad else "good"
            got.append(f"{'风险词→红' if bad else '增长词→绿'}")
    if "reveal" not in d and seg.layout in ("quote", "ending"):
        big = d.get("big1", "") + d.get("big2", "")
        if big and len(big.replace("*", "")) <= 12:
            d["reveal"] = "chars"
            got.append("短金句→逐字展开")
    if seg.layout == "chapter" and "energy" not in d:
        d["energy"] = "calm"
        got.append("章节卡→平静")
    return got


def overlap(a, b):
    x = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    y = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    return x * y


def variety(film):
    warns = []
    gs = [s for s in film.segs if s.kind == "graphic"]
    for a, b in zip(gs, gs[1:]):
        if a.layout == b.layout and a.layout != "band":
            warns.append(f"图解版式连用：{a.id}、{b.id} 都是 {a.layout}")
    cnt = Counter(s.layout for s in gs)
    for k, n in cnt.items():
        if n > LIMITS.get(k, DEFAULT_LIMIT):
            warns.append(f"{k} 用了 {n} 次（上限 {LIMITS.get(k, DEFAULT_LIMIT)}）")
    seen = {}
    for s_ in gs:
        key = (s_.layout,) + tuple(s_.data.get(k) for k in PARA_KEYS)
        if key in seen:
            warns.append(f"{seen[key]} 和 {s_.id} 版式相同、段落层参数也相同，动起来会一模一样：换入场、色调或节奏")
        seen.setdefault(key, s_.id)
    sig = set(film.st.signature)
    if gs and not sig & set(cnt):
        warns.append(f"没用本风格（{film.st.name}）的招牌版式：{'、'.join(sorted(sig))}")
    if film.dur > 90 and len(cnt) < 5:
        warns.append(f"图解版式只有 {len(cnt)} 种，90 秒以上的片子至少 5 种")
    hs = Counter(s.layout for s in film.segs if s.kind == "host")
    if hs.get("side_tags", 0) > 2:
        warns.append("两侧对立标签超过 2 处：只用在真正对立的地方")
    return warns


def registry_check(film, reg):
    acc = film.plan.get("account")
    if not acc or acc not in reg:
        return []
    last = [r for r in reg[acc] if r.get("title") != film.title][-3:]  # 同一支片子重剪、重导不算重复
    w = []
    gs = [s.layout for s in film.segs if s.kind == "graphic"]
    for r in last:
        if r.get("style") == film.st.key and gs[:2] == r.get("graphic", [])[:2]:
            w.append(f"和同账号《{r['title']}》开场两段版式一样（{gs[:2]}），换一个")
        if r.get("style") == film.st.key and gs[-1:] == r.get("graphic", [])[-1:] and r.get("accent") == film.st.acc_key:
            w.append(f"和同账号《{r['title']}》收尾版式、强调色都一样，换强调色或收尾做法")
        if r.get("motif") == film.motif and r.get("style") == film.st.key:
            w.append(f"和同账号《{r['title']}》母题图标一样，按本片内容重选")
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("--assets", required=True); ap.add_argument("--geom", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--strict", action="store_true"); ap.add_argument("--register", action="store_true")
    a = ap.parse_args()
    pdir = os.path.dirname(os.path.abspath(a.plan))
    plan = json.load(open(a.plan, encoding="utf-8"))
    rel = lambda p: p if os.path.isabs(p) else os.path.join(pdir, p)
    plan["_captions"] = json.load(open(rel(plan["captions"]), encoding="utf-8")) if plan.get("captions") else []
    plan["_cuts"] = json.load(open(rel(plan["cuts"]), encoding="utf-8")) if plan.get("cuts") else []
    # 重说接点（prep.py cut 写的 joins.json，和 cuts.json 在一起）：离镜头边界 0.3 秒以内，就把镜头边界挪到接点上，
    # 让镜头切换本身遮住接点；不然切换后两三帧画面又跳一下，看起来就是「卡了一下」。
    # 落在人物段中间的接点不用管：跳切推近会在接点换一次景别（1.0／1.08），这是口播剪辑遮接点的常规做法
    jp = os.path.join(os.path.dirname(rel(plan["cuts"])), "joins.json") if plan.get("cuts") else ""
    joins = json.load(open(jp)) if jp and os.path.exists(jp) else []
    segs = plan["segments"]
    for t in [j["t"] for j in joins if j.get("kind") == "retake"]:
        for k in range(1, len(segs)):
            edge = segs[k]["start"]
            if isinstance(edge, (int, float)) and 0 < abs(edge - t) <= 0.3:
                segs[k]["start"] = segs[k - 1]["end"] = round(t, 3)
    plan["_chartimes"] = json.load(open(rel(plan["chartimes"]), encoding="utf-8")) if plan.get("chartimes") and os.path.exists(rel(plan["chartimes"])) else []
    assets = json.load(open(a.assets, encoding="utf-8"))
    geom = json.load(open(a.geom, encoding="utf-8"))
    film = Film(plan, assets, geom, a.out)
    film.st.bind(film)
    errors = resolve_times(film)
    auto_log = {}
    explicit = sum(1 for s in film.segs if s.kind == "graphic" and (any(k in s.data for k in PARA_KEYS) or "*" in json.dumps(s.data, ensure_ascii=False)))
    if not plan.get("no_auto"):
        state = {"punch": 0, "last": -9, "idx": -1}
        for s in film.segs:
            got = auto_params(s, state)
            if got:
                auto_log[s.id] = got
    for s in film.segs:
        film.prepare(s)
        fn = (HOST_LAYOUTS if s.kind == "host" else GRAPHIC_LAYOUTS).get(s.layout)
        if not fn:
            errors.append(f"{s.id}：没有版式 {s.layout}（人物段可用 {', '.join(HOST_LAYOUTS)}；图解段可用 {', '.join(GRAPHIC_LAYOUTS)}）")
            continue
        try:
            fn(film, s)
        except BuildError as e:
            errors.append(f"{s.id}：{e}")
        except KeyError as e:
            errors.append(f"{s.id}（{s.layout}）：data 缺字段 {e}")
        if s.kind == "graphic":
            film.sfx.append((max(0, s.start - 0.12), "soft", None))
    film.prepare(None)
    # 碰脸检查
    seg_by = {s.id: s for s in film.segs}
    face_hits = []
    for sid, name, rect, s0, s1, zoom in film.zones:
        hb = head_box(film, seg_by[sid])
        ov = overlap(rect, hb)
        if ov > 0:
            face_hits.append(f"{sid}.{name} 和头部范围重叠 {ov:.0f}px²（元素 {rect}，头部 {[round(v) for v in hb]}）")
    errors += face_hits
    frame.dock(film)
    frame.captions(film)
    order = [("dock", 0, film.dur, 2, 5, "graphics")]
    for k, s in enumerate(film.segs):
        if s.kind == "host":
            order.append((s.id, s.start, s.end, 3 + k % 2, 3, "graphics"))
        else:
            order.append((s.id, s.start, s.end, 6 + k % 3, 4, "graphics"))
    order.append(("captions", 0, film.dur, 9, 6, "captions"))
    frame.index(film, order)
    warns = variety(film)
    ng = sum(1 for s in film.segs if s.kind == "graphic")
    if ng and explicit < ng / 2:
        warns.append(f"只有 {explicit}/{ng} 个图解段在分镜表里按内容设了段落层参数（tone／energy／enter／card_enter／reveal／*重点词*），"
                     "其余靠自动推断；按 references/02 的「内容 → 调法」表逐段补上")
    reg_p = os.path.join(ROOT, "data", "registry.json")
    reg = json.load(open(reg_p, encoding="utf-8")) if os.path.exists(reg_p) else {}
    warns += registry_check(film, reg)
    if geom.get("estimated_head_top"):
        warns.append("人物测量用的是 OpenCV 兜底，头顶是估算值；有条件请装 mediapipe 重测")
    report = {"title": film.title, "style": film.st.key, "accent": film.st.acc_key, "segments": [(s.id, s.kind, s.layout, s.start, s.end) for s in film.segs],
              "errors": errors, "warnings": warns, "auto_params": auto_log, "sfx": len(film.sfx), "zones": len(film.zones)}
    json.dump(report, open(os.path.join(a.out, "build_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for sid, got in auto_log.items():
        print(f"·  {sid} 自动按内容调整：{'、'.join(got)}")
    for w in warns:
        print("⚠️ ", w)
    for e in errors:
        print("✗ ", e)
    if errors or (a.strict and warns):
        sys.exit(f"构建未通过：{len(errors)} 个错误、{len(warns)} 个警告（见 {a.out}/build_report.json）")
    if a.register and plan.get("account"):
        reg[plan["account"]] = [r for r in reg.get(plan["account"], []) if r.get("title") != film.title]  # 同名片子只留最新一版
        reg[plan["account"]].append({"title": film.title, "style": film.st.key, "accent": film.st.acc_key, "motif": film.motif,
                                                     "graphic": [s.layout for s in film.segs if s.kind == "graphic"]})
        json.dump(reg, open(reg_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(os.listdir(os.path.join(a.out, "compositions")))
    print(f"✓ {film.st.name}·{film.st.acc_key}：{len(film.segs)} 段、{n} 个合成、{len(film.sfx)} 个音效、{len(film.zones)} 个人物区元素已过碰脸检查")


if __name__ == "__main__":
    main()
