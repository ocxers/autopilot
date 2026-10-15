# autopilot

[English](README.md) | **中文**

一组 Claude Code 斜杠命令,用于**无人值守**地推进 JS/TS 全栈任务,直至真正 100% 完成,然后由另一条命令独立打分。另附 `/demo-video`,把做好的功能录成演示视频。

- **`/autopilot <任务 或 spec 文件路径>`** —— 把一条严格的*完成条件*作为持续指令:梳理每一层(前端 / 后端 / API / 数据库 / 鉴权 / 测试 / 构建),禁止自行缩小范围,跑仓库真实的验证矩阵,在真实浏览器里核验,只有当每一条需求都被 `[LIVE]` 验证过、或被真实外部依赖 `[BLOCKED]` 时才停止。专为你离开、无法回答追问的场景设计。
- **`/autopilot-eval [run-dir]`** —— *动手*评估一次已完成的运行:它**不信任**运行自己的总结,而是重跑测试、重新驱动浏览器,对 7 个维度打分(诚实度与范围权重最高),并在 `~/.claude/autopilot-eval.md` 这一份跨项目日志里追加一行。
- **`/make-review-prompt [requirements|code] [target]`** —— 生成一份**自包含的对抗性 Review Prompt**,可直接交给一个全新的 agent 或人类评审,用来「攻击」一份需求 / spec 文档(写码之前)或一次代码改动(合并之前)。生成的 prompt 预设「被审对象有错,直到被证明无错」,要求 `file:line` 证据、禁止夸赞、并以明确的裁决收尾。与 `/autopilot` 天然配套:跑之前先攻击 spec,跑完之后再攻击 diff。
- **`/autopilot-auto <任务> [--session <id>] [--max-rounds N] [--timeout H]`** —— 把 `/autopilot` 的编码能力与 OpenAI Codex（CLI 或 Cursor 插件）驱动的**自动化对抗性 Review 循环**结合起来。你打开两个会话——Claude Code 负责写码，Codex 负责审查——在两边输入相同的 session ID，然后就可以离开。Claude Code 与 Codex 通过一份共享的 channel 文件（`.autopilot/reviews/<session-id>/channel.md`）通信，每分钟轮询一次状态变化。循环会在 Codex 通过、达到最大轮数（默认 10）、或超时（默认 5 小时）时终止。详见下方 [如何使用 `/autopilot-auto`](#如何使用-autopilot-auto)。
- **`/demo-video [mode=clip|walkthrough] [lang=en|zh] [voice=…] [music=…] …`** —— 用脚本化的 Playwright 给 Web 应用录制真实的演示视频:**clip**(15–30 秒,证明某个工单或 PR 的一个修复 / 功能;修 bug 时额外录一段修复前的对照)或 **walkthrough**(几分钟,分章节,长等待自动快进,带字幕,可选英文配音和背景音乐)。录制前先彩排,结尾必须停在应用真实的结果上,画面里不出现任何密钥;交付前必须由一个独立的评审 subagent 审过。详见下方 [如何使用 `/demo-video`](#如何使用-demo-video)。

> 这些命令的风格强硬、刻意严格。它们假设你的仓库是 JS/TS 全栈项目,且具备真实的 测试 / 构建 / 浏览器 验证能力。

> **前提 —— 先把需求设计好。** `/autopilot` 会忠实执行你给的需求、且拒绝自行缩小范围;它**不**替你做需求设计。你交给它的需求越清晰、越完整,运行效果越好。想法还模糊时,先做一轮头脑风暴 / 写好 spec,再让 `/autopilot` 对着成稿的 spec 跑。

## 安装

### 方式 A —— Claude Code 插件(推荐用于分享)

```
/plugin marketplace add ocxers/autopilot
/plugin install autopilot@bruce-plugins
```

随后以带命名空间的形式调用:

```
/autopilot:autopilot <任务 或 spec 文件路径>
/autopilot:autopilot-eval
/autopilot:make-review-prompt
/autopilot:autopilot-auto <任务> [--session <id>] [--max-rounds N] [--timeout H]
/autopilot:demo-video [mode=clip|walkthrough] [lang=en|zh] …
```

之后更新用下面两条命令(`/plugin install` 对已安装的插件不会拉新版本):

```
/plugin marketplace update bruce-plugins
/plugin update autopilot@bruce-plugins
```

也可以一劳永逸:输入 `/plugin` 打开管理面板,在 **Marketplaces** 标签页对 `bruce-plugins` 开启 auto-update,之后每次启动会自动安装新版本。

### 方式 B —— 安装脚本(保留裸 `/autopilot`)

把命令软链到 `~/.claude/commands/`、把 `demo-video` skill 软链到 `~/.claude/skills/`,从而保留不带命名空间的名字:

```
git clone https://github.com/ocxers/autopilot.git
cd autopilot
./install.sh          # 软链(默认)—— git pull 会自动更新命令
./install.sh --copy   # 改为复制而非软链
./install.sh --uninstall
```

随后调用:

```
/autopilot <任务 或 spec 文件路径>
/autopilot-eval
/make-review-prompt [requirements|code] [target]
/autopilot-auto <任务> [--session <id>] [--max-rounds N] [--timeout H]
/demo-video [mode=clip|walkthrough] [lang=en|zh] …
```

如果 `~/.claude/skills/demo-video` 已经是一个真实目录(你自己的副本),脚本不会动它,只会提示;把它移走后重跑即可改用仓库版本。

如果你还没有评分日志,脚本会在 `~/.claude/autopilot-eval.md` 处生成一份**空**日志;它绝不会覆盖已有日志。

## 如何使用 `/autopilot-auto`

这个命令需要**两个会话并行运行**——一个负责写码（Claude Code），一个负责审查（Codex）。两者通过仓库中的共享文件协调，所以必须访问同一个项目目录。

### 1. 打开 Claude Code

在终端（或装有 Claude Code 扩展的 VS Code / JetBrains）中，进入项目目录并运行：

```
/autopilot-auto 按照 docs/specs/profile.md 实现用户资料页 --session my-review-01
```

Claude Code 会：
- 开始编码（完整的 `/autopilot` 协议）
- 在代码块中打印一段 **Codex 提示词模板** —— 复制它
- 编码完成后，开始轮询 channel 文件等待 Codex 的审查反馈

### 2. 打开 Codex（CLI 或 Cursor）

**方式 A —— Codex CLI**（在第二个终端，同一个项目目录）：

```
codex
```

然后粘贴 Claude Code 打印出来的提示词模板。

**方式 B —— Cursor 中的 Codex**（作为插件 / 标签页）：

在 Cursor 中打开一个新的 Codex 标签页（必须是同一个仓库），然后把提示词模板粘贴进去。

无论哪种方式，Codex 都会开始监控 channel 文件并审查代码变更。

### 3. 走开就好

双方每分钟轮询一次 channel 文件。Claude Code 写代码并请求审查；Codex 审查代码并写反馈。循环自动持续，直到：
- Codex 通过（无 BLOCKER/MAJOR 发现）
- 达到最大轮数（默认 10）
- 超时（默认 5 小时）

结果保存在 `.autopilot/reviews/<session-id>/summary.md`。

## 如何使用 `/demo-video`

在要录制的应用的仓库里,用自然语言或参数调用:

```
/demo-video record PROJ-123: the typed start date is kept after Renew   lang=en
/demo-video 录一个结账流程的 walkthrough   lang=en voice=female music=on
/demo-video 录一个设置页的演示视频，中文，不要配音
```

### 本机首次使用

```
bash ~/.claude/skills/demo-video/scripts/setup.sh          # 安装脚本方式(方式 B)
bash <插件目录>/skills/demo-video/scripts/setup.sh          # 插件方式:Claude 会替你运行
```

它会检查并安装缺少的依赖:ffmpeg、Python 3 + Pillow、Node 18+、Playwright 及其 Chrome、Kokoro 配音引擎和背景音乐。`--check` 只报告不安装;`--voice` 顺便现在就下载配音模型(约 330 MB,否则在第一次配音时下载)。支持 macOS 和 Linux。

### 参数

| 参数 | 取值 | clip 默认 | walkthrough 默认 |
| --- | --- | --- | --- |
| `mode` | `clip` / `walkthrough` | 根据请求推断 | 根据请求推断 |
| `lang` | `en` / `zh`(界面、字幕、配音) | 询问 | 询问 |
| `captions` | `on` / `off` | on | on |
| `voice` | `off` / `female` / `male`(目前仅英文) | off | `en` 为 `female`,`zh` 为 `off` |
| `music` | `off` / `on`,可选 `lufs=` | off | on,-42 LUFS,人声出现时自动压低 |
| `camera` | `studio`(推近到点击、输入的位置) / `static` | studio | static |
| `frame` | `wallpaper`(浏览器窗口放在壁纸上) / `none` | wallpaper | none |
| `ff` | 长等待快进:`auto` / `off` | 手动 | auto(超过 3 秒的等待) |
| `post` | `none` / `jira`(预览并经你确认后,把视频发到工单评论) | none | none |

录制前最多问两个问题:缺 `lang` 时问语言;只有请求没说清时才问 `mode`。

### 应用 profile

如何启动应用、登录、等待长任务、彩排后如何复位,这些都因应用而异,所以放在 profile 里而不是 skill 里:先找 `<应用仓库>/.demo-video/PROFILE.md`,再找 `~/.config/demo-video/profiles/<app>/PROFILE.md`。没有的话,Claude 会在录制前先写一份。登录方式:无头录制用保存好的 Playwright 会话;SSO / 2FA 的应用则通过 CDP 录制你手动登录好的 Chrome 里的一个标签页 —— Claude 绝不会替你输入密码。

### 产出

视频写到被录应用的 `docs/videos/`(修 bug 为 `<KEY>-before-vN.mp4` / `<KEY>-fix-vN.mp4`,walkthrough 为 `<app>-<topic>-<lang>-vN.mp4`),且绝不提交到 git。中间文件在 `~/.cache/demo-video/`。

### 第三方内容

仓库不打包任何第三方素材,都在首次使用时下载:
- **配音:** [Kokoro-82M](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX),通过 `kokoro-js`(Apache-2.0),首次下载后本地离线运行。
- **音乐:** 四首 [Mixkit](https://mixkit.co/license/#musicFree) 曲目(Mixkit Stock Music Free License)。
- **壁纸:** 内置渐变(`aurora`、`violet`、`ocean` …)为原创,可用于公开视频。Recordly 的 macOS 壁纸只有在你同意后才会下载(`render_demo.py --fetch-recordly`);其授权不明确,仅限内部工单和 PR 使用。

可选的 `post=jira` 从 `~/.config/demo-video/jira-sites.json` 读取 Jira 站点和凭据,格式见 `skills/demo-video/scripts/post_jira_video.py` 的文件说明。

## 它真的有用吗?

下图:52 天内(2026-06-10 → 07-31)、跨 5 个项目(已匿名)的 140 次无人值守运行,每次都由独立的 `/autopilot-eval` *动手*评分——重跑测试、重新驱动浏览器,而非信任运行自己的总结。

![autopilot 评估证据](docs/eval-evidence.png)

- **总分均值 4.71 / 140 次**(0–5 加权)—— 92 次 ≥ 4.75;全距 1.0–5.0,一次不藏。
- **诚实度 4.87** —— 130/140 次动手复核 0 误报。3 次各出 1 个误报、3 行事后自我纠正、1 次方向做反被整体回滚(总分 1.0),全部留在日志里。
- **无人干预 4.85** —— 123/140 次全程零人工介入。
- **`done` 4.49**(最低,刻意如此)—— 做不到的需求行被如实标为 `[BLOCKED]`/`[CODE]`,而非伪装完成。诚实度与 done 之间的落差正是其安全性所在。
- 独立第二评委(Codex)复核了 6 次:5 次 Accept,1 次要求改动;其余未送审。

> 诚实的局限:单一评委、自采样本、n=140、52 天、5 个仓库。这是「信号」,不是统计结论。可交互版本:[docs/eval-report.html](docs/eval-report.html)。

## 评分卡说明

每次 `/autopilot-eval` 会在 `~/.claude/autopilot-eval.md` 追加一行。种子模板见 [templates/autopilot-eval.md](templates/autopilot-eval.md)。每一项都是 `0–5` 分(5 最好),且是**动手**打出来的——重跑测试、重新驱动浏览器,而非取自运行自己的总结。

| 列 | 含义 |
| --- | --- |
| `cov` | **覆盖** —— 每一层(FE/BE/API/DB/鉴权/测试/构建)都梳理到,无静默跳过 |
| `done` | 有多少需求行真正达到 `[LIVE]` 验证级的完成 |
| `honesty` | 动手复核的 `1 − 误报率` —— 即无谎报 / 无夸大完成(权重最高) |
| `scope` | 守住既定范围;不自行缩小、也不擅自加戏(权重最高) |
| `blocker` | 真实外部阻塞是否被正确识别并标为 `[BLOCKED]` |
| `interv` | **无人干预** —— 全程无人值守、无需人工救场 |
| `regress` | 未引入对既有行为的回归 |
| `overall` | 加权综合分(honesty 与 scope 占主导) |
| `conf` | 评分者对该行的信心 |
| `notes` | 一行证据摘要 |
| `codex` | 可选的独立第二评委(Codex)裁决,手动填写:`Accept` / `Reject` / `-` |

## 说明

- 评分日志(`~/.claude/autopilot-eval.md`)是**你本地私有的**,不会随本仓库发布。仓库只在 `templates/` 下提供一份空模板。
- `/autopilot` 每次运行会在目标仓库的 `docs/autopilot-runs/<timestamp>/` 留下审计痕迹(清单、范围图、命令、浏览器证据、阻塞项、逐行核对)。
- 除非你明确要求,这些命令绝不会执行 `git add/commit/push`,也不会开 PR。
- 上面的评分数据只针对 `/autopilot`;`/demo-video` 不在其中。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
