---
name: FW-IFA-explainer-studio
description: 把一条真人口播原片做成「图解口播」竖版成片（财经知识类的图解包装：深色电影感、玻璃卡、金属大字、中英双语标题、人物小窗、透视图表、持续缓动），基于 OpenMotion 出可编辑工程。一套统一骨架（底座章节进度条、字幕位置、头顶标题不压人、人脸安全取景、缓动语法）＋五套风格包（炭金／档案／矿石／瓷蓝／霓虹），每支片按内容挑版式、母题图标和强调色，同风格也不出一模一样的片子。macOS／Windows 通用；使用前先装基础 OpenMotion（https://github.com/nexu-io/openmotion，scripts/setup.py 一键装）。用户说「图解口播」「知识口播包装」「财经口播加图解」「用 OpenMotion 做口播」「五套风格里选一套」时使用。没有原片、要从文稿生成整片，或只写口播稿，不归这里。
---

# FW-IFA 图解口播 · explainer-studio

真人口播原片 → OpenMotion 可编辑工程 → 成片。画面包装拆自 5 支财经知识类参考片（只借方法，不借内容和品牌），做成「一个骨架＋五套风格」。

下文命令都在**本技能目录**里运行（`cd` 到 SKILL.md 所在的文件夹）。Windows 把 `python3` 换成 `py -3.11`。

## 零、使用前准备：先装基础 OpenMotion，再走本技能

本技能建在 **OpenMotion** 上：工程、检查、预览、Studio 编辑器、导出都靠它。没装 OpenMotion 时，只能做前期、测量和生成源码。

- GitHub：https://github.com/nexu-io/openmotion
- 安装说明（npm 发布版，本技能用这个）：https://github.com/nexu-io/openmotion/blob/main/docs/install.md
- 版本号和校验值：https://releases.open-design.ai/motion
- 本技能在 `@openmotion/app` **0.1.1** 上测试通过。源码安装需要 Node 26，不推荐。

**第一步：运行安装脚本**

```
python3 scripts/setup.py --check      # 只检查，看缺什么
python3 scripts/setup.py              # 装：OpenMotion 0.1.1 接到 Claude Code＋本技能依赖＋自检
python3 scripts/setup.py --host claude --host codex --host deepseek --profile desktop   # 多个 Agent 一起接
```

脚本按顺序做：
1. 查 Node 22.18+ 和 ffmpeg。缺了只给出安装命令，不替你装。
2. 装 Pillow；Windows／Linux 还装 MediaPipe。
3. 找本机 Chrome。
4. 用官方命令装 OpenMotion：`npx --yes --package @openmotion/app@0.1.1 openmotion setup --host …`。
5. 跑 `om.py doctor` 自检。

接 Codex 时，如果已经用 claude 宿主装过，脚本只登记 MCP，不再复制一份技能，免得 Codex 读到两份。已经装过的机器，跑 `setup.py --check` 确认即可。

**第二步（可选）：离线自检**：`python3 scripts/selftest.py`。不用任何真人视频，用占位人形和渐变素材，把示例分镜表、版式变体、自动草稿在五套风格下各构建一遍，跑 lint 和版面检查，约 2 分钟；加 `--snapshot` 会抽帧。

**第三步：请用户发一段口播视频试做。** 安装和自检通过后，Agent 主动对用户说：

> 环境装好了。发一段 30–60 秒的口播视频给我试试：手机竖拍、对着镜头说一段话就行，最好头顶留一点空。再告诉我内容讲什么、想要哪种感觉（讲钱、讲机构、讲资源、讲品牌、讲科技），我按这个技能做一支样片，顺便帮你选风格。

收到视频后按第四节流程做；第一次试做可以只做 30–60 秒，先确认人物测量、头顶标题、小窗取景和底座都正常。

手动安装（脚本跑不了时）：

