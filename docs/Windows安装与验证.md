# Windows 安装与验证

## 2026-10-04 安装核验

个人版 0.1.0+personal.20261004 已通过官方 `codex plugin add` 更新。为保留开发目录中的未提交修改，本机市场改为引用独立发布目录；该目录是本次发布快照，后续更新需同步发布源再执行安装命令。未直接改写安装缓存或信任状态。

已核对安装后的运行脚本、提示词、Hook 定义与 manifest 和发布源一致。doctor 返回 App Server 正常，Stop 与 SessionEnd 均为 enabled=true、trustStatus=trusted。172 项离线测试通过，5 项合并交付案例通过真实模型评测。自然触发和桌面显示尚未验收；运行中的旧会话如未加载更新，可重启 App 后验证。

个人 fork 沿用上游 Python 实现与 Windows 文件锁。上游自动化和 CLI 连接的历史记录保留在下文，不代表本 fork 的新标题策略已通过真实模型、Stop Hook 或 Windows Desktop 显示验收。

## 安装条件

1. 安装 Python 3.10 或以上版本并加入 PATH，确保 `python --version` 可用。Windows Hook 使用 `python -X utf8`，不依赖 `py` Launcher。Codex Desktop 进程也必须能从 PATH 找到该解释器。
2. 安装并登录兼容的 Codex CLI。可使用 PATH 中的原生 `codex.exe`，或标准 npm 安装提供的 `codex.cmd`。
3. 将完整插件安装到本机 Codex，通过官方 Hook 管理入口检查并信任定义。安装插件本身不代表 Hook 已获信任。

插件会将标准 npm 入口解析到原生 `codex.exe`，支持 x64/ARM64 对应包及新旧 vendor 布局；不会通过 `cmd.exe` 转义命名参数。无法识别的自定义启动脚本需要显式指定原生可执行文件。

在插件目录的 PowerShell 中运行：

```powershell
python scripts/oil_codex_title.py doctor
python scripts/oil_codex_title.py configure --codex-bin 'C:\Codex\codex.exe'
```

第二条仅在默认检测找不到正确 CLI 时使用，替换为实际存在的路径。

## 安装个人 fork

以下路径是示例，替换为自己的目录。示例以 `D:\01_WORKS` 为本地市场根目录，插件源是其下的 fork clone。

### 获取指定分支

在 PowerShell 中运行：

```powershell
git clone --branch codex/personal-title-policy https://github.com/MaddogQ/oil-codex-title.git D:\01_WORKS\oil-codex-title-personal
Set-Location D:\01_WORKS\oil-codex-title-personal
git remote add upstream https://github.com/oil-oil/oil-codex-title.git
python --version
codex --version
python scripts/oil_codex_title.py doctor
```

已经克隆时直接进入现有目录并检查 `git branch --show-current` 和 `git remote -v`，不要重复克隆或覆盖本地修改。`upstream` 已存在时保留正确地址。

### 注册本地市场

在 `D:\01_WORKS\.agents\plugins\marketplace.json` 创建以下目录与文件。已有市场文件时添加插件条目，保留其他条目和市场名称，不覆盖原文件。

```json
{
	"name": "oil-title-personal",
	"interface": {
		"displayName": "Personal title policy"
	},
	"plugins": [
		{
			"name": "oil-codex-title",
			"source": {
				"source": "local",
				"path": "./oil-codex-title-personal"
			},
			"policy": {
				"installation": "AVAILABLE",
				"authentication": "ON_INSTALL"
			},
			"category": "Productivity"
		}
	]
}
```

然后注册市场并检查解析路径：

```powershell
codex plugin marketplace add D:\01_WORKS
codex plugin marketplace list
codex plugin add oil-codex-title@oil-title-personal --json
```

`source.path` 相对市场根目录解析，不能相对 `.agents/plugins` 目录解析。若已安装上游同名插件，先在插件目录禁用上游版本，避免两个命名 Hook 同时处理标题。仅注册市场还没有安装插件；上面的 `plugin add` 会安装并启用完整插件。也可以在 Codex Desktop 插件目录选择该本地市场安装。安装后核验 Hook 信任状态，界面未刷新时再重启 App。

