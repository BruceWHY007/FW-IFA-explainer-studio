# -*- coding: utf-8 -*-
"""OpenMotion 调用封装（macOS／Windows／Linux 通用）。直接调用 OpenMotion 自带的命令行入口，不依赖宿主是否加载了 MCP 工具。

  python om.py doctor                                   查环境：node、OpenMotion、ffmpeg、Chrome、Python 依赖
  python om.py create  --work W --title 标题 --req 需求    新建工程，编号记到 W/om_state.json
  python om.py import  --work W --manifest import.json  导入素材（视频、音频、图片、字体），生成 W/assets.json（键 → 工程内路径）
  python om.py save    --work W --dir OUT --summary 说明  把 build 出来的 index.html＋compositions 存成新版本
  python om.py stage   --work W --dir OUT                把工程素材链到 OUT/assets，供本地 lint／snapshot
  python om.py lint    --dir OUT
  python om.py snapshot --dir OUT --at 1.2,5.8,… --out 帧目录
  python om.py check   --dir OUT                       全画面版面检查：文字互相压住、超出画面、溢出容器（每段入场后和段尾各查一帧）
  python om.py preview --work W                          打开 Studio 编辑器，打印网址
  python om.py export  --work W --out 成片.mp4            导出并等技术校验，复制成片

import.json 格式：[{"key":"aroll","path":"/绝对路径/aroll.mp4","name":"显示名","license":"/同目录/许可.txt（字体才要）"}]
"""
import argparse, json, os, platform, re, shutil, subprocess, sys, tempfile, time, uuid, webbrowser

IS_WIN = platform.system() == "Windows"


# ---------------------------------------------------------------- 环境
def om_home():
    if os.environ.get("OPENMOTION_HOME"):
        return os.environ["OPENMOTION_HOME"]
    if IS_WIN:
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "openmotion")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "openmotion")


def install():
    p = os.path.join(om_home(), "install.json")
    if not os.path.exists(p):
        sys.exit(f"没找到 OpenMotion（{p}）。先装基础 OpenMotion（https://github.com/nexu-io/openmotion）：python scripts/setup.py")
    return json.load(open(p, encoding="utf-8"))


def node():
    n = os.environ.get("OPENMOTION_NODE") or shutil.which("node")
    if not n:
        sys.exit("没找到 node（需要 Node 22.18+）")
    return n


def chrome():
    if os.environ.get("HYPERFRAMES_BROWSER_PATH"):
        return os.environ["HYPERFRAMES_BROWSER_PATH"]
    cands = {
        "Darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "Windows": [os.path.join(os.environ.get(v, ""), r"Google\Chrome\Application\chrome.exe") for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")],
    }.get(platform.system(), [shutil.which("google-chrome") or "", shutil.which("chromium") or ""])
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def tool_env():
    """渲染用本机的 Chrome 和 ffmpeg，不让 HyperFrames 另外下载；关掉使用数据上报。"""
    env = dict(os.environ)
    c = chrome()
    if c:
        env.setdefault("HYPERFRAMES_BROWSER_PATH", c)
    for k, exe in (("HYPERFRAMES_FFMPEG_PATH", "ffmpeg"), ("HYPERFRAMES_FFPROBE_PATH", "ffprobe")):
        w = shutil.which(exe)
        if w:
            env.setdefault(k, w)
    env.setdefault("OPENMOTION_TELEMETRY", "0")
    return env


def call(tool, args):
    ins = install()
    cli = os.path.join(ins["appRoot"], "scripts", "npm-installer.mjs")
    host = next(iter(ins.get("hosts", {"claude": {}})))
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(args, f, ensure_ascii=False)
        fn = f.name
    try:
        r = subprocess.run([node(), cli, "call", tool, "--args-file", fn, "--host", host], capture_output=True, text=True, encoding="utf-8", env=tool_env())
    finally:
        os.unlink(fn)
    try:
        out = json.loads(r.stdout)
    except Exception:
        sys.exit(f"{tool} 调用失败：{r.stdout[-800:]}{r.stderr[-800:]}")
    if out.get("isError"):
        txt = "".join(c.get("text", "") for c in out.get("content", []))
        sys.exit(f"{tool} 报错：{txt[:1500]}")
    return out.get("structuredContent") or {}


def rid(tag):
    return f"tujie-{tag}-{uuid.uuid4().hex[:10]}"


def state_path(work):
    return os.path.join(work, "om_state.json")