| 要装的 | macOS | Windows |
|-|-|-|
| Node 22.18+ | `brew install node@22` | `winget install OpenJS.NodeJS.LTS` |
| ffmpeg／ffprobe | `brew install ffmpeg` | `winget install Gyan.FFmpeg` |
| Python 3.9–3.12＋Pillow | 系统自带 3.9＋`pip install pillow` | `py -3.11 -m pip install pillow` |
| 人物测量 | 系统自带 Vision，不用装 | `py -3.11 -m pip install mediapipe==0.10.14 opencv-python-headless` |
| **OpenMotion 0.1.1** | `npx --yes --package @openmotion/app@0.1.1 openmotion setup --host claude --skills-dir ~/.agents/skills` | 同一条命令 |
| Chrome | 有就用本机的 | 有就用本机的；没有时 OpenMotion 会自己下载，走代理可能失败，先装 Chrome 更稳 |

详见 [references/05-OpenMotion与跨平台.md](references/05-OpenMotion与跨平台.md)。

## 一、统一骨架（五套风格都一样，不许改）

| 部件 | 规则 |
|-|-|
| 画布 | 1080×1920、30fps。0–1576 是人物画面区，图解段也只在这一区排版；1576–1920 是底座。 |
| 底座 | 全片常驻、盖在所有画面上面。平时显示章节进度条（3–6 章，编号＋章名，当前章点亮、下划线展开）；讲到需要更新或补充的事实时，换成「最新进展」卡（标题＋出处＋最多 2 个数字）。底座和人物画面交界处有一块署名牌。只放进度类和补充类信息，主要包装不放这里。 |
| 字幕 | 得意黑 60px、白字、风格色阴影。人物段固定在 1300；图解段跟着版式走（横条下方、小窗上方或旁边），撞到小窗会自动让开或缩小字号。 |
| 头顶标题 | 只放在头顶以上的空间。位置按实测头顶算，放不下就报错，改用身前卡片。头顶标题所在段自动关掉跳切推近。 |
| 人物段元素 | 两侧标签贴在下巴两侧；身前卡片、名牌、数字、贴纸放在下巴以下；任何元素碰到头部范围（头顶到下巴、脸宽外扩 5%，按推近后的位置）build 直接失败。 |
| 小窗 | 按这一段的人脸位置取景，脸完整、头顶留空，画面铺满窗口。圆窗直径 230–300，竖窗约 420×500 或 470×800。 |
| 缓动 | 卡片、小窗、标签持续上下浮动（±6–10px、周期 3–4 秒、相邻元素错开）；透视面板和倾斜图表轻摆 2–4°。不允许画面静止。 |
| 标题语法 | 中文大字＋字距拉开的英文副题；数字、图表一律标「示意 · ILLUSTRATIVE」，除非是核实过的真实数据。 |
| 跳切 | 人物段在剪辑点交替原尺寸／放大 1.08 倍，推近原点在人脸中心。 |
| 声音 | 人声 −16 LUFS；配乐侧链避让，约 −31 LUFS；成片约 −15 LUFS。入场有音效，图解段切入有过渡声。 |

## 二、五套风格

| 风格 | 参考题材 | 适合 | 材质与字 | 小窗 | 动作签名 | 招牌版式 |
|-|-|-|-|-|-|-|
| **炭金** tanjin | 黄金 | 宏观、市场、资产价格、上市估值 | 深炭底、金属渐变字、深色玻璃卡带虚线内框、粒子光球 | 大圆窗，左下 | 放大＋模糊收拢 | 大字横条、透视编号链、粒子金句 |
| **档案** dangan | 保险公司 | 行业史、机构、风险、案例复盘、保险 | 暖黑纸面、铬银衬线字、珐琅白卡、火漆印章、品红光带 | 白边圆窗，右上 | 横向收拢＋纸张落下 | 机构墙、文件高亮、母题图标滚动章节卡 |
| **矿石** kuangshi | 稀土 | 资源、地缘、产业链、大宗、政策博弈 | 石墨岩面、金框铭牌、酒红徽章、书法收尾 | 圆角方窗，居中在字幕下方 | 金色从左往右显出、3D 摆入 | 金框铭牌、A／B 对比、年份标尺横条 |
| **瓷蓝** cilan | 酒店品牌 | 品牌、消费、商业模式、公司拆解 | 雾蓝底＋母题图标纹、白纸立体图表、蓝玻璃面板、全息环 | 细白边圆窗，左上 | 翻牌＋卡片抛落 | 滚动数字、白纸柱图、环形关系图 |
| **霓虹** nihong | 游戏公司（横版改竖版） | 科技、互联网、娱乐、AI 产品、争议事件 | 黑紫底、霓虹描边、金色书法大字、斜切色块 | 霓虹边竖窗，左下 | 灯管闪亮、笔刷写出 | 倾斜面积图、霓虹产品排、书法金句 |

