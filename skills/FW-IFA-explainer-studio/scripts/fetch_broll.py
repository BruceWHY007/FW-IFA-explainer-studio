# -*- coding: utf-8 -*-
"""B-roll 一条命令下完并转好：几条同时下载，每条下完立刻转成横条／背景／配图并写进导入清单。

用法（挑好片之后，放到后台跑，同时写分镜表）：
  python3 scripts/fetch_broll.py --work 工作目录 键=来源:编号:种类[:起点[:时长]] …
  例：python3 scripts/fetch_broll.py --work W drop=pe:3945008:band lab=pe:8381408:band \\
          mall=pe:36593014:bg school=pe:37777213:thumb clip=/素材/本地.mp4:band,thumb:2:8
  种类：band 横条、tile 宫格、full 竖版全屏、bg 背景图、thumb 配图，可用逗号写多个；起点默认 1 秒，时长默认 12 秒。
  分镜表里的素材键是「种类_键」：band_drop、bg_mall、thumb_school。

下载借 IFA口播成片 的 scripts/stock.py（搜索也用它：python3 <IFA口播成片>/scripts/stock.py 项目目录 search "英文画面词"），
不改它：每条在自己的临时目录里下（stock.py 下完会改写 stock_picks.json，几条同时写会互相覆盖），下完搬回项目目录、合并授权记录。
没装 IFA口播成片 时只能用本地文件（写成 键=/路径/文件.mp4:band）。
项目目录默认是工作目录的上一级（broll/stock 在那里，和 stock.py search 用同一个）。

为什么这样做：实测一支 2.5 分钟的片子，8 条素材一条接一条下，Agent 在前台干等了 7 分钟；同时下载本身快不了多少（瓶颈是网速），省时间靠和写分镜表同时进行。
下载跑在后台、同时写分镜表；导入（om.py import）之前等它跑完。
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = re.compile(r"^(?P<key>[A-Za-z0-9_-]+)=(?P<src>.+?):(?P<kinds>[a-z]+(?:,[a-z]+)*)(?::(?P<start>[\d.]+))?(?::(?P<dur>[\d.]+))?$")
VIDEO_KINDS = {"band", "tile", "full", "bg", "thumb"}
IMAGE_KINDS = {"bg", "thumb"}
LOCK = threading.Lock()


def find_stock():
    """找 IFA口播成片 的 stock.py：环境变量 TUJIE_STOCK → 和本技能并排装的 → 常见安装位置。"""
    cands = [os.environ.get("TUJIE_STOCK", ""),
             os.path.join(HERE, "..", "..", "IFA口播成片", "scripts", "stock.py")]
    home = os.path.expanduser("~")
    for root in (".agents", ".claude", ".codex", ".dsh"):
        cands.append(os.path.join(home, root, "skills", "IFA口播成片", "scripts", "stock.py"))
    for c in cands:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    return None


def merge_json(path, name, entry):
    with LOCK:
        d = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
        d[name] = entry
        json.dump(d, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def download(it, stock, proj):
    """在临时项目目录里跑 stock.py get，搜索缓存（_thumbs、_html）链回正式目录。返回 (本地文件, 是否图片)。"""
    D = os.path.join(proj, "broll", "stock")
    for f in (it["key"] + ".mp4",):
        p = os.path.join(D, f)
        if os.path.exists(p) and os.path.getsize(p) > 50000:
            return p, False
    pimg = os.path.join(proj, "broll", "img", it["key"] + ".jpg")
    if os.path.exists(pimg) and os.path.getsize(pimg) > 20000:
        return pimg, True
    tmp = tempfile.mkdtemp(prefix="tujie_fetch_")
    try:
        td = os.path.join(tmp, "broll", "stock")
        os.makedirs(td)
        for sub in ("_thumbs", "_html"):
            os.makedirs(os.path.join(D, sub), exist_ok=True)
            try:
                os.symlink(os.path.abspath(os.path.join(D, sub)), os.path.join(td, sub), target_is_directory=True)
            except OSError:  # Windows 没开开发者模式不能建符号链接：复制搜索索引（缓存页面就不共享了）
                shutil.copytree(os.path.join(D, sub), os.path.join(td, sub), dirs_exist_ok=True)
        r = subprocess.run([sys.executable, stock, tmp, "get", it["src"], it["key"]], capture_output=True, text=True, encoding="utf-8")
        out = (r.stdout + r.stderr).strip()
        vid = os.path.join(td, it["key"] + ".mp4")
        img = os.path.join(tmp, "broll", "img", it["key"] + ".jpg")
        if os.path.exists(vid) and os.path.getsize(vid) > 50000:
            os.makedirs(D, exist_ok=True)
            dst = os.path.join(D, it["key"] + ".mp4")
            shutil.move(vid, dst)
            picks = json.load(open(os.path.join(td, "stock_picks.json"), encoding="utf-8")) if os.path.exists(os.path.join(td, "stock_picks.json")) else {}
            if it["key"] in picks:
                merge_json(os.path.join(D, "stock_picks.json"), it["key"], picks[it["key"]])
            return dst, False
        if os.path.exists(img) and os.path.getsize(img) > 20000:
            d2 = os.path.join(proj, "broll", "img")
            os.makedirs(d2, exist_ok=True)
            dst = os.path.join(d2, it["key"] + ".jpg")
            shutil.move(img, dst)
            rp = os.path.join(tmp, "broll", "img", "img_picks.json")
            picks = json.load(open(rp, encoding="utf-8")) if os.path.exists(rp) else {}
            if it["key"] in picks:
                merge_json(os.path.join(d2, "img_picks.json"), it["key"], picks[it["key"]])
            return dst, True
        raise RuntimeError("下载失败：" + (out.splitlines()[-1] if out else "stock.py 没有输出"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def convert(it, path, is_img, work):
    """转成分镜表要的素材并写进导入清单（import.json 只能一条一条写，加锁）。"""
    kinds = it["kinds"]
    if is_img or os.path.splitext(path)[1].lower() in (".jpg", ".jpeg", ".png", ".webp"):
        bad = [k for k in kinds if k not in IMAGE_KINDS]
        if bad:
            raise RuntimeError(f"图片只能做 bg／thumb，不能做 {'、'.join(bad)}")
        cmd = ["image", "--work", work, "--src", path, "--key", it["key"], "--kinds", ",".join(kinds)]
    else:
        cmd = ["broll", "--work", work, "--src", path, "--key", it["key"], "--kinds", ",".join(kinds),
               "--start", str(it["start"]), "--dur", str(it["dur"])]
    with LOCK:
        r = subprocess.run([sys.executable, os.path.join(HERE, "prep.py")] + cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError("转换失败：" + (r.stdout + r.stderr).strip()[-300:])
    return [f"{k}_{it['key']}" for k in kinds]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", required=True)
    ap.add_argument("--proj", help="stock.py 的项目目录（broll/stock 所在）；默认是工作目录的上一级")
    ap.add_argument("--jobs", type=int, default=4, help="同时下载几条，默认 4")
    ap.add_argument("items", nargs="+", help="键=来源:编号:种类[:起点[:时长]]，或 键=/本地/文件:种类[:起点[:时长]]")
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    proj = os.path.abspath(a.proj or os.path.join(work, ".."))
    items = []
    for s in a.items:
        m = SPEC.match(s)
        if not m:
            sys.exit(f"看不懂「{s}」：写成 键=来源:编号:种类[:起点[:时长]]，如 drop=pe:3945008:band")
        kinds = m["kinds"].split(",")
        bad = [k for k in kinds if k not in VIDEO_KINDS]
        if bad:
            sys.exit(f"「{s}」里的种类 {'、'.join(bad)} 不认识：只能用 band、tile、full、bg、thumb")
        src = os.path.expanduser(m["src"])
        items.append({"key": m["key"], "src": src, "local": os.path.isfile(src), "kinds": kinds,
                      "start": float(m["start"] or 1), "dur": float(m["dur"] or 12)})
    stock = find_stock()
    if any(not it["local"] for it in items) and not stock:
        sys.exit("没找到 IFA口播成片 的 scripts/stock.py（或用环境变量 TUJIE_STOCK 指定）：免费片库要自己下好，写成 键=/路径/文件.mp4:band")
    t0 = time.time()
    done, failed = [], []

    def one(it):
        ts = time.time()
        try:
            path, is_img = (it["src"], False) if it["local"] else download(it, stock, proj)
            keys = convert(it, path, is_img, work)
            mb = os.path.getsize(path) / 1e6
            print(f"✓ {it['key']:12s} {mb:6.1f}MB  {time.time() - ts:5.1f}s  → {'、'.join(keys)}", flush=True)
            done.extend(keys)
        except Exception as e:  # 一条失败不拖住其他条
            print(f"✗ {it['key']:12s} {e}", flush=True)
            failed.append(it["key"])

    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        list(ex.map(one, items))
    print(f"共 {len(items)} 条，成功 {len(items) - len(failed)} 条，用时 {time.time() - t0:.0f} 秒。素材键：{'、'.join(done) or '无'}")
    if failed:
        print(f"失败：{'、'.join(failed)}（换一条重下：同一条命令只写失败的那几条）")
        sys.exit(1)


if __name__ == "__main__":
    main()
