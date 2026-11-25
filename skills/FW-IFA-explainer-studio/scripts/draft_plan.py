# -*- coding: utf-8 -*-
"""从字幕自动出分镜表草稿：按停顿和句子分段，判断每段在讲什么（数字／列举／对比／问句／自我介绍／结论），
按风格和差异规则建议版式和段落层参数，时间尽量写成「@关键词」（跟着本人说话走）。Agent 再逐段改。

用法：python draft_plan.py --captions captions.json --style tanjin --title "片名" --host 主讲人 --badge 名,后缀 --out plan_draft.json
      [--geom geom.json] [--chartimes chartimes.json] [--cuts cuts.json] [--duration 145.4] [--aroll-duration 144.4] [--account 账号]
给了 --geom 就按人物实际位置避开放不下的版式：头顶不够不出头顶标题（开场改身前卡片），脸两侧不够不出对立标签。
草稿里所有 B-roll、配图、英文副题、章节名都标了 TODO，素材键是 band_TODO_1 这样的占位：不改 build 会直接报错，避免带着占位出片。
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, HERE)
from tujie import styles  # noqa: E402
from build import BAD_WORDS, GOOD_WORDS, LIMITS, DEFAULT_LIMIT  # noqa: E402
from icons import ZH  # noqa: E402
from tujie import room  # noqa: E402

NUM = re.compile(r"(\d+(?:\.\d+)?\s*(?:%|万|亿|千|百|倍|年|元|块|美元|个)?)")
LIST_W = ("第一", "第二", "第三", "首先", "其次", "然后", "最后", "另外", "还有", "一是", "二是")
CONTRAST_W = ("但是", "不过", "而是", "反而", "可是", "然而", "但 ", "还是")
Q_W = ("？", "?", "吗", "为什么", "怎么", "是不是", "到底", "凭什么", "呢")
PERSON_W = ("我是", "我叫", "作为一个", "作为一名", "创始人", "董事长")
CONCL_W = ("说白了", "其实", "关键", "本质", "记住", "所以", "总之", "最后")


def clip(s, n):
    s = s.strip()
    out, w = "", 0
    for ch in s:
        w += 0.55 if re.match(r"[A-Za-z0-9 ]", ch) else 1
        if w > n:
            break
        out += ch
    return out.strip()


def phrases(text):
    return [p for p in re.split(r"[\s，。？！、；,.?!;]+", text) if p]


def classify(text, k, n):
    if k == 0:
        return "open"
    if k == n - 1:
        return "end"
    if any(w in text for w in PERSON_W):
        return "person"
    if NUM.search(text) and re.search(r"\d", text):
        return "number"
    ph = phrases(text)
    if any(w in text for w in LIST_W) or len([p for p in ph if len(p) <= 6]) >= 3:
        return "list"
    if any(w in text for w in CONTRAST_W):
        return "contrast"
    if any(w in text for w in Q_W):
        return "question"
    if k >= n * 0.85 or any(text.startswith(w) for w in CONCL_W):
        return "conclusion"
    return "talk"


CANDS = {  # 每类内容可用的版式（人物段, 图解段）
    "number": (["counter"], ["bignum", "compare", "bars"]),
    "list": (["chest_cards"], ["chain", "cascade", "grid4", "product_row", "pip_cards"]),
    "contrast": (["side_tags", "chest_cards"], ["compare"]),
    "question": (["title_top", "sticker"], ["quote", "chapter"]),
    "person": (["namecard"], []),
    "conclusion": (["sticker"], ["quote"]),
    "talk": (["plain", "chest_cards"], ["band", "bigword_band", "doc", "tilt_chart"]),
}
CARD_ENTERS = ["toss", "drop", "rise", "swing", "pop", "slide"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captions", required=True); ap.add_argument("--style", required=True); ap.add_argument("--title", required=True)
    ap.add_argument("--host", default="主讲人"); ap.add_argument("--badge", default=""); ap.add_argument("--account", default="")
    ap.add_argument("--chartimes"); ap.add_argument("--cuts"); ap.add_argument("--duration", type=float); ap.add_argument("--aroll-duration", type=float)
    ap.add_argument("--out", required=True)
    ap.add_argument("--geom", help="measure.py 的 geom.json：按人物位置避开放不下的头顶标题、对立标签")
    ap.add_argument("--fill-placeholders", help="自检用：把 TODO 素材键换成现成的键，如 band=band_demo,thumb=thumb_demo1,tile=band_demo")
    a = ap.parse_args()
    st = styles.get(a.style)
    G = room.Geo(json.load(open(a.geom, encoding="utf-8"))) if a.geom else None

    def fits(lay, t0, t1):
        if G is None:
            return True
        if lay == "title_top":
            return room.title_ok(G, t0, t1)
        if lay == "side_tags":
            return room.side_ok(G, t0, t1)
        return True
    caps = json.load(open(a.captions, encoding="utf-8"))
    dur = a.duration or round(caps[-1]["end"] + 1.4, 2)
    adur = a.aroll_duration or round(caps[-1]["end"] + 0.3, 2)
    # 1 分段：攒够 3.2 秒并遇到停顿或句末就切，超过 7 秒强制切
    beats, cur = [], []
    for i, c in enumerate(caps):
        cur.append(c)
        span = cur[-1]["end"] - cur[0]["start"]
        gap = (caps[i + 1]["start"] - c["end"]) if i + 1 < len(caps) else 9
        if (span >= 3.2 and (gap >= 0.25 or re.search(r"[？?！!。]$", c["text"]))) or span >= 7:
            beats.append(cur); cur = []
    if cur:
        if beats and cur[-1]["end"] - cur[0]["start"] < 2:
            beats[-1] += cur
        else:
            beats.append(cur)
    n = len(beats)
    starts = [0.0] + [round(b[0]["start"] - 0.05, 3) for b in beats[1:]]
    ends = starts[1:] + [dur]
    texts = [" ".join(c["text"] for c in b) for b in beats]
    kinds = [classify(t, k, n) for k, t in enumerate(texts)]
    # 2 定人物段／图解段：开场人物、结尾图解，中间交替，不连续 3 段同类
    segs, used, todo = [], {}, []
    punch, side, g_run, h_run, ce_k, tcount = 0, 0, 0, 0, 0, {"band": 0, "thumb": 0, "tile": 0}

    def key(kind):
        tcount[kind] += 1
        return f"{kind}_TODO_{tcount[kind]}"

    def last_graphic():
        for sg in reversed(segs):
            if sg["kind"] == "graphic":
                return sg["layout"]
        return None

    def pick(cands, kindname):
        sig = [c for c in cands if c in st.signature]
        lg = last_graphic()
        for c in sig + [c for c in cands if c not in sig]:
            if used.get(c, 0) < LIMITS.get(c, DEFAULT_LIMIT) and (c != lg or c == "band"):
                return c
        return None

    for k, (t, cls) in enumerate(zip(texts, kinds)):
        s0, s1 = starts[k], ends[k]
        ph = phrases(t) or [t]
        if cls == "open":
            kind, lay = "host", "title_top"
            if not fits("title_top", s0, s1):
                lay = "chest_cards"
                todo.append(f"h{k + 1:02d}：头顶只有 {room.title_avail(G, s0, s1):.0f}px，放不下标题，开场改用身前卡片")
        elif cls == "end":
            kind, lay = "graphic", "ending"
        else:
            hc, gc = CANDS[cls]
            want_g = cls in ("list", "number") or (h_run >= 2) or (cls == "talk" and segs and segs[-1]["kind"] == "host")
            if g_run >= 2 and hc:
                want_g = False
            if cls == "contrast" and side < 2 and not want_g and fits("side_tags", s0, s1):
                lay = "side_tags"; kind = "host"; side += 1
            else:
                lay = pick(gc, cls) if (want_g and gc) else None
                kind = "graphic" if lay else "host"
                if not lay:
                    lay = pick([c for c in hc if (c != "side_tags" or side < 2) and fits(c, s0, s1)], cls) or "plain"
        used[lay] = used.get(lay, 0) + 1
        g_run = g_run + 1 if kind == "graphic" else 0
        h_run = h_run + 1 if kind == "host" else 0
        d = {}
        first = clip(ph[0], 10)
        last = clip(ph[-1], 10)
        if lay == "title_top":
            # 头顶只放一行核心信息（话题＋数字）；后半句、问句交给字幕
            d = {"lines": [{"text": clip(t.split(" ")[0] if cls == "open" else first, 12), "cls": "T1", "t": round(s0 + 0.1, 2)}]}
        elif lay == "plain":
            d = {}
        elif lay == "side_tags":
            parts = re.split(r"但是|不过|而是|反而|可是|然而|还是|但", t, maxsplit=1)
            d = {"left": [clip(parts[0], 5), "TODO"], "right": [clip(parts[-1], 5), "TODO"], "tones": ["info", "accent"], "tl": round(s0 + 0.3, 2), "tr": "@" + phrases(parts[-1])[0][:3] if phrases(parts[-1]) else round(s0 + 1.2, 2)}
        elif lay == "chest_cards":
            items = [p for p in ph if 2 <= len(p) <= 8][:3] or [first]
            d = {"cards": [{"zh": clip(p, 6), "tag": "TODO", "t": "@" + p[:3]} for p in items]}
        elif lay == "namecard":
            d = {"name": a.host, "role": "TODO 身份一行", "t": round(s0 + 0.4, 2)}
        elif lay == "counter":
            m = NUM.search(t)
            d = {"label": "TODO 指标名", "to": float(re.sub(r"[^\d.]", "", m.group(1)) or 0), "suffix": re.sub(r"[\d.\s]", "", m.group(1)), "t": "@" + m.group(1).strip()[:4]}
            todo.append(f"{'h' if kind == 'host' else 's'}{k + 1:02d}：数字 {m.group(1)} 要核实出处")
        elif lay == "sticker":
            d = {"words": [{"zh": clip(last, 6), "en": "TODO", "t": "@" + last[:3]}]}
        elif lay == "ending":
            d = {"big1": clip(ph[0], 8), "t1": "@" + ph[0][:3], "big2": clip(ph[-1], 8) if len(ph) > 1 else "TODO", "t2": ("@" + ph[-1][:3]) if len(ph) > 1 else round(s0 + 1.5, 2),
                 "t_end": round(s1 - 1.3, 2), "tagline": "TODO 英文一行", "reveal": "chars", "energy": "calm"}
        elif lay == "quote":
            d = {"lab1": clip(first, 6) if len(ph) > 1 else "", "en1": "TODO", "big1": clip(last, 8), "t1": "@" + last[:3]}
            if cls == "question" and punch < 2:
                d.update({"energy": "punch", "enter": "zoom"}); punch += 1
            if cls == "conclusion":
                d.update({"reveal": "chars", "energy": "calm"})
        elif lay == "chapter":
            d = {"zh": clip(first, 6), "en": "TODO", "t": round(s0 + 0.15, 2)}
        elif lay in ("band", "bigword_band", "doc", "tilt_chart"):
            if lay == "band":
                d = {"band": key("band"), "title": {"zh": clip(first, 10), "en": "TODO"}}
                nb = used.get("band", 1)
                if nb % 3 == 1:
                    d["badge"] = {"zh": clip(last, 6), "t": "@" + last[:3]}
                elif nb % 3 == 2:
                    d["corner_tag"] = {"zh": clip(first, 4), "en": "TODO", "icon": "bookmark"}
                else:
                    d["dots"] = True
            elif lay == "bigword_band":
                d = {"word": clip(last, 5), "t": "@" + last[:3], "band": key("band"), "ticker": ["TODO"]}
            elif lay == "doc":
                d = {"source": "TODO 出处", "headline": clip(t, 26), "highlight": clip(last, 8), "lines": ["TODO"], "t_hi": "@" + last[:3]}
            else:
                d = {"title": {"zh": clip(first, 12), "en": "TODO"}, "values": [10, 12, 11, 15, 18, 17, 22, 26], "line_t": round(s0 + 0.5, 2)}
                todo.append(f"s{k + 1:02d}：图表是示意数，换成真实数据或保留「示意」")
            todo.append(f"s{k + 1:02d}：找 B-roll／配图，内容是「{clip(t, 30)}」")
        elif lay in ("chain", "cascade", "pip_cards", "product_row", "grid4"):
            items = [p for p in ph if len(p) >= 2]
            if len(items) >= 3:
                items = items[1:]  # 第一句做标题，不再重复当第一项
            items = items[:4] or [first]
            if lay == "grid4":
                items = (items * 4)[:4]
                d = {"title": {"zh": clip(first, 8), "en": "TODO"}, "tiles": [{"key": key("tile"), "label": clip(p, 6), "t": "@" + p[:3]} for p in items]}
            elif lay == "pip_cards":
                d = {"title": {"zh": clip(first, 10), "en": "TODO"}, "cards": [{"zh": clip(p, 8), "en": "TODO", "img": key("thumb"), "t": "@" + p[:3]} for p in items[:2]]}
            elif lay == "product_row":
                d = {"title": {"zh": clip(first, 10), "en": "TODO"}, "items": [{"label": clip(p, 5), "sub": "TODO", "icon": "box", "t": "@" + p[:3]} for p in items[:3]]}
            else:
                d = {"title": {"zh": clip(first, 8), "en": "TODO"}, "items": [{"zh": clip(p, 8), "en": "TODO", "img": key("thumb"), "t": "@" + p[:3]} for p in items]}
            d["card_enter"] = CARD_ENTERS[ce_k % len(CARD_ENTERS)]; ce_k += 1
        elif lay == "compare":
            parts = re.split(r"但是|不过|而是|反而|可是|然而|还是|但", t, maxsplit=1)
            nums = NUM.findall(t)
            va, vb = (nums + ["TODO", "TODO"])[:2] if len(nums) >= 2 else (clip(parts[0], 6), clip(parts[-1], 6))
            d = {"title": {"zh": clip(first, 10), "en": "TODO"}, "a": {"label": "TODO", "value": va, "icon": "circle", "n": 4}, "t_a": round(s0 + 0.4, 2),
                 "b": {"label": "TODO", "value": vb, "icon": "circle", "n": 10}, "t_b": round(s0 + (s1 - s0) * 0.5, 2)}
        elif lay in ("bignum", "bars"):
            m = NUM.search(t)
            if lay == "bignum":
                d = {"pre": "TODO", "to": float(re.sub(r"[^\d.]", "", m.group(1)) or 0) if m else 0, "suffix": re.sub(r"[\d.\s]", "", m.group(1)) if m else "", "sub": "TODO", "t": ("@" + m.group(1).strip()[:4]) if m else round(s0 + 0.4, 2)}
            else:
                d = {"title": {"zh": clip(first, 10), "en": "TODO"}, "values": [3, 4, 5, 7, 9], "bars_t": round(s0 + 0.5, 2)}
            todo.append(f"s{k + 1:02d}：数字要核实出处")
        if used.get(lay, 0) >= 2 and lay not in ("plain",):  # 同一版式第二次起换节奏，不让两段动得一样
            d.setdefault("energy", ["calm", "normal", "calm"][used[lay] % 3])
            if used[lay] % 2 == 0:
                d.setdefault("enter", ["rise", "wipe", "flip"][used[lay] % 3])
        if kind == "graphic" and lay not in ("ending",) and any(w in t for w in BAD_WORDS):
            d.setdefault("tone", "bad")
        elif kind == "graphic" and any(w in t for w in GOOD_WORDS) and "？" not in t:
            d.setdefault("tone", "good")
        sid = f"{'h' if kind == 'host' else 's'}{k + 1:02d}"
        segs.append({"id": sid, "kind": kind, "layout": lay, "start": round(s0, 3), "end": round(s1, 3), "data": d, "_text": t})
    # 3 章节：大约 25–35 秒一章
    chapters, last = [[0, "TODO 章名"]], 0.0
    for sg in segs[1:]:
        if sg["start"] - last >= 25 and len(chapters) < 6:
            chapters.append([sg["start"], "TODO 章名"]); last = sg["start"]
    # 4 母题图标：按全文里出现的题材词选
    full = " ".join(texts)
    motif = []
    for zh, en in ZH.items():
        if zh in full:
            for name in en.split():
                if os.path.exists(os.path.join(ROOT, "assets", "icons", "lucide", name + ".svg")) and name not in motif:
                    motif.append(name)
                    break
    motif = (motif + ["circle-dollar-sign", "trending-up", "landmark"])[:3]
    host_badge = [x for x in a.badge.split(",")] if a.badge else [a.host, ""]
    plan = {"title": a.title, "style": st.key, "account": a.account, "duration": dur, "aroll_duration": adur,
            "captions": os.path.basename(a.captions),
            "host": {"name": a.host, "badge": host_badge}, "chapters": chapters, "updates": [], "motif": motif, "segments": segs,
            "_todo": todo + ["每个 TODO 都要换成实际内容；英文副题按中文意思写", "检查每段版式是否贴合内容，参考 references/02 的「内容 → 调法」"]}
    if a.chartimes:
        plan["chartimes"] = os.path.basename(a.chartimes)
    if a.cuts:
        plan["cuts"] = os.path.basename(a.cuts)
    if a.fill_placeholders:
        rep = dict(x.split("=") for x in a.fill_placeholders.split(","))
        txt = json.dumps(plan, ensure_ascii=False)
        for k_, v_ in rep.items():
            txt = re.sub(rf'"{k_}_TODO_\d+"', f'"{v_}"', txt)
        txt = txt.replace('"TODO"', '"Note"').replace('TODO 章名', '章节').replace('TODO 英文一行', 'Note').replace('TODO 出处', '示例').replace('TODO 身份一行', '示例').replace('TODO 指标名', '示例')
        plan = json.loads(txt)
    json.dump(plan, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"草稿：{len(segs)} 段（人物 {sum(1 for s in segs if s['kind'] == 'host')}、图解 {sum(1 for s in segs if s['kind'] == 'graphic')}），{len(chapters)} 章，母题 {motif}")
    if G is not None:
        for ln in room.summary(G.geom)[1]:
            print("  人物空间｜" + ln)
    for sg in segs:
        print(f"  {sg['id']} {sg['start']:6.1f}–{sg['end']:6.1f} {sg['kind']:7s} {sg['layout']:13s} {clip(sg['_text'], 24)}")
    print("待办：\n  - " + "\n  - ".join(plan["_todo"]))


if __name__ == "__main__":
    main()
