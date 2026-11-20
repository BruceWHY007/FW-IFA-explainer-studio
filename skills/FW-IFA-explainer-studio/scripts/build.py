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
    last = reg[acc][-3:]
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
    assets = json.load(open(a.assets, encoding="utf-8"))
    geom = json.load(open(a.geom, encoding="utf-8"))
    film = Film(plan, assets, geom, a.out)
    film.st.bind(film)
    errors = []
    for s in film.segs:
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
    reg_p = os.path.join(ROOT, "data", "registry.json")
    reg = json.load(open(reg_p, encoding="utf-8")) if os.path.exists(reg_p) else {}
    warns += registry_check(film, reg)
    if geom.get("estimated_head_top"):
        warns.append("人物测量用的是 OpenCV 兜底，头顶是估算值；有条件请装 mediapipe 重测")
    report = {"title": film.title, "style": film.st.key, "accent": film.st.acc_key, "segments": [(s.id, s.kind, s.layout, s.start, s.end) for s in film.segs],
              "errors": errors, "warnings": warns, "sfx": len(film.sfx), "zones": len(film.zones)}
    json.dump(report, open(os.path.join(a.out, "build_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for w in warns:
        print("⚠️ ", w)
    for e in errors:
        print("✗ ", e)
    if errors or (a.strict and warns):
        sys.exit(f"构建未通过：{len(errors)} 个错误、{len(warns)} 个警告（见 {a.out}/build_report.json）")
    if a.register and plan.get("account"):
        reg.setdefault(plan["account"], []).append({"title": film.title, "style": film.st.key, "accent": film.st.acc_key, "motif": film.motif,
                                                     "graphic": [s.layout for s in film.segs if s.kind == "graphic"]})
        json.dump(reg, open(reg_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n = len(os.listdir(os.path.join(a.out, "compositions")))
    print(f"✓ {film.st.name}·{film.st.acc_key}：{len(film.segs)} 段、{n} 个合成、{len(film.sfx)} 个音效、{len(film.zones)} 个人物区元素已过碰脸检查")


if __name__ == "__main__":
    main()
