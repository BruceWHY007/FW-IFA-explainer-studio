# -*- coding: utf-8 -*-
"""重剪：剪辑表改了以后（多剪了重说、改了 fix.json 的 drop、手改了 edl.json），一条命令把后面的步骤按顺序重跑一遍。

用法：
  python3 scripts/recut.py --work 工作目录 --plan plan.json --geom geom.json --out out
      先重跑 edl.py（转写、原片、fix.json 沿用上一次 edl.py 的输入，记在 edl_report.json 里），再往下跑
  python3 scripts/recut.py ... --no-edl        手改过 edl.json，直接用它往下跑
  python3 scripts/recut.py ... --dry-run       只算分镜表时间怎么搬，不改任何文件
  python3 scripts/recut.py --work 工作目录 --where 107.5    成片第 107.5 秒是原片第几秒、在说哪句（用户指出还有重说时用）
人听出来、自动没找到的重说：查到原片区间后写进 fix.json 的 "cut": [[原片起, 原片止]]，再跑 recut.py（重跑也保留，不要手改 edl.json）。
顺序：edl.py → prep.py cut → voice → captions → mix（做过配乐才跑）→ measure.py → 搬分镜表时间 → om.py import
      → build.py → om.py stage → lint → check → safe（平台安全区）→ edl.py --scan 查剪好的人声里还有没有重说。
      哪一步失败就停在哪一步，前面的产物留着。跑完以后自己抽帧看接点，再 om.py save、export。
搬分镜表时间：plan.json 里写成数字的时间（段起止、章节、各版式的 t／t1…、底座卡起止、caption_skip）都是旧成片时间。
  旧剪辑表把它换回原片时间，新剪辑表再换成新成片时间；落进新剪掉那段的，贴到下一段保留段的开头。
  写成「@关键词」的时间不用搬，build 按新字幕自己找。人声结束后的落版留白长度保持不变。
  改之前备份到 工作目录/_recut/时间/（plan.json、edl_frames.json、cuts.json、captions.json、geom.json）。
"""
import argparse, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build import TIME_KEYS  # noqa: E402  和 build.py 用同一份时间字段表

PY = sys.executable


def run(step, args):
    t = time.time()
    print(f"\n▶ {step}", flush=True)
    r = subprocess.run([PY] + args, text=True, encoding="utf-8")
    if r.returncode:
        print(f"✗ {step} 失败（退出码 {r.returncode}），停在这一步")
        sys.exit(r.returncode)
    print(f"  {step} 用时 {time.time() - t:.0f} 秒")


def mapper(old, new):
    """旧成片时间 → 原片时间 → 新成片时间。old／new 是剪辑表（原片里保留的段）。"""
    def seq(spans):
        out, off = [], 0.0
        for a, b in spans:
            out.append((a, b, off))
            off += b - a
        return out, off
    os_, ot = seq(old)
    ns, nt = seq(new)

    def to_src(t):
        for a, b, o in os_:
            if o - 1e-6 <= t <= o + (b - a) + 1e-6:
                return a + (t - o)
        return os_[-1][1] if os_ else t

    def to_new(s):
        for a, b, o in ns:
            if a - 1e-6 <= s <= b + 1e-6:
                return o + (s - a)
        for a, b, o in ns:  # 落进剪掉的那段：贴到下一段保留段的开头
            if a > s:
                return o
        return nt
    def f(t):
        if t >= ot - 1e-6:  # 人声结束以后的落版：跟着片尾平移，长度不变
            return round(nt + (t - ot), 3)
        return round(to_new(to_src(t)), 3)
    return f, ot, nt


