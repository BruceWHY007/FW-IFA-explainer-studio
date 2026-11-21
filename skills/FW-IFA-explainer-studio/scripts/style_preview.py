# -*- coding: utf-8 -*-
"""开工时让用户选风格：用本人的画面和这支片的开头标题，五套风格各出两格（人物段头顶标题＋图解段金句），拼成一张对照图，
并按转写内容给出推荐（讲钱／机构／资源／品牌／科技 → 炭金／档案／矿石／瓷蓝／霓虹）。

用法（prep.py cut／captions／base 和 measure.py 跑完之后）：
  python3 scripts/style_preview.py --work 工作目录 --geom geom.json --transcript transcript.json \\
      --title "香港定存|*3.6%*" --sub "你是不是也有点心动？" --phrase "每个条件|都不是废话" [--account 账号] [--out 对照图.jpg]
产物：对照图（默认 工作目录/style_preview.jpg），终端打印推荐和理由。约 40 秒。
Agent 把对照图和推荐发给用户问一次：「选哪套？回『你定』就用推荐的」。用户在请求里已经点名风格就不跑这一步。
"""
import argparse, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "lib"))
sys.path.insert(0, HERE)
from tujie import styles  # noqa: E402
import om  # noqa: E402

TOPIC = {  # 按题材推荐：命中的词越多越像
    "tanjin": ("讲钱：宏观、市场、资产价格、估值", ["黄金", "金价", "股", "市场", "估值", "上市", "利率", "降息", "加息", "美元", "资产", "价格", "通胀", "收益", "基金", "债", "汇率", "楼市"]),
    "dangan": ("讲机构：银行、保险、条款、风险、案例", ["银行", "保险", "机构", "监管", "条件", "条款", "风险", "合规", "牌照", "存款", "定存", "保单", "历史", "案例", "理财客户", "分行"]),
    "kuangshi": ("讲资源：资源、产业链、地缘、政策", ["稀土", "石油", "矿", "资源", "产业链", "关税", "制裁", "地缘", "大宗", "出口", "能源", "政策", "供应链"]),
    "cilan": ("讲品牌：品牌、消费、商业模式", ["品牌", "酒店", "消费", "门店", "商业模式", "会员", "零售", "餐厅", "连锁", "体验", "复购"]),
    "nihong": ("讲科技：AI、互联网、游戏、产品", ["AI", "模型", "芯片", "游戏", "互联网", "科技", "算力", "App", "平台", "机器人", "大模型", "软件"]),
}