选风格按题材，不按心情：先看内容是「讲钱」「讲机构」「讲资源」「讲品牌」还是「讲科技」，再看账号登记里最近用过什么。**开工时问用户一次**（流程第 6 步）：用本人画面出五套对照图、标出推荐，用户选一套或回「你定」；用户在请求里已经点名风格就不问。每套有 3 种强调色（`accent`），同一账号连续两支用同一风格时换强调色。细节见 [references/01-五套风格.md](references/01-五套风格.md)。

## 三、统一，但不千篇一律：两层差异

**选定风格只定了外观**（底、字、卡片材质、小窗、默认动作）。同一套风格下，每支片、每一段的展示细节和动态都要按内容调。两个人用同一套风格做的片子，看得出是一个系列，但画面不能一样。

### 第一层：整支片（写分镜表时定）

1. **版式按内容挑**：27 个版式（人物段 10＋图解段 17，其中 5 个各有两种排法）。数字用滚动数字或对比，清单用编号链或层叠卡，人物用名牌，文件和新闻用文件高亮，机构用机构墙，对立概念用两侧标签，金句用金句卡。见 [references/02-版式库.md](references/02-版式库.md)。
2. **母题图标按题材选**：每支片从图标库（Lucide 1539 个）里按内容挑 2–3 个，铺进背景纹样、章节卡滚动条和立方体。比如保险用公文包＋盾牌，AI 用芯片＋铃铛＋K 线。`python3 scripts/icons.py 关键词` 搜图标。
3. **强调色**：每套 3 种，按题材选；同一账号连续两支同风格时换一种。
4. **版式变体**：编号链、柱状图、对比、宫格、层叠卡各有两种排法（竖向链／横向步骤，竖柱／横向排名，左右／上下，2×2／一大三小，斜向／左右交错），按内容长短或种子自动选，`data.variant` 可指定。
5. **实拍调色和声音跟风格走**：免费片库的实拍按本风格统一调色（档案偏暖加颗粒、矿石去饱和、霓虹偏紫……）；每套风格有自己的 6 个音效（程序合成，在 `assets/sfx/<风格>/`），档案是纸张和印章声，霓虹是合成器声。
6. **随机种子**：按片名生成，决定编号链、层叠卡、竖窗卡片的镜像方向、倾斜图表的倾斜方向、卡片抛落角度。
7. **账号登记**：`build.py --register` 记下风格、强调色、母题、图解版式序列。同账号下一支片子开场两段一样、收尾一样、母题一样，build 会提醒。

### 第二层：每一段（段落层参数，写在每段的 data 里）

| 参数 | 可选值 | 作用 |
|-|-|-|
| `*重点词*` | 任何标题、卡片、金句文字里用星号包住 | 换成本风格的强调色；字幕里出现同一个词也自动变色（另可在 plan 里写 `keywords`） |
| `tone` | good 绿／bad 红／warn 黄／info 蓝 | 这一段的点亮框、小标签、重点词、英文副题换成情绪色 |
| `energy` | calm／normal／punch | 平静：动作放慢 35%、缓动幅度减小；有力：动作加快、更冲、缓动幅度加大 |
| `enter` | blur／stretch／wipe／flip／flicker／rise／zoom | 标题入场方式，不写就用本风格的默认动作 |
| `card_enter` | slide／drop／swing／toss／pop／rise | 卡片入场方式，不写就用本风格的默认动作 |
| `reveal` | chars | 大字逐字出现（金句、结尾、头顶标题、超大字），速度按这句话在原声里说了多久自动算 |
| 时间写成 `"@关键词"` | 任何时间字段（t、t1、tl…） | 这个词被说出来的那一刻出现，`"@关键词+0.3"` 可加减偏移；build 从字级时间（chartimes.json）或字幕里找 |

**内容 → 调法**（写每一段时对照）：

