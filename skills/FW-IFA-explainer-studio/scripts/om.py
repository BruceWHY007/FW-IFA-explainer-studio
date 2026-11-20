# -*- coding: utf-8 -*-
"""OpenMotion 调用封装（macOS／Windows／Linux 通用）。直接调用 OpenMotion 自带的命令行入口，不依赖宿主是否加载了 MCP 工具。

  python om.py doctor                                   查环境：node、OpenMotion、ffmpeg、Chrome、Python 依赖
  python om.py create  --work W --title 标题 --req 需求    新建工程，编号记到 W/om_state.json
  python om.py import  --work W --manifest import.json  导入素材（视频、音频、图片、字体），生成 W/assets.json（键 → 工程内路径）
  python om.py save    --work W --dir OUT --summary 说明  把 build 出来的 index.html＋compositions 存成新版本
  python om.py stage   --work W --dir OUT                把工程素材链到 OUT/assets，供本地 lint／snapshot
  python om.py lint    --dir OUT
  python om.py snapshot --dir OUT --at 1.2,5.8,… --out 帧目录
  python om.py preview --work W                          打开 Studio 编辑器，打印网址
  python om.py export  --work W --out 成片.mp4            导出并等技术校验，复制成片

import.json 格式：[{"key":"aroll","path":"/绝对路径/aroll.mp4","name":"显示名","license":"/同目录/许可.txt（字体才要）"}]
"""
import argparse, json, os, platform, shutil, subprocess, sys, tempfile, time, uuid, webbrowser

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
    todo = [it for it in items if it["key"] not in amap or a.force]
    for i in range(0, len(todo), 40):
        batch = []
        for it in todo[i:i + 40]:
            x = {"itemId": it["key"], "sourcePath": os.path.abspath(it["path"]), "name": it.get("name", it["key"])}
            if it.get("license"):
                x["licensePath"] = os.path.abspath(it["license"])
            batch.append(x)
        r = call("openmotion_import_assets", {"projectId": st["projectId"], "requestId": rid("import"), "items": batch})
        for x in r.get("items", []):
            if x.get("status") == "completed":
                amap[x["itemId"]] = x["path"]
            else:
                print(f"✗ {x.get('itemId')}: {x.get('status')} {x.get('error', '')}", file=sys.stderr)
        json.dump(amap, open(amap_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"assets.json：{len(amap)} 项")


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
    p = sp.add_parser("preview"); p.add_argument("--work", required=True); p.add_argument("--open", action="store_true")
    p = sp.add_parser("export"); p.add_argument("--work", required=True); p.add_argument("--out", required=True); p.add_argument("--timeout", type=int, default=3600)
    a = ap.parse_args()
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