def retime(plan, f, ot, nt):
    """把分镜表里的数字时间搬到新时间轴。返回搬动了几个。"""
    n = [0]

    def mv(v):
        n[0] += 1
        return f(v)

    def walk(o):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k in TIME_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                    o[k] = mv(v)
                elif k == "tiles_t" and isinstance(v, list):
                    o[k] = [mv(x) if isinstance(x, (int, float)) else x for x in v]
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    old_aroll = float(plan.get("aroll_duration") or ot)
    tail = max(0.0, float(plan.get("duration", old_aroll)) - old_aroll)
    for s in plan.get("segments", []):
        for k in ("start", "end"):
            if isinstance(s.get(k), (int, float)):
                s[k] = mv(s[k])
        walk(s.get("data") or {})
    if plan.get("chapters"):
        plan["chapters"] = [[mv(t) if isinstance(t, (int, float)) else t, name] for t, name in plan["chapters"]]
    if plan.get("caption_skip"):
        plan["caption_skip"] = [[mv(x), mv(y)] for x, y in plan["caption_skip"]]
    for u in plan.get("updates", []) or []:
        for k in ("start", "end"):
            if isinstance(u.get(k), (int, float)):
                u[k] = mv(u[k])
    plan["aroll_duration"] = round(nt, 3)
    plan["duration"] = round(nt + tail, 3)
    if plan.get("segments"):
        plan["segments"][-1]["end"] = plan["duration"]
    return n[0]