此仓库本身没有市场 catalog，不能把 `codex plugin marketplace add MaddogQ/oil-codex-title` 当作完整安装。这里使用本地 catalog 指向指定分支的 clone。[OpenAI 官方插件文档](https://developers.openai.com/plugins/build/plugins)说明本地市场注册、相对路径和桌面安装流程。

### 启用并信任 Hook

1. 检查 `codex features list`，需要时运行 `codex features enable hooks`。
2. 在 Codex 的官方 Hook 管理入口检查并信任插件的 Stop 和 SessionEnd Hook。CLI 中使用 `/hooks`；Desktop 的入口随版本变化，通过实际界面确认。逐项核对，不把旧版 Stop 已信任当作新增 SessionEnd 已生效。
3. 运行 `python scripts/oil_codex_title.py doctor`。它检查程序与读取能力，不证明 Desktop 自然触发已经成功。
4. 在新对话正常提出具体任务，正常退出会话后检查日志、真实标题元数据与侧边栏显示。
5. 用“验收通过，收尾吧”检查 `✓ `，再提出新实质任务，核对 `✓ ` 移除且创建日期不变。

只信任读取当前话题、调用现有命名模型和通过 `thread/name/set` 改标题的 Hook。不创建归档计划，不主动扫描历史标题。插件安装、Hook 信任、真实自动触发与列表显示分别核验。

## 更新 fork 与同步上游

仅更新已发布的个人分支时，在干净工作树运行：

```powershell
Set-Location D:\01_WORKS\oil-codex-title-personal
git status --short
git pull --ff-only origin codex/personal-title-policy
```

维护个人策略并合并上游修复时，先确认工作树干净且当前目录没有其他正在写入的任务。保留未提交、未跟踪与忽略的必要文件，不自动 stash、reset 或 clean。

```powershell
git switch codex/personal-title-policy
git fetch upstream
git merge upstream/main
python -m unittest discover -s tests -v
git diff
git status --short
```

如有冲突，保留个人日期、9 类、completion 和旧标题不主动迁移的规则，同时核对并发、手工锁、stale-result 防护与上游模型调用方式。测试通过后，将合并结果提交并推送到 fork 的个人分支；不要向原作者提交个人策略 PR。

更新本地市场指向的源目录后，重启 Desktop，并在插件目录更新或重新安装本地插件。宿主可能加载安装缓存，核对实际安装版本，不直接编辑缓存文件。再检查 Stop 和 SessionEnd Hook 的信任与自然触发；仅更新 Git clone 不代表运行中的插件已经更新。SessionEnd 验收使用 CLI 正常退出，检查后台最终日志与标题读回；`/clear` 不保证立即结束旧会话。

## 已适配的行为

- Hook 使用 Windows 专用命令 `python -X utf8`，通过插件路径变量定位脚本。
- Windows 使用标准库 `msvcrt` 的内核字节锁；macOS/Linux 保留 `fcntl`。进程退出后自动释放锁。
- 子进程使用参数数组与 UTF-8 管道，支持路径中的中文、空格和 Unicode 标题。
- 后台 Codex 子进程不创建新的控制台窗口。
- 校验器拒绝将 Windows 盘符路径或 UNC 路径写入标题。

## 上游历史验收与本 fork 检查

自动化矩阵覆盖 Windows 的 Python 3.10/3.13，以及 macOS/Linux 的 Python 3.13。程序测试不调用付费模型；上游 Windows CI 另安装官方 Codex CLI，检查原生入口解析与 App Server 连接。

2026-09-14 的四组环境均通过全部 54 项测试，结果见 [跨平台验收记录](https://github.com/oil-oil/oil-codex-title/actions/runs/34799381646)。Windows CLI 检查使用 codex-cli 0.154.0，App Server 连接成功；CI 没有登录账号，也没有加载桌面 Hook。

账号环境中的最终检查仍需在 Windows Codex 中完成：新建正常话题、结束一轮有具体目标的对话、检查后台日志与实际显示标题，确认没有额外命名消息。没有这一步证据时，不宣称 Windows 桌面体验已经完整验收。

参考：[官方 Hook 的 Windows 命令与异步配置](https://learn.chatgpt.com/docs/hooks)、[Python Windows 文件锁](https://docs.python.org/3/library/msvcrt.html)。

## 本机安装记录（2026-10-01）

已通过官方 CLI 注册本地市场并安装 `oil-codex-title@oil-title-personal`，版本 `0.1.0+personal.20261001`。已读回 `installed=true`、`enabled=true`；桌面内置 CLI 的 `doctor` 返回 `hook.status=ready`，Stop 定义为 `enabled=true`、`trustStatus=trusted`。Windows Hook 使用现有 Python 3.12.9，无须安装 Launcher。144 项程序测试通过，包括中文和空格路径下执行实际 Windows Hook 命令。自然 Stop 触发与 Desktop 显示仍需单独验证。