def load_state(work):
    p = state_path(work)
    if not os.path.exists(p):
        sys.exit(f"{p} 不存在，先运行 create")
    return json.load(open(p, encoding="utf-8"))


def save_state(work, st):
    json.dump(st, open(state_path(work), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 命令
def cmd_doctor(a):
    rows = []
    rows.append(("系统", platform.platform()))
    try:
        rows.append(("node", subprocess.check_output([node(), "--version"], text=True).strip()))
    except SystemExit as e:
        rows.append(("node", f"✗ {e}"))
    p = os.path.join(om_home(), "install.json")
    rows.append(("OpenMotion", json.load(open(p))["version"] + " @ " + om_home() if os.path.exists(p) else f"✗ 未安装（{p}）"))
    for exe in ("ffmpeg", "ffprobe"):
        rows.append((exe, shutil.which(exe) or "✗ 未找到（mac: brew install ffmpeg；Windows: winget install Gyan.FFmpeg）"))
    rows.append(("Chrome", chrome() or "✗ 未找到（HyperFrames 会自己下载一份，或设 HYPERFRAMES_BROWSER_PATH）"))
    if platform.system() == "Darwin":
        rows.append(("人物测量", "vision（系统自带）" if shutil.which("swiftc") else "✗ 缺 swiftc：xcode-select --install，或改用 mediapipe"))
    else:
        try:
            import mediapipe  # noqa: F401
            rows.append(("人物测量", "mediapipe ✓"))
        except Exception:
            rows.append(("人物测量", "✗ pip install mediapipe==0.10.14 opencv-python-headless（Python 3.9–3.12）"))
    try:
        import PIL  # noqa: F401
        rows.append(("Pillow", "✓"))
    except Exception:
        rows.append(("Pillow", "✗ pip install pillow"))
    for k, v in rows:
        print(f"{k:12s} {v}")


def cmd_create(a):
    os.makedirs(a.work, exist_ok=True)
    r = call("openmotion_create_project", {"requestId": rid("create"), "projectType": "natural_language", "title": a.title,
                                           "namingLanguage": "zh-CN", "requirements": a.req})
    pid = r.get("projectId") or (r.get("project") or {}).get("id")
    save_state(a.work, {"projectId": pid, "title": a.title})
    print(pid)


def cmd_import(a):
    st = load_state(a.work)
    items = json.load(open(a.manifest, encoding="utf-8"))
    amap_p = os.path.join(a.work, "assets.json")
    amap = json.load(open(amap_p, encoding="utf-8")) if os.path.exists(amap_p) else {}
    fp_p = os.path.join(a.work, "assets_src.json")  # 每个键导入时源文件的指纹：重剪、重混后同名文件变了要重新导入
    fps = json.load(open(fp_p, encoding="utf-8")) if os.path.exists(fp_p) else {}
    fp = lambda pth: [os.path.abspath(pth), os.path.getsize(pth), int(os.path.getmtime(pth))]
    todo = [it for it in items if a.force or it["key"] not in amap or fps.get(it["key"]) != fp(it["path"])]
    if todo and any(it["key"] in amap for it in todo):
        print("源文件变了，重新导入：" + "、".join(it["key"] for it in todo if it["key"] in amap))
    for i in range(0, len(todo), 40):
        batch = []
        for it in todo[i:i + 40]:
            f_ = fp(it["path"])  # 编号带上文件指纹：OpenMotion 同一个编号不会替换文件，源文件变了要换编号才会导入新文件
            x = {"itemId": f'{it["key"]}--{f_[1]}-{f_[2]}', "sourcePath": os.path.abspath(it["path"]), "name": it.get("name", it["key"])}
            if it.get("license"):
                x["licensePath"] = os.path.abspath(it["license"])
            batch.append(x)
        r = call("openmotion_import_assets", {"projectId": st["projectId"], "requestId": rid("import"), "items": batch})
        for x in r.get("items", []):
            key_ = x.get("itemId", "").split("--")[0]
            if x.get("status") == "completed":
                amap[key_] = x["path"]
                src_ = next((it["path"] for it in todo if it["key"] == key_), None)
                if src_:
                    fps[key_] = fp(src_)
            else:
                print(f"✗ {x.get('itemId')}: {x.get('status')} {x.get('error', '')}", file=sys.stderr)
        json.dump(amap, open(amap_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(fps, open(fp_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"assets.json：{len(amap)} 项（这次导入 {len(todo)} 项）")


def cmd_save(a):
    st = load_state(a.work)
    pid = st["projectId"]
    g = call("openmotion_get_project", {"projectId": pid})
    mode = "modify" if st.get("versionId") else "create"
    b = call("openmotion_open_preview", {"action": "begin", "projectId": pid, "requestId": rid("begin"), "mode": mode, "presentation": "background"})
    w = b["inlineWork"]
    files = [{"path": "index.html", "content": open(os.path.join(a.dir, "index.html"), encoding="utf-8").read()}]
    cdir = os.path.join(a.dir, "compositions")
    for f in sorted(os.listdir(cdir)):
        if f.endswith(".html"):
            files.append({"path": f"compositions/{f}", "content": open(os.path.join(cdir, f), encoding="utf-8").read()})
    if len(files) > 100:
        sys.exit("一次最多存 100 个文件，合并部分段落再存")
    e = call("openmotion_edit_project", {"projectId": pid, "requestId": rid("save"), "workId": w["id"], "expectedRevision": w["revision"],
                                         "expectedVersionId": w["versionId"], "summary": a.summary[:300], "presentation": "background", "files": files})
    v = e["version"]
    c = call("openmotion_open_preview", {"action": "complete_generation", "projectId": pid, "workId": w["id"], "requestId": rid("complete"),
                                         "expectedRevision": v["revision"], "expectedVersionId": v["versionId"]})
    st.update({"workId": w["id"], "versionId": v["versionId"], "versionNumber": v.get("versionNumber"), "revision": v["revision"],
               "projectDir": (g.get("project") or {}).get("directory")})
    save_state(a.work, st)
    print(f"已存第 {v.get('versionNumber')} 版 {v['versionId']}")


def link_dir(src, dst):
    if os.path.lexists(dst):
        return
    try:
        os.symlink(src, dst, target_is_directory=True)
    except OSError:
        if IS_WIN:  # 没有开发者模式时用目录联接
            subprocess.run(["cmd", "/c", "mklink", "/J", dst, src], check=True, capture_output=True)
        else:
            raise


def cmd_stage(a):
    st = load_state(a.work)
    g = call("openmotion_get_project", {"projectId": st["projectId"]})
    pdir = (g.get("project") or {}).get("directory")
    link_dir(os.path.join(pdir, "assets"), os.path.join(a.dir, "assets"))
    hj = os.path.join(a.dir, "hyperframes.json")
    if not os.path.exists(hj) and os.path.exists(os.path.join(pdir, "hyperframes.json")):
        shutil.copy(os.path.join(pdir, "hyperframes.json"), hj)
    print(f"{a.dir}/assets → {pdir}/assets")


def hf_cli():
    ins = install()
    return os.path.join(ins["appRoot"], "node_modules", "hyperframes", "bin", "hyperframes.mjs")


def cmd_lint(a):
    ins = install()
    r = subprocess.run([node(), os.path.join(ins["appRoot"], "scripts", "lint-project.mjs"), ins["appRoot"], os.path.abspath(a.dir)],
                       capture_output=True, text=True, encoding="utf-8", env=tool_env())
    out = r.stdout
    try:
        d = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        print(out[-4000:], r.stderr[-2000:])
        sys.exit(r.returncode)
    print(f"{'✓ 通过' if d.get('ok') else '✗ 未通过'}：{d.get('errorCount', 0)} 个错误、{d.get('warningCount', 0)} 个警告，查了 {d.get('filesScanned')} 个文件")
    for f in d.get("findings", []):
        print(f"  [{f['severity']}] {f['code']} · {os.path.basename(f.get('file', ''))}：{f['message'][:220]}")
    sys.exit(0 if d.get("ok") else 1)


def cmd_check(a):
    """全画面检查：用渲染器自带的完整检查（版面＋对比度＋可读性＋运行），在每段入场后、段尾和每个动画起止各取一帧。
    装饰层和设计上的叠放（进度条亮暗两层、金句前后两句）已在生成时标注，不算问题。
    分两档：「必须改」退出码 1；「要看」打印出来逐条判断，不挡。"""
    rep = os.path.join(a.dir, "build_report.json")
    segs = json.load(open(rep, encoding="utf-8"))["segments"] if os.path.exists(rep) else []
    times = set()
    for sid, kind, lay, s0, s1 in segs:
        d = s1 - s0
        times.add(round(s0 + min(1.3, d * 0.45), 2))
        times.add(round(s1 - 0.35, 2))
    if a.at:
        times |= {float(x) for x in a.at.split(",")}
    at = ",".join(f"{t:g}" for t in sorted(times)) or "1"
    r = subprocess.run([node(), hf_cli(), "check", os.path.abspath(a.dir), "--json", "--at", at, "--at-transitions",
                        "--max-transition-samples", "160", "--max-issues", "400", "--timeout", "20000"],
                       cwd=a.dir, capture_output=True, text=True, encoding="utf-8", env=tool_env())
    try:
        d = json.loads(r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1])
    except Exception:
        sys.exit("检查没跑起来：" + (r.stdout + r.stderr)[-1200:])
    seg_at = lambda t: next((s[0] for s in segs if s[3] - 0.01 <= t < s[4]), "?")
    names = {"content_overlap": "文字互相压住", "canvas_overflow": "超出画面", "text_box_overflow": "文字溢出容器",
             "clipped_text": "文字被裁掉", "text_occluded": "文字被盖住", "text_not_painted": "文字没画出来",
             "caption_zone_collision": "压到字幕区", "frame_out_of_frame": "出画", "contrast_aa_failure": "字和底色太接近",
             "line_unread": "停留太短来不及读", "text_below_floor": "字太小", "runtime_script_error": "脚本报错"}
    must, look = [], []
    mid = {round(t, 2) for t in (d.get("layout") or {}).get("transitionSamples") or []} - {round(t, 2) for t in times}
    for sec in ("runtime", "layout", "contrast", "craft"):
        for x in (d.get(sec) or {}).get("findings") or []:
            c, sev = x.get("code"), x.get("severity")
            if sev == "info" or c in ("clip_media_fit", "panel_out_of_canvas") or (c == "container_overflow" and "-pip" in (x.get("selector") or "")):
                continue  # 音效槽比音效长、底座和小窗的浮动外溢：渲染时自动处理，不是画面问题
            if c == "contrast_aa_failure" and all(round(t, 2) in mid for t in x.get("times") or [x.get("time") or 0]):
                continue  # 只在动画半途（淡入淡出）的帧上不够清楚，不算
            if c == "contrast_aa_failure":
                (must if x.get("ratio", 9) < 2.2 or sev == "error" else look).append(x)
                x["_note"] = f"{x.get('ratio')}:1，至少要 {x.get('requiredRatio')}:1"
            elif c in ("content_overlap", "text_occluded") and x.get("heldMs") is not None and x["heldMs"] < 300:
                look.append(x)  # 入场飞过标题这类，压住不到 0.3 秒
                x["_note"] = f"动画途中一闪，{int(x['heldMs'])} 毫秒"
            elif c == "text_occluded":
                (must if (x.get("coveredFraction") or 0) >= 0.3 else look).append(x)
                x["_note"] = f"盖住 {int((x.get('coveredFraction') or 0) * 100)}%"
            elif c == "line_unread":
                look.append(x)
                x["_note"] = f"只停 {x.get('seconds')} 秒，至少要 {x.get('floorSeconds')} 秒"
            elif c == "text_below_floor":
                m = re.search(r"renders at (\d+) ?px", x.get("message", ""))
                if m and int(m.group(1)) < 16:  # 风格里的小号字距英文是装饰；16px 以下手机上看不出是字
                    x["_note"] = f"{m.group(1)}px"
                    look.append(x)
            elif sev == "error" or c in names:
                must.append(x)
    show = lambda x: (f"  {x.get('time') or 0:6.2f}s [{seg_at(x.get('time') or 0)}] {names.get(x['code'], x['code'])}"
                      f"{('（' + x['_note'] + '）') if x.get('_note') else ''}：{x.get('selector', '')} "
                      f"{('↔ ' + x['containerSelector']) if x.get('containerSelector') else ''} 「{(x.get('text') or '')[:20]}」")
    lay = d.get("layout") or {}
    print(f"{'✓ 检查通过' if not must else '✗ 有必须改的问题'}：抽查 {len(lay.get('samples') or times)} 个时间点＋{len(lay.get('transitionSamples') or [])} 个动画衔接点，"
          f"必须改 {len(must)} 处，要看 {len(look)} 处")
    for x in must:
        print(show(x))
    if look:
        print("要看（逐条判断，是设计如此就在交付说明里交代）：")
        for x in look:
            print(show(x))
    sys.exit(1 if must else 0)


# ---------------------------------------------------------------- 安全区
# 1080×1920 画布上平台界面的遮挡和裁切（视频号实测＋通用 9:16 安全区示意图，见 references/04-人脸安全.md「平台安全区」）
SAFE = {"l": 60, "r": 1020, "top": 270, "bottom": 1483, "text": 72}
SAFE_BG = ["#hostwrap", "#hostscrim", ".bgbase", ".vig", ".grain", ".gradeov", ".motifc", "[data-layout-allow-overflow]", "[data-safe-bleed]",
           "[data-layout-ignore]", '[id$="-shade"]', ".streak", "video:not(.pipc video)"]  # 背景：允许出界（含装饰用的滚动条、光带）
SAFE_DOCK = [".dk", ".dkg", ".rule", ".chap", ".upd", ".badge"]  # 底座：不查底部线（左右单独按代码排）
CSS_EL = ("#main{background:#808080!important}#root{background:transparent!important}"
          + ",".join(f"{x},{x} *" for x in SAFE_BG + SAFE_DOCK) + "{visibility:hidden!important}"  # 子元素一起藏：播放器会给素材写行内 visibility
          '[style*="inset:0"]{background:transparent!important;background-image:none!important;box-shadow:none!important;border-color:transparent!important}')  # 整屏底色层：只去掉它自己的底色
CSS_TX = ("#main{background:#000!important}#root{background:transparent!important}"
          "*{background:transparent!important;background-image:none!important;border-color:transparent!important;box-shadow:none!important;"
          "filter:none!important;color:#fff!important;-webkit-text-fill-color:#fff!important;text-shadow:none!important;-webkit-text-stroke:0!important}"
          "*::before,*::after{background:transparent!important;background-image:none!important;border-color:transparent!important;box-shadow:none!important}"
          "img,video,svg,canvas,.pipc{visibility:hidden!important}"
          + ",".join(f"{x},{x} *" for x in SAFE_DOCK + ["[data-safe-bleed]"]) + "{visibility:hidden!important}")


def safe_variant(src, dst, css):
    """复制一份工程，每个 html 的样式末尾加一段 css（藏背景／只留文字），素材链回原工程。"""
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(os.path.join(dst, "compositions"))
    for f in ("index.html", "hyperframes.json"):
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), os.path.join(dst, f))
    for f in os.listdir(os.path.join(src, "compositions")):
        shutil.copy(os.path.join(src, "compositions", f), os.path.join(dst, "compositions", f))
    link_dir(os.path.realpath(os.path.join(src, "assets")), os.path.join(dst, "assets"))
    for f in ["index.html"] + ["compositions/" + x for x in os.listdir(os.path.join(dst, "compositions")) if x.endswith(".html")]:
        q = os.path.join(dst, f)
        t = open(q, encoding="utf-8").read()
        open(q, "w", encoding="utf-8").write(t.replace("</style>", css + "</style>", 1))


def cmd_safe(a):
    """平台安全区检查：除背景以外，字、脸、小窗、卡片、标签都要在安全区里。
    渲染两遍：一遍藏掉背景（实拍、底纹、全宽横条、人物画面、底座）、铺灰底，看元素有没有越线；
    一遍去掉所有底色和图片、文字刷白，看文字离左右边够不够远。
    必须改：元素进了左右 60 像素（视频号会裁掉：iPhone 每边约 49，主流安卓约 60）、顶部 270（状态栏和返回键）、
            底部 1483 以下（账号名、标题文案；底座不算）。要看：文字离左右边不到 72。"""
    from PIL import Image, ImageChops, ImageDraw
    d = os.path.abspath(a.dir)
    rep = os.path.join(d, "build_report.json")
    segs = json.load(open(rep, encoding="utf-8"))["segments"] if os.path.exists(rep) else []
    times = set()
    for sid, kind, lay, s0, s1 in segs:
        dd = s1 - s0
        times |= {round(s0 + min(1.3, dd * 0.45), 2), round((s0 + s1) / 2, 2), round(s1 - 0.35, 2)}
    if a.at:
        times |= {float(x) for x in a.at.split(",")}
    times = sorted(t for t in times if t >= 0)
    if not os.path.exists(os.path.join(d, "assets")):
        sys.exit("✗ out/assets 不存在：先跑 om.py stage")
    work = os.path.join(d, ".safe")
    jobs = []
    for mode, css in (("el", CSS_EL), ("tx", CSS_TX)):
        vd = os.path.join(work, mode)
        safe_variant(d, vd, css)
        fd = os.path.join(work, mode + "_frames")
        shutil.rmtree(fd, ignore_errors=True)
        jobs.append((mode, fd, subprocess.Popen([node(), hf_cli(), "snapshot", vd, "--at", ",".join(f"{t:g}" for t in times), "--no-end",
                                                 "-o", fd, "--timeout", "120000"], cwd=vd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=tool_env())))
    frames = {}
    for mode, fd, pr in jobs:
        out, err = pr.communicate()
        if pr.returncode:
            sys.exit(f"✗ 安全区抽帧失败（{mode}）：{err.decode('utf-8', 'ignore')[-600:]}")
        fs = sorted(f for f in os.listdir(fd) if f.startswith("frame-") and f.endswith(".png"))
        frames[mode] = [os.path.join(fd, f) for f in fs]
    seg_of = lambda t: next((sid for sid, kind, lay, s0, s1 in segs if s0 <= t < s1), "")

    def hits(img, bg, box, thr):
        reg = img.crop(box)
        m = ImageChops.difference(reg, Image.new("RGB", reg.size, bg)).convert("L").point(lambda v: 255 if v > thr else 0)
        bb = m.getbbox()
        n = m.histogram()[255]
        return (n, (bb[0] + box[0], bb[1] + box[1], bb[2] + box[0], bb[3] + box[1])) if bb and n > 40 else (0, None)
    raw, look, shots = [], [], []  # raw: (时间, 段, 区, 说明)
    rd = os.path.join(work, "report")
    shutil.rmtree(rd, ignore_errors=True)
    os.makedirs(rd)
    for t, fe, ft in zip(times, frames["el"], frames["tx"]):
        el = Image.open(fe).convert("RGB")
        tx = Image.open(ft).convert("RGB")
        W_, H_ = el.size
        zones = {"左边": (0, 0, SAFE["l"] - 3, H_), "右边": (SAFE["r"] + 3, 0, W_, H_),
                 "顶部": (0, 0, W_, SAFE["top"] - 3), "底部": (0, SAFE["bottom"] + 3, W_, H_)}
        bad = []
        for name, box in zones.items():
            n, bb = hits(el, (128, 128, 128), box, 40)
            if bb:
                bad.append((name, bb))
                raw.append((t, seg_of(t), name, f"{t:7.2f}s [{seg_of(t)}] {name}越过安全线：x {bb[0]}–{bb[2]}、y {bb[1]}–{bb[3]}"))
        for name, box in zones.items():  # 文字越线同样必须改（元素那遍里文字可能在被藏掉的容器里）
            n, bb = hits(tx, (0, 0, 0), box, 90)
            if bb and not any(b[0] == name for b in bad):
                bad.append((name, bb))
                raw.append((t, seg_of(t), name, f"{t:7.2f}s [{seg_of(t)}] {name}文字越过安全线：x {bb[0]}–{bb[2]}、y {bb[1]}–{bb[3]}"))
        for name, box in (("左边", (0, 0, SAFE["text"] - 2, H_)), ("右边", (W_ - SAFE["text"] + 2, 0, W_, H_))):
            n, bb = hits(tx, (0, 0, 0), box, 90)
            if bb and not any(b[0].startswith(name) for b in bad):
                bad.append((name + "文字", bb))
                look.append(f"{t:7.2f}s [{seg_of(t)}] 文字离{name}不到 {SAFE['text']} 像素：x {bb[0]}–{bb[2]}、y {bb[1]}–{bb[3]}")
        if bad:
            dr = ImageDraw.Draw(el)
            for x in (SAFE["l"], SAFE["r"]):
                dr.line([(x, 0), (x, H_)], fill=(255, 40, 40), width=3)
            for y in (SAFE["top"], SAFE["bottom"]):
                dr.line([(0, y), (W_, y)], fill=(255, 40, 40), width=3)
            for name, bb in bad:
                dr.rectangle(bb, outline=(255, 220, 0), width=5)
            pth = os.path.join(rd, f"{t:07.2f}s-{seg_of(t)}.png")
            el.resize((W_ // 2, H_ // 2)).save(pth)
            shots.append(pth)
    # 段尾（停稳以后）还越线的才算必须改；只在中途越线的多半是入场、出场动画，列「要看」
    last = {sid: round(s1 - 0.35, 2) for sid, kind, lay, s0, s1 in segs}
    at_end = {(sid, z) for t, sid, z, msg in raw if abs(t - last.get(sid, -1)) < 0.01}
    must = [msg for t, sid, z, msg in raw if (sid, z) in at_end or sid not in last]
    look = [msg + "（只在动画途中，段尾停稳后在线内）" for t, sid, z, msg in raw if not ((sid, z) in at_end or sid not in last)] + look
    print(f"{'✓ 安全区通过' if not must else '✗ 有元素越过安全线'}：抽查 {len(times)} 个时间点，必须改 {len(must)} 处，要看 {len(look)} 处")
    for x in must:
        print("  " + x)
    if look:
        print("要看（逐条判断）：")
        for x in look:
            print("  " + x)
    if shots:
        print(f"标出位置的图（灰底上只剩元素，黄框是越线的地方）：{rd}")
    sys.exit(1 if must else 0)


def cmd_snapshot(a):
    os.makedirs(a.out, exist_ok=True)
    r = subprocess.run([node(), hf_cli(), "snapshot", os.path.abspath(a.dir), "--at", a.at, "--no-end", "-o", os.path.abspath(a.out), "--timeout", "120000"],
                       cwd=a.dir, capture_output=True, text=True, encoding="utf-8", env=tool_env())
    print(r.stdout[-1500:], r.stderr[-1500:])
    sys.exit(r.returncode)


def cmd_preview(a):
    st = load_state(a.work)
    r = call("openmotion_open_preview", {"projectId": st["projectId"]})
    url = r.get("sessionUrl") or r.get("previewUrl")
    print(url)
    if a.open and url:
        webbrowser.open(url)


def cmd_export(a):
    st = load_state(a.work)
    pid = st["projectId"]
    r = call("openmotion_export_request", {"action": "request", "projectId": pid, "requestId": rid("export"), "workId": st["workId"],
                                           "versionId": st["versionId"], "expectedRevision": st["revision"], "audio": "required"})
    job = r["job"]["id"]
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        time.sleep(10)
        g = call("openmotion_get_project", {"projectId": pid, "exportJobId": job})
        ej = g.get("exportJob") or {}
        if ej.get("state") in ("completed", "failed", "expired", "cancelled"):
            ver = ej.get("verification") or {}
            for c in ver.get("checks", []):
                print(f"  {'✓' if c['status'] == 'passed' else '✗'} {c['name']}: {c.get('details', '')}")
            if ej["state"] != "completed" or not ver.get("file"):
                sys.exit(f"导出失败：{ej.get('state')} {json.dumps(ej.get('error', ''), ensure_ascii=False)[:600]}")
            os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
            shutil.copy(ver["file"], a.out)
            print(f"成片：{a.out}（技术校验 {ver.get('status')}）")
            return
        print(f"  … {ej.get('stage', ej.get('state'))} {int(time.time() - t0)}s", flush=True)
    sys.exit(f"导出超过 {a.timeout}s 还没完成，job {job}，稍后用 get_project 查")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("doctor")
    p = sp.add_parser("create"); p.add_argument("--work", required=True); p.add_argument("--title", required=True); p.add_argument("--req", required=True)
    p = sp.add_parser("import"); p.add_argument("--work", required=True); p.add_argument("--manifest", required=True); p.add_argument("--force", action="store_true")
    p = sp.add_parser("save"); p.add_argument("--work", required=True); p.add_argument("--dir", required=True); p.add_argument("--summary", default="图解口播生成")
    p = sp.add_parser("stage"); p.add_argument("--work", required=True); p.add_argument("--dir", required=True)
    p = sp.add_parser("lint"); p.add_argument("--dir", required=True)
    p = sp.add_parser("snapshot"); p.add_argument("--dir", required=True); p.add_argument("--at", required=True); p.add_argument("--out", required=True)
    p = sp.add_parser("check"); p.add_argument("--dir", required=True); p.add_argument("--at", help="另外加查的时间点，逗号分隔")
    p = sp.add_parser("safe"); p.add_argument("--dir", required=True); p.add_argument("--at", help="另外加查的时间点，逗号分隔")
    p = sp.add_parser("preview"); p.add_argument("--work", required=True); p.add_argument("--open", action="store_true")
    p = sp.add_parser("export"); p.add_argument("--work", required=True); p.add_argument("--out", required=True); p.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