| 这段在讲 | 建议 |
|-|-|
| 风险、亏损、代价、警告 | `tone: bad`，重点词标出来；警示字可以用印章或 `energy: punch` |
| 增长、机会、收益 | `tone: good`，数字用滚动数字 |
| 反问、转折、「但是」 | `energy: punch` ＋ `enter: zoom` |
| 结论、金句、收尾 | `reveal: chars`，`energy: calm` |
| 揭晓答案、公布数字 | `enter: wipe` 或滚动数字 |
| 列举、并列 | 卡片依次入场，`card_enter` 选 toss／drop／rise 之一，和上一个列举段不同 |
| 解释背景、慢慢讲 | `energy: calm` |
| 补充说明、中性信息 | `tone: info` |

**自动推断**：分镜表里没写的段落层参数，build 会按文字自动补上：
- 标题里有问号，用有力节奏加放大冲击；
- 出现风险词用红色调，出现增长词用绿色调；
- 短金句和结尾逐字展开；
- 章节卡用平静节奏。

推断结果写在 build_report.json 的 `auto_params` 里。写了的参数优先；整片不想自动推断，在 plan 里写 `"no_auto": true`。

**硬要求**：写分镜表时，至少一半的图解段要按内容设段落层参数（上表任意一项，或 `*重点词*`）。少于一半，build 会警告「没有按内容调整」。不能只靠自动推断。

### build 自动查的差异规则

- 图解版式不能连用（横条除外）。
- 同一版式最多用 2 次；横条最多 4 次，金句 3 次，章节卡 4 次。
- 至少用一个本风格的招牌版式。
- 90 秒以上的片子，图解版式至少 5 种。
- 两侧对立标签最多 2 处。
- 至少一半图解段设了段落层参数。

## 四、流程

每次开工前可以先跑 `python3 scripts/om.py doctor` 确认环境。

1. **转写**：要带字级时间戳的转写（格式见 03）。用户装了 IFA口播成片 技能时可以用它的 `scripts/ingest.py`；也可以用 whisper.cpp、FunASR 等。
2. **校对稿**：对照原稿改错字（专有名词、数字），写 `fix.json`；开头空白、现场对话、明显的废句写进 `drop`。字幕按本人实际说的话，用户给的文案一字不改。
3. **剪辑表＋查重说卡顿**：`python3 scripts/edl.py --transcript transcript.json --src 原片.mp4 --work 工作目录 --fix fix.json --verify`。
   - 转写模型常把「说到一半停住、又从头说一遍」合成一句，只看文字会漏，所以 edl.py 同时看三个信号：语速低于本人中位语速的 6 成、同一段声音在一句里出现两次、和后面 3 句文字很像。
   - 慢＋声音重复 → 自动剪掉第一遍，留最后完整的一遍（`--verify` 把留下的那遍单独再转写一次核对）；文字相似度 >0.7 → 删前一句；只有一个信号 → 进「待听清单」，不剪，交付时请人听。
   - 只留一遍完整的，不把几遍的碎片拼成一句；第一遍里后面没再说的铺垫要留。句间停顿超过 0.42 秒压到 0.26 秒。
   - 产物：`edl.json`、`transcript_edl.json`（剪掉第一遍的句子逐字时间已重排，下一步字幕用它）、`edl_report.json`。
4. **前期**（`scripts/prep.py`）：`cut` → `voice` → `captions --transcript 工作目录/transcript_edl.json` → `base --style 推荐风格`；B-roll 用 `broll`／`image` 逐条处理；最后 `mix` 配乐。
5. **量人物**：`python3 scripts/measure.py 工作目录/om_assets/aroll.mp4 geom.json`。macOS 用系统 Vision；Windows／Linux 用 MediaPipe（setup.py 已装）。
6. **请用户选风格（问一次）**：`python3 scripts/style_preview.py --work 工作目录 --geom geom.json --transcript transcript.json --title "开头标题|*重点*" --sub "副标题" --phrase "片中一句金句" --account 账号`，约 40 秒。
   - 出一张五套风格对照图：每套两格，用本人画面配头顶标题，再配一格图解金句。按转写内容标出推荐和备选，并写明理由（讲钱／机构／资源／品牌／科技各命中哪些词）。
   - 把图和推荐发给用户：「选哪套？回『你定』就用推荐的。」用户在请求里已经点名风格就跳过这一步。
   - 选定的不是第 4 步 `base` 用的风格时，重跑一次 `prep.py base --style 选定风格`。