def recommend(text, account=None):
    score = {k: sum(text.count(w) for w in ws) for k, (_, ws) in TOPIC.items()}
    order = sorted(score, key=lambda k: -score[k])
    hits = {k: [w for w in TOPIC[k][1] if w in text][:5] for k in order[:2]}
    last = None
    reg = os.path.join(ROOT, "data", "registry.json")
    if account and os.path.exists(reg):
        films = json.load(open(reg, encoding="utf-8")).get(account) or []
        last = films[-1].get("style") if films else None
    return order, score, hits, last


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True); ap.add_argument("--geom", required=True); ap.add_argument("--transcript", required=True)
    ap.add_argument("--title", required=True, help="开头标题，| 换行，*…* 强调"); ap.add_argument("--sub", default="")
    ap.add_argument("--phrase", required=True, help="片中一句金句或转折，图解段大字用，| 换行")
    ap.add_argument("--account"); ap.add_argument("--out")
    a = ap.parse_args()
    W = os.path.abspath(a.work)
    P = os.path.join(W, "_style_preview")
    shutil.rmtree(P, ignore_errors=True)
    A = os.path.join(P, "assets")
    os.makedirs(A)
    assets = {}
    for it in json.load(open(os.path.join(W, "import.json"), encoding="utf-8")):  # prep.py 写的导入清单
        ext = os.path.splitext(it["path"])[1]
        dst = os.path.join(A, it["key"] + ext)
        try:
            os.symlink(it["path"], dst)
        except OSError:
            shutil.copy(it["path"], dst)
        assets[it["key"]] = "assets/" + it["key"] + ext
    g = os.path.join(om.install()["appRoot"], "node_modules", "gsap", "dist", "gsap.min.js")
    shutil.copy(g, os.path.join(A, "gsap.min.js"))
    json.dump(assets, open(os.path.join(P, "assets.json"), "w"), indent=1)
    caps = [c for c in json.load(open(os.path.join(W, "captions.json"), encoding="utf-8")) if c["start"] < 7]
    json.dump(caps, open(os.path.join(P, "captions.json"), "w", encoding="utf-8"), ensure_ascii=False)
    tr = json.load(open(a.transcript, encoding="utf-8"))
    text = "".join(s["text"] for s in (tr["sentences"] if isinstance(tr, dict) else tr))
    order, score, hits, last = recommend(text, a.account)
    lines = a.title.split("|")
    tl = [{"text": ln, "cls": "T2" if k == 0 and len(lines) > 1 else "T1", "t": round(0.1 + 0.25 * k, 2)} for k, ln in enumerate(lines)]
    if a.sub:
        tl.append({"text": a.sub, "cls": "sub", "t": 0.7})
    shots = []
    for st in styles.STYLES:
        plan = {"title": "风格对照", "style": st, "duration": 6.4, "aroll_duration": 6.4, "captions": "captions.json",
                "host": {"name": "", "badge": ["", ""]}, "chapters": [[0, "开场"], [3.2, "要点"], [5.0, "结论"]],
                "segments": [{"id": "h01", "kind": "host", "layout": "title_top", "start": 0, "end": 3.2, "data": {"lines": tl}},
                             {"id": "s02", "kind": "graphic", "layout": "quote", "start": 3.2, "end": 6.4,
                              "data": {"lab1": "", "en1": "", "big1": a.phrase, "t1": 3.5}}]}
        pp = os.path.join(P, f"plan_{st}.json")
        json.dump(plan, open(pp, "w", encoding="utf-8"), ensure_ascii=False)
        d = os.path.join(P, st)
        r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), pp, "--assets", os.path.join(P, "assets.json"),
                            "--geom", os.path.abspath(a.geom), "--out", d], capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            print(f"✗ {st} 构建失败：{(r.stdout + r.stderr)[-300:]}")
            continue
        om.link_dir(A, os.path.join(d, "assets"))
        json.dump({"paths": {"blocks": "compositions", "assets": "assets"}}, open(os.path.join(d, "hyperframes.json"), "w"))
        sd = os.path.join(P, f"snap_{st}")
        subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "snapshot", "--dir", d, "--at", "2.2,4.7", "--out", sd],
                       capture_output=True, text=True, encoding="utf-8")
        fs = sorted(f for f in os.listdir(sd) if f.startswith("frame-")) if os.path.isdir(sd) else []
        if len(fs) >= 2:
            shots.append((st, [os.path.join(sd, f) for f in fs[:2]]))
    from PIL import Image, ImageDraw, ImageFont
    fp = os.path.join(ROOT, "assets", "fonts", "SmileySans-Oblique.otf")
    f1, f2 = ImageFont.truetype(fp, 44), ImageFont.truetype(fp, 26)
    cw, ch, top = 324, 576, 150
    sheet = Image.new("RGB", (len(shots) * (cw * 2 + 24) + 24, ch + top + 30), (14, 14, 16))
    dr = ImageDraw.Draw(sheet)
    for k, (st, ims) in enumerate(shots):
        x = 24 + k * (cw * 2 + 24)
        name = styles.STYLES[st].name
        tag = "  ★ 推荐" if st == order[0] else ("  · 备选" if st == order[1] else "")
        dr.text((x, 24), f"{name}{tag}", font=f1, fill=(240, 200, 120) if st == order[0] else (230, 230, 230))
        dr.text((x, 84), TOPIC[st][0], font=f2, fill=(170, 170, 175))
        for j, im in enumerate(ims):
            sheet.paste(Image.open(im).convert("RGB").resize((cw, ch)), (x + j * cw, top))
    out = a.out or os.path.join(W, "style_preview.jpg")
    sheet.save(out, quality=88)
    nm = lambda k: styles.STYLES[k].name if k in styles.STYLES else k
    print(f"对照图：{out}")
    print(f"推荐：{nm(order[0])}（命中 {score[order[0]]} 次：{'、'.join(hits[order[0]])}）；备选：{nm(order[1])}（{score[order[1]]} 次：{'、'.join(hits[order[1]]) or '无'}）")
    if last:
        print(f"这个账号上一支用的是 {nm(last)}：选同一套的话，build 会提醒换强调色。")


if __name__ == "__main__":
    main()
