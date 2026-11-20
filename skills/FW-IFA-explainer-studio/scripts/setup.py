# -*- coding: utf-8 -*-
"""IFA图解口播 一键安装（macOS／Windows／Linux）。先装基础 OpenMotion，再装本技能的依赖，最后自检。

基础：OpenMotion（开源本地动效视频工作台，本技能的工程、预览、编辑器、导出都靠它）
  GitHub   https://github.com/nexu-io/openmotion
  安装说明 https://github.com/nexu-io/openmotion/blob/main/docs/install.md（npm 发布版，本技能用这个）
  版本与校验 https://releases.open-design.ai/motion
  本技能在 @openmotion/app 0.1.1 上测试通过。源码安装需要 Node 26，不推荐。

用法：
  python setup.py --check                      只检查，不安装
  python setup.py                              装到 Claude Code（默认）
  python setup.py --host claude --host deepseek --profile desktop
  python setup.py --host codex                 Codex：如果已经用 claude 装过，只登记 MCP，不再复制一份技能
Windows 用 py 代替 python。
"""
import argparse, json, os, platform, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OM_VERSION = "0.1.1"
GITHUB = "https://github.com/nexu-io/openmotion"
SYS = platform.system()
IS_WIN = SYS == "Windows"


def say(ok, name, msg=""):
    print(f"{'✓' if ok else '✗'} {name:14s}{msg}")
    return ok


def run(cmd, **kw):
    print("  $ " + " ".join(cmd))
    return subprocess.run(cmd, **kw)


def om_home():
    if os.environ.get("OPENMOTION_HOME"):
        return os.environ["OPENMOTION_HOME"]
    if IS_WIN:
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "openmotion")
    return os.path.join(os.path.expanduser("~"), ".local", "share", "openmotion")


def node_version():
    n = shutil.which("node")
    if not n:
        return None
    v = subprocess.check_output([n, "--version"], text=True).strip().lstrip("v")
    return tuple(int(x) for x in v.split(".")[:3])


def install_hint(what):
    return {
        "node": {"Darwin": "brew install node@22（或 Volta：volta install node@22）", "Windows": "winget install OpenJS.NodeJS.LTS"}.get(SYS, "用发行版包管理器装 Node 22.18+"),
        "ffmpeg": {"Darwin": "brew install ffmpeg", "Windows": "winget install Gyan.FFmpeg（装完重开终端）"}.get(SYS, "apt install ffmpeg"),
        "chrome": {"Windows": "winget install Google.Chrome"}.get(SYS, "安装 Google Chrome"),
    }[what]