7. **出分镜表草稿，再逐段改**：`python3 scripts/draft_plan.py --captions 工作目录/captions.json --chartimes 工作目录/chartimes.json --cuts 工作目录/cuts.json --style 风格 --title 片名 --host 名字 --out plan.json`。草稿按停顿分段、判断每段在讲什么（数字／列举／对比／问句／自我介绍／结论），按风格和差异规则建议版式和段落层参数，时间尽量写成 `@关键词`。所有 B-roll、配图、英文副题、章节名都是 TODO，素材键是 `band_TODO_1` 这样的占位，不改 build 会报错。逐段改：版式贴不贴内容、标题要不要换成更有力的说法、哪些词标 `*重点*`。写法见 [references/03-分镜表.md](references/03-分镜表.md)，示例见 `examples/demo/`。
8. **找 B-roll**：免费可商用片库（Pexels／Pixabay）。内容要对得上，宁可用抽象画面也不用张冠李戴的实拍。
9. **建工程**：`om.py create` → `om.py import --manifest 工作目录/import.json`（生成 `assets.json`）。
10. **构建**：`python3 scripts/build.py plan.json --assets assets.json --geom geom.json --out out`。有错误就改分镜表重来，警告要逐条看。
11. **自查**：`om.py stage` → `om.py lint`（必须 0 错误）→ `om.py check`（全画面版面检查：文字互相压住、字幕压到卡片、超出画面、溢出容器，必须 0 处）→ `om.py snapshot` 抽 12–15 帧，逐帧看：碰脸、空得太多、两段太像、整片的节奏和色调有没有随内容起伏。
12. **存版本、打开编辑器**：`om.py save` → `om.py preview --open`。用户在 Studio 里可以直接改字、调时间、换素材。
13. **导出**：`om.py export --out 成片.mp4`，等技术校验通过（14 项）。然后 `build.py --register` 登记。
14. **交付**：成片路径、编辑器网址、制作说明（剪了什么、风格和版式、素材授权、事实依据、已知限制），以及 `edl_report.json` 的待听清单（时间＋原话，请人听）。

各命令和跨平台细节见 [references/05-OpenMotion与跨平台.md](references/05-OpenMotion与跨平台.md)；人物测量和碰脸规则见 [references/04-人脸安全.md](references/04-人脸安全.md)。

## 五、交付前自验

- lint 0 错误；`om.py check` 0 处；build_report.json 里 0 错误，警告逐条有交代。
- 抽帧看过每一段；人物段没有任何元素压脸压头。
- edl.py 自动剪掉的每一处，`--verify` 复核相似度 ≥0.85；待听清单已写进交付说明。
- 事实性信息（日期、价格、数字）查过公开报道，最新进展卡标出处；本人说的话不改，用卡片补。
- 图表没有真实数据就标「示意」，不编数字。
- 成片里不出现参考账号的名字、logo、台标，只借方法。
- 素材都有授权记录：B-roll 来自可商用片库；字体 OFL；图标 ISC；音效、配乐用有授权记录的。

## 文件

- `scripts/`：setup.py 安装（先装 OpenMotion）、selftest.py 离线自检、prep.py 前期、edl.py 剪辑表和重说卡顿检查、measure.py＋measure.swift 人物测量、style_preview.py 五套风格对照图（开工时请用户选）、draft_plan.py 分镜表草稿、build.py 构建、om.py OpenMotion 调用（含 check 版面检查）、icons.py 图标搜索、gen_textures.py 底纹和 gen_sfx.py 音效（都已生成）
- `lib/tujie/`：core 骨架工具、styles 五套风格、frame 底座字幕和主时间线、layouts_host 人物段版式、layouts_graphic 图解段版式
- `assets/`：fonts（得意黑、Inter、Oswald、站酷小薇、志莽行书，均 OFL，许可证在旁边）、icons（Lucide，ISC）、textures 和 sfx（程序生成，无版权问题）
- `examples/demo/`：示例分镜表和字幕（占位内容）：plan_demo 全流程、plan_variants 版式变体；selftest.py 还会现场生成一份草稿一起测
- `references/06-参考片拆解.md`：5 支参考片拆出来的部件清单，加第六套风格时从这里开始