def where(W, t):
    """成片时间 → 原片时间，列出附近的句子（原片时间、逐字时间），方便写 fix.json 的 cut。"""
    frames = json.load(open(os.path.join(W, "edl_frames.json")))
    off = 0.0
    src = None
    for a, b in frames:
        if off <= t <= off + (b - a):
            src = a + (t - off)
            break
        off += b - a
    if src is None:
        sys.exit(f"✗ 成片只有 {off:.2f} 秒")
    print(f"成片 {t:.2f} 秒 ＝ 原片 {src:.2f} 秒")
    tp = os.path.join(W, "transcript_edl.json")
    if os.path.exists(tp):
        tr = json.load(open(tp, encoding="utf-8"))
        for s in (tr["sentences"] if isinstance(tr, dict) else tr):
            if s["end"] > src - 6 and s["start"] < src + 6:
                mark = "  ← 这里" if s["start"] - 0.3 <= src <= s["end"] + 0.3 else ""
                print(f"  {s['start']:7.2f}–{s['end']:7.2f}  {'(已删) ' if s.get('drop') else ''}{s['text']}{mark}")
                if mark and s.get("chars"):
                    print("           " + " ".join(f"{q['c']}{q['s']:.2f}" for q in s["chars"]))
    print("确认要剪的原片区间后写进 fix.json：\"cut\": [[起, 止]]，再跑 recut.py")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True); ap.add_argument("--plan")
    ap.add_argument("--geom"); ap.add_argument("--out")
    ap.add_argument("--where", type=float, help="成片秒数：换成原片秒数，并列出前后的句子和逐字时间")
    ap.add_argument("--src"); ap.add_argument("--transcript"); ap.add_argument("--fix")
    ap.add_argument("--no-edl", action="store_true", help="不重跑 edl.py，直接用工作目录里的 edl.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    W = os.path.abspath(a.work)
    if a.where is not None:
        return where(W, a.where)
    if not (a.plan and a.geom and a.out):
        ap.error("要 --plan、--geom、--out（或只用 --where）")
    t_all = time.time()
    rp = os.path.join(W, "edl_report.json")
    inp = (json.load(open(rp, encoding="utf-8")).get("输入") or {}) if os.path.exists(rp) else {}
    src, trn = a.src or inp.get("src"), a.transcript or inp.get("transcript")
    fix = a.fix or inp.get("fix")
    if not src or not trn:
        sys.exit("✗ 找不到原片或转写：上一次 edl.py 的输入没记下来，请加 --src 原片 --transcript transcript.json")
    old_frames = json.load(open(os.path.join(W, "edl_frames.json")))  # 现在这版成片用的剪辑表（按帧取整过）
    plan = json.load(open(a.plan, encoding="utf-8"))

    # 自检：旧剪辑表映射到自己，时间应该不变
    f_id, _, _ = mapper(old_frames, old_frames)
    for t in (0.0, 1.234, float(plan.get("aroll_duration") or 0) * 0.5):
        assert abs(f_id(t) - round(t, 3)) < 0.002, "时间映射自检没通过"
    if a.dry_run:
        new = json.load(open(os.path.join(W, "edl.json")))
        f, ot, nt = mapper(old_frames, new)
        p2 = json.loads(json.dumps(plan))
        n = retime(p2, f, ot, nt)
        print(f"（只算不改）会搬 {n} 个时间；人声 {ot:.2f} → {nt:.2f} 秒")
        for s0, s1 in zip(plan["segments"], p2["segments"]):
            print(f"  {s0['id']}  {s0['start']:.2f}–{s0['end']:.2f} → {s1['start']:.2f}–{s1['end']:.2f}")
        return

    bk = os.path.join(W, "_recut", time.strftime("%m%d-%H%M%S"))
    os.makedirs(bk)
    for p in (os.path.abspath(a.plan), os.path.join(W, "edl_frames.json"), os.path.join(W, "cuts.json"),
              os.path.join(W, "captions.json"), os.path.abspath(a.geom)):
        if os.path.exists(p):
            shutil.copy(p, bk)
    print(f"已备份到 {bk}")

    S = lambda n: os.path.join(HERE, n)
    if not a.no_edl:
        run("剪辑表 edl.py", [S("edl.py"), "--transcript", trn, "--src", src, "--work", W] + (["--fix", fix] if fix else []))
    run("剪辑 prep.py cut", [S("prep.py"), "cut", "--work", W, "--src", src, "--edl", os.path.join(W, "edl.json")])
    run("人声 prep.py voice", [S("prep.py"), "voice", "--work", W])
    tr_edl = os.path.join(W, "transcript_edl.json")
    run("字幕 prep.py captions", [S("prep.py"), "captions", "--work", W, "--transcript", tr_edl if os.path.exists(tr_edl) else trn]
        + (["--fix", fix] if fix else []))
    new_frames = json.load(open(os.path.join(W, "edl_frames.json")))
    f, ot, nt = mapper(old_frames, new_frames)
    mp = os.path.join(W, "mix.json")
    if os.path.exists(mp):
        m = json.load(open(mp))
        args = [S("prep.py"), "mix", "--work", W, "--music", m["music"], "--gain", str(m["gain"])]
        if m.get("dur"):
            args += ["--dur", str(round(m["dur"] + nt - ot, 3))]
        run("配乐 prep.py mix", args)
    run("量人物 measure.py", [S("measure.py"), os.path.join(W, "om_assets", "aroll.mp4"), os.path.abspath(a.geom)])
    n = retime(plan, f, ot, nt)
    bad = [s["id"] for s in plan.get("segments", []) if s["end"] - s["start"] < 0.5]
    json.dump(plan, open(a.plan, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n▶ 分镜表：搬了 {n} 个时间；人声 {ot:.2f} → {nt:.2f} 秒，片长 {plan['duration']:.2f} 秒")
    if bad:
        print(f"  ! 这几段剪完不到 0.5 秒（内容多半被剪掉了），去 plan.json 删掉或并进相邻段：{'、'.join(bad)}")
    run("导入 om.py import", [S("om.py"), "import", "--work", W, "--manifest", os.path.join(W, "import.json")])
    run("构建 build.py", [S("build.py"), os.path.abspath(a.plan), "--assets", os.path.join(W, "assets.json"),
                          "--geom", os.path.abspath(a.geom), "--out", os.path.abspath(a.out)])
    run("挂素材 om.py stage", [S("om.py"), "stage", "--work", W, "--dir", os.path.abspath(a.out)])
    run("代码检查 om.py lint", [S("om.py"), "lint", "--dir", os.path.abspath(a.out)])
    run("完整检查 om.py check", [S("om.py"), "check", "--dir", os.path.abspath(a.out)])
    run("平台安全区 om.py safe", [S("om.py"), "safe", "--dir", os.path.abspath(a.out)])
    run("查剩下的重说 edl.py --scan", [S("edl.py"), "--scan", os.path.join(W, "om_assets", "voice.wav")])
    print(f"\n✓ 重剪完成，共 {time.time() - t_all:.0f} 秒。下一步：抽帧看接点（joins.json 里 kind=retake 的时间），"
          f"再 om.py save、om.py export。")


if __name__ == "__main__":
    main()
