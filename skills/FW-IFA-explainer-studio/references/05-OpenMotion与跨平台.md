# OpenMotion 调用与跨平台

## 为什么基于 OpenMotion

- 交付的是**可编辑工程**：Studio 里可以直接改字、调时间、换素材，每次保存都是一个版本，可以回退。
- 导出自带 14 项技术校验（尺寸、帧率、时长、音轨、完整解码、首中尾定位）。
- 三个宿主都能用：Claude Code、Codex、DeepSeek Harness 都装了同一份 OpenMotion。

`scripts/om.py` 直接调用 OpenMotion 自带的命令行入口（`npm-installer.mjs call 工具名 --args-file`），不依赖宿主有没有加载 MCP 工具，三个宿主、两个系统都一样用。

## 命令

| 命令 | 做什么 |
|-|-|
| `om.py doctor` | 查 node、OpenMotion、ffmpeg、Chrome、人物测量依赖、Pillow |
| `om.py create --work W --title 标题 --req 需求` | 新建工程，编号写进 `W/om_state.json` |
| `om.py import --work W --manifest W/import.json` | 导入素材（字体带许可证），生成 `W/assets.json`；已导入的跳过，`--force` 重导 |
| `om.py save --work W --dir out --summary 说明` | 开工作轮次 → 写入 index.html 和全部 compositions → 完成，记下新版本号 |
| `om.py stage --work W --dir out` | 把工程素材目录链到 `out/assets`，本地 lint、抽帧用 |
| `om.py lint --dir out` | OpenMotion 自带检查，必须 0 错误 |
| `om.py snapshot --dir out --at 2.6,6.6,… --out 帧目录` | 按时间抽帧，生成 PNG 和总览图 |
| `om.py check --dir out` | 完整检查（渲染器自带的 check，约 35 秒）：每段入场后、段尾和每个动画起止各取一帧，查文字互相压住或被盖住、超出画面、溢出容器、字和底色对比度、停留时长、字号。分两档：「必须改」退出码 1；「要看」只打印（被盖住不到三成、对比度略低、停留略短、16px 以下的小字）。动画半途的对比度、音效槽长度、小窗浮动外溢不算问题；装饰层和设计上的叠放已在生成时标注 |
| `om.py safe --dir out` | 平台安全区检查：渲染两遍（一遍藏掉背景铺灰底，一遍只留文字），查元素有没有越过左右 60、顶部 270、底部 1483（底座不算），文字离左右边是否不到 72。段尾停稳后仍越线的「必须改」（退出码 1），只在动画途中越线的「要看」。越线的帧存在 `out/.safe/report/`，灰底上只剩元素、黄框标出越线的地方。见 04-人脸安全.md 第 5 节 |
| `om.py preview --work W --open` | 打开 Studio 编辑器 |
| `om.py export --work W --out 成片.mp4` | 导出、等技术校验、复制成片（63 秒样片约 80 秒） |

导入清单 `import.json` 由 `prep.py` 各步骤自动累积，格式：`[{"key", "path", "name", "license"}]`。

剪辑表和重剪不走 OpenMotion，见 [07-重说与口误.md](07-重说与口误.md)：`edl.py` 找重说、出剪辑表（`--scan` 只查不剪），`recut.py` 改了剪辑表以后一条命令重跑到检查。两者都要 whisper-cli 和 `~/.cache/whisper-cpp/` 下的模型（Windows 上 IFA口播成片 的 setup.py 把 whisper-cli 放在 `~/.cache/ifa-koubo/bin/`，edl.py 会去那里找；也可以设环境变量 `WHISPER_MODEL` 指定模型）。

## 安装

基础是 OpenMotion：GitHub https://github.com/nexu-io/openmotion ，npm 发布版安装说明 https://github.com/nexu-io/openmotion/blob/main/docs/install.md ，版本和校验值 https://releases.open-design.ai/motion 。

最省事的是运行 `scripts/setup.py`（先 `--check` 看缺什么）。它装 OpenMotion 0.1.1（本技能测过的版本）和本技能的依赖，最后自检。下面是手动步骤。

### macOS

```bash
brew install ffmpeg                                   # 有就跳过
npx --yes --package "@openmotion/app@0.1.1" openmotion setup --host claude --skills-dir ~/.agents/skills   # 需要 Node 22.18+
python3 ~/.agents/skills/IFA图解口播/scripts/om.py doctor
```

OpenMotion 默认装在 `~/.local/share/openmotion`。om.py 调用时会把本机的 Chrome 和 ffmpeg 告诉 HyperFrames，不另外下载。

### Windows

```powershell
winget install OpenJS.NodeJS.LTS        # Node 22.18+
winget install Gyan.FFmpeg              # ffmpeg / ffprobe 进 PATH
winget install Google.Chrome            # 没有也行，HyperFrames 会自己下载一份
npx --yes --package "@openmotion/app@0.1.1" openmotion setup --host claude --skills-dir ~/.agents/skills
py -3.11 -m pip install mediapipe==0.10.14 opencv-python-headless pillow
py ~\.agents\skills\IFA图解口播\scripts\om.py doctor
```

- OpenMotion 装在 `%LOCALAPPDATA%\openmotion`；`om.py` 读它的 `install.json` 找应用和数据目录，也可以设 `OPENMOTION_HOME`。
- 人物测量用 mediapipe（Windows 没有 Vision）。
- Chrome 按 `Program Files`、`Program Files (x86)`、`LOCALAPPDATA` 三处找；都没有可以设 `HYPERFRAMES_BROWSER_PATH`。
- `om.py stage` 链素材目录：有权限就建符号链接，没有就用目录联接（mklink /J），不需要管理员。
- 音效默认读 `~/.agents/skills/video-shotcraft/template/public/audio`，没有这个技能就设 `TUJIE_SFX_DIR` 指到放 6 个 mp3 的目录；都没有就不加音效，其他照常。
- 路径里有中文和空格没问题，脚本都用参数列表调用，不拼命令行字符串。

**状态**：Windows 流程按 OpenMotion 和各依赖的官方 Windows 支持写成，MediaPipe 测量在 macOS 上实测过，Windows 真机还没跑过。第一次在 Windows 上用时先跑 `setup.py --check`，再跑 `selftest.py --snapshot`，最后请用户发一段真实口播试做一支。

## 常见问题

- **lint 报 `media_missing_id`**：视频没有 id 会冻结。版式代码里每个 `<video>` 都要有 id。
- **lint 报 `gsap_non_transform_motion`**：不要做字距、宽高、left/top 动画，逐帧渲染会发抖；用 x／y／scale／opacity／clipPath。
- **lint 报 `gsap_cold_seek_hidden_fromto_missing_reveal`**：初始隐藏的元素，fromTo 的终点里要写 `opacity:1`。
- **save 报版本冲突**：别人在 Studio 里改过。先 `om.py preview` 看改了什么，要保留就把改动合进分镜表再 build。
- **导出超时**：`om.py export` 默认等 3600 秒，超时会打印导出任务编号；导出在 OpenMotion 后台继续跑，成片在 OpenMotion 数据目录的 `exports/任务编号/` 下。
- **使用数据上报**：`om.py` 调用时设了 `OPENMOTION_TELEMETRY=0`。