def main():
    sys.stdout.reconfigure(line_buffering=True)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只检查，不安装")
    ap.add_argument("--host", action="append", choices=["claude", "codex", "deepseek"], help="把 OpenMotion 接到哪个 Agent，可以写多次；默认 claude")
    ap.add_argument("--profile", default=None, help="DeepSeek Harness 的配置档名（--host deepseek 时用）")
    ap.add_argument("--version", default=OM_VERSION, help=f"OpenMotion 版本，默认 {OM_VERSION}（本技能测过的版本）")
    ap.add_argument("--upgrade", action="store_true", help="已装也按 --version 重装")
    a = ap.parse_args()
    hosts = a.host or ["claude"]
    print(f"基础：OpenMotion  {GITHUB}\n系统：{platform.platform()}\n")
    blockers = []

    # 1 Node
    nv = node_version()
    if not say(bool(nv and nv >= (22, 18)), "Node 22.18+", f"{'.'.join(map(str, nv)) if nv else '没有'}" + ("" if nv and nv >= (22, 18) else f" → {install_hint('node')}")):
        blockers.append("node")
    # 2 ffmpeg
    for exe in ("ffmpeg", "ffprobe"):
        if not say(bool(shutil.which(exe)), exe, shutil.which(exe) or f"没有 → {install_hint('ffmpeg')}"):
            blockers.append(exe)
    # 3 Python
    pv = sys.version_info[:2]
    say((3, 9) <= pv <= (3, 12), "Python", f"{pv[0]}.{pv[1]}" + ("" if (3, 9) <= pv <= (3, 12) else "（MediaPipe 需要 3.9–3.12；Windows 用 py -3.11 运行本脚本）"))
    try:
        import PIL  # noqa: F401
        say(True, "Pillow")
    except Exception:
        if a.check:
            say(False, "Pillow", "没有 → pip install pillow")
        else:
            run([sys.executable, "-m", "pip", "install", "pillow"])
    # 4 人物测量
    if SYS == "Darwin":
        if not say(bool(shutil.which("swiftc")), "人物测量", "系统 Vision（需要 swiftc）" if shutil.which("swiftc") else "缺 swiftc → xcode-select --install"):
            blockers.append("swiftc")
    else:
        try:
            import mediapipe  # noqa: F401
            say(True, "人物测量", "mediapipe")
        except Exception:
            if a.check or not (3, 9) <= pv <= (3, 12):
                say(False, "人物测量", "没有 mediapipe → pip install mediapipe==0.10.14 opencv-python-headless")
            else:
                run([sys.executable, "-m", "pip", "install", "mediapipe==0.10.14", "opencv-python-headless"])
    # 5 Chrome（没有也能用，OpenMotion 会自己下载，但走代理可能失败）
    sys.path.insert(0, HERE)
    from om import chrome  # noqa: E402
    say(bool(chrome()), "Chrome", chrome() or f"没有（OpenMotion 会自己下载；网络受限时先 {install_hint('chrome')}）")

    # 6 OpenMotion
    ins_p = os.path.join(om_home(), "install.json")
    cur = json.load(open(ins_p, encoding="utf-8")).get("version") if os.path.exists(ins_p) else None
    need = a.upgrade or cur is None
    say(bool(cur), "OpenMotion", f"{cur} @ {om_home()}" if cur else f"没装（{GITHUB}）")
    if cur and cur != a.version:
        print(f"  ⚠️ 已装 {cur}，本技能测的是 {OM_VERSION}；要换版本加 --upgrade --version X.Y.Z")
    if need and not a.check:
        if "node" in blockers:
            sys.exit("先装好 Node 22.18+ 再运行本脚本")
        npx = shutil.which("npx") or "npx"
        pkg = ["--yes", "--package", f"@openmotion/app@{a.version}", "openmotion", "setup"]
        skills_dir = os.path.join(os.path.expanduser("~"), ".agents", "skills")
        for h in hosts:
            if h == "claude":
                run([npx, *pkg, "--host", "claude", "--skills-dir", skills_dir], check=True, shell=IS_WIN)
            elif h == "deepseek":
                run([npx, *pkg, "--host", "deepseek", *(["--profile", a.profile] if a.profile else [])], check=True, shell=IS_WIN)
            elif h == "codex":
                if "claude" in hosts or os.path.exists(os.path.join(skills_dir, "openmotion-director")):
                    # 技能已在 ~/.agents/skills，Codex 会直接读到；再跑 setup --host codex 会多复制一份，只登记 MCP
                    ins = json.load(open(ins_p, encoding="utf-8")) if os.path.exists(ins_p) else None
                    if ins and shutil.which("codex"):
                        run(["codex", "mcp", "add", "openmotion", "--", shutil.which("node"), ins["launcher"]], shell=IS_WIN)
                    else:
                        print("  ⚠️ 先装 claude 宿主，再重跑 --host codex；或者没有 codex 命令行，手动登记 MCP")
                else:
                    run([npx, *pkg, "--host", "codex"], check=True, shell=IS_WIN)
        local_fix = os.path.join(os.path.expanduser("~"), ".local", "share", "openmotion-local", "use-local-tools.sh")
        if os.path.exists(local_fix):  # 本机若有本地化补丁（把 OpenMotion 指到本机 Chrome 和 ffmpeg），装完重新打上
            run(["bash", local_fix])
    elif need:
        print(f"  → 安装：python setup.py（会执行 npx --yes --package @openmotion/app@{a.version} openmotion setup --host claude --skills-dir ~/.agents/skills）")

    # 7 自检
    print("\n自检：")
    subprocess.run([sys.executable, os.path.join(HERE, "om.py"), "doctor"])
    if blockers:
        print(f"\n还缺：{', '.join(blockers)}。装好后重跑 python setup.py --check")
    else:
        print("\n基础环境就绪。可以先跑 python3 scripts/selftest.py 离线自检；"
              "然后发一段 30–60 秒的口播视频给 Agent（手机竖拍、对着镜头说话），让它按本技能试做一支。")


if __name__ == "__main__":
    main()
