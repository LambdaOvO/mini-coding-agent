<div align="center">

# Mini Coding Agent

**一个可以在终端中读取、创建、修改代码并运行项目命令的 mini agent。**

Python 3.12+ · OpenAI-compatible SDK · DeepSeek · Windows 原生优先

</div>

## 能做什么

- 用自然语言描述需求，在交互式终端持续对话，或执行一次任务后退出。
- 列目录、按关键字搜索代码、分段读取文件。
- 创建文件和父目录，精确替换已有代码；修改前显示 Diff。
- 运行你批准的测试、构建、语法检查等项目命令，并把结果交给模型继续修复。
- 修改前检查文件版本，防止覆盖等待确认期间的外部编辑。
- 默认只读；编辑和命令通过启动参数显式启用。
- 拒绝操作立即停止本轮；Ctrl+C 中断当前任务并回收正在执行的命令。
- 不使用 Agent 框架，核心循环、工具分发、权限和进程管理都在源码中。

这是面向自己理解的本地小项目的实现，不是完整复刻 Claude Code。原来的固定 demo 检查保留在教学示例中，正式 CLI 使用通用 `run_command`，不要求你预先编写专用验证脚本。

## 快速开始：从 GitHub Release 安装

以下流程面向 Windows PowerShell。下载发布附件即可安装，无须克隆源码仓库；安装时需要 uv、Python 3.12，以及用于下载依赖的网络连接。发布附件是 Python wheel 安装包，运行环境由工具安装器管理。

### 1. 准备 uv 和 Python

按照 [uv 官方安装说明](https://docs.astral.sh/uv/getting-started/installation/) 安装 uv，重新打开 PowerShell，检查是否可用：

```powershell
uv --version
```

没有 Python 3.12 时，可通过 uv 安装；已有可用的 3.12 时跳过这一步：

```powershell
uv python install 3.12
```

### 2. 下载发布附件

打开 [Releases 页面](https://github.com/LambdaOvO/mini-coding-agent/releases)，在所选版本的 **Assets** 中下载下面两个文件，并放在同一个目录：

```text
mini_coding_agent-0.1.0-py3-none-any.whl
requirements.lock.txt
```

此安装流程使用手动上传的两个附件；GitHub 自动提供的 `Source code (zip)` 和 `Source code (tar.gz)` 是源码归档。其他版本请使用该版本配套的 wheel 和依赖文件。

### 3. 安装命令行工具

在下载目录打开 PowerShell，执行：

```powershell
uv tool install --python 3.12 --constraints .\requirements.lock.txt .\mini_coding_agent-0.1.0-py3-none-any.whl
mini-coding-agent --help
```

`--python 3.12` 选择工具环境的解释器，`--constraints` 限制运行依赖版本，最后的 `.whl` 是要安装的程序。`.\` 表示当前目录，因此运行安装命令时，这两个文件应位于终端的当前目录。

安装器会生成 `mini-coding-agent.exe` 命令入口。之后在任意目录都可直接使用，无须 `uv run`，也不依赖源码仓库或它的 `.venv`。

如果提示找不到命令，执行 `uv tool update-shell`，然后重新打开 PowerShell 或 PyCharm 的终端。安装方式见 [uv 工具安装文档](https://docs.astral.sh/uv/guides/tools/)。

### 4. 启动并配置密钥

先准备一个已经存在的目标项目目录，然后启动：

```powershell
# 指定目录
mini-coding-agent --workspace "D:\projects\my-app" --allow-edit --allow-commands

# 当前目录
mini-coding-agent --allow-edit --allow-commands
```



首次启动且没有可用密钥时，会显示：

```text
DeepSeek API Key（输入隐藏，留空取消）：
保存到当前用户的 Windows 凭据管理器，下次自动读取？[y/N]
```

使用者填写自己的 DeepSeek API Key，输入内容不会显示。输入 `y` 将其保存到 Windows 凭据管理器；直接回车或输入 `n` 仅用于本次会话。保存操作不会修改系统环境变量。发布附件不包含开发者的密钥。

也可以先进入目标项目目录，再执行 `mini-coding-agent --allow-edit --allow-commands`；省略 `--workspace` 时使用当前目录。

### 5. 提交任务

进入交互模式后，用自然语言描述需求，例如：

```text
定位订单总价的计算代码，修复单价乘数量的问题。只修改相关文件，
如果项目已有测试就运行相关测试，然后告诉我实际改了什么。
```

模型会自主搜索、读取和提出操作。文件写入前显示 Diff，命令执行前显示参数、工作目录和时限。输入 `y` 批准，其他输入或直接回车拒绝。

只读分析时，省略编辑和命令权限：

```powershell
mini-coding-agent "分析登录逻辑，列出相关文件和调用关系" --workspace "D:\projects\my-app"
```

提供位置参数 `task` 时，执行一次任务后退出；省略时持续对话。交互中使用 `/key` 更换密钥、`/diff` 查看修改、`/exit` 退出。创建小项目时，先由你准备一个空目录，再将它作为工作区传入。

## 更新与卸载

更新时下载新 Release 配套的两个附件，在下载目录重新安装。以下以 `0.1.0` 为例，实际操作时替换为新版本的 wheel 文件名：

```powershell
uv tool install --force --python 3.12 --constraints .\requirements.lock.txt .\mini_coding_agent-0.1.0-py3-none-any.whl
```

卸载命令入口和对应的独立工具环境：

```powershell
uv tool uninstall mini-coding-agent
```

卸载不会删除目标项目文件，也不会清除 Windows 中已保存的密钥。需要清除密钥时，打开「控制面板 → 用户账户 → 凭据管理器 → Windows 凭据」，删除普通凭据 `mini-coding-agent/deepseek-api-key`。

## 密钥与模型配置

启动时按以下顺序取得密钥：有效的 `DEEPSEEK_API_KEY` 环境变量 → Windows 凭据管理器中的保存项 → 终端隐藏输入。通过 `--env-file` 加载的值也属于当前进程环境变量。

交互模式中只输入 `/key`，即可在隐藏提示中更换密钥。留空取消，保留原配置；选择不保存时不会覆盖已有的 Windows 保存项。`--yes` 不会自动同意保存密钥。配置成功表示本地已取得密钥，是否有效要以随后的 API 请求结果为准。

Windows 保存项名称为 `mini-coding-agent/deepseek-api-key`，由系统管理，属于同一台电脑上的当前用户；可在 Windows「凭据管理器 → Windows 凭据 → 普通凭据」中删除。其他平台支持会话内隐藏输入和环境变量，不提供内置持久保存。

仍可直接设置当前终端的环境变量，或显式加载文件：

```powershell
$env:DEEPSEEK_API_KEY = "你的 DeepSeek 密钥"
```

如需环境文件，可自行创建 `.env` 并填写以下内容；源码仓库也提供 `.env.example` 模板：

```dotenv
DEEPSEEK_API_KEY=你的DeepSeek密钥
```

再从该文件所在目录启动：

```powershell
mini-coding-agent --env-file .env --workspace "D:\projects\my-app" --allow-edit --allow-commands
```

只在传入 `--env-file` 时加载；已有进程环境变量优先。环境文件支持简单的 `NAME=value`、引号和独立注释行，不执行脚本，不做变量展开。不要提交真实密钥。PyCharm 某个运行配置中的环境变量不会自动出现在独立 PowerShell 中。

隐藏输入需要交互式终端；使用管道、重定向或不支持隐藏输入的 IDE 控制台时，请通过环境变量、已保存凭据或 `--env-file` 提供密钥。

```powershell
mini-coding-agent --model deepseek-flash --base-url https://api.deepseek.com --workspace "D:\projects\my-app"
```

也可设置 `DEEPSEEK_MODEL` 和 `DEEPSEEK_BASE_URL`。默认关闭 thinking，沿用已验证的 Chat Completions 工具协议。

## 交互命令

| 输入 | 作用 |
|---|---|
| 普通文本 | 提交新任务，沿用当前对话上下文 |
| `/key` | 隐藏输入并更换 DeepSeek 密钥，可选择保存；不要在命令后附加密钥 |
| `/diff` | 查看本会话按操作顺序记录的文件修改 |
| `/clear` | 清除内存对话、读取版本和修改记录；不撤销磁盘文件 |
| `/help` | 显示交互命令 |
| `/exit` 或 `/quit` | 退出 |
| Ctrl+C | 中断当前轮；在输入提示处不会直接关闭终端 |
| Ctrl+D / Windows Ctrl+Z 后回车 | 结束输入并退出 |

会话保存在当前进程内存中，退出后不恢复；不会自动重放上次的文件写入或命令。

## 参数

```powershell
mini-coding-agent --help
```

| 参数 | 作用 |
|---|---|
| `task` | 可选，提供则单次执行；省略则交互对话 |
| `--workspace PATH` | 工作区，默认当前目录，启动后固定 |
| `--allow-edit` | 启用创建和编辑，仍逐次审批 |
| `--allow-commands` | 启用本地命令，仍逐次审批 |
| `--yes` | 自动批准已启用的操作，仅用于你信任的项目 |
| `--env-file PATH` | 显式加载环境文件 |
| `--model NAME` / `--base-url URL` | 配置模型与兼容地址 |
| `--max-model-calls N` | 每轮模型请求上限，默认 30；SDK 网络重试最多 1 次 |
| `--max-tool-calls N` | 每轮工具调用上限，默认 80 |
| `--pass-env NAME` | 允许项目命令继承额外环境变量，可重复 |
| `--debug` | 显示经过基础脱敏的工具参数 |

一次任务的退出码：`0` 表示模型正常结束回答，`1` 表示错误或预算耗尽，`2` 表示配置/参数错误，`3` 表示用户拒绝，`130` 表示中断。**退出码 0 不自动意味着所有业务需求或测试已经通过，应查看实际命令结果和 Diff。**

## 命令执行方式

模型请求的是参数数组，例如：

```json
{"argv": ["python", "-m", "pytest", "-q"], "cwd": ".", "timeout": 30}
```

- `python` 默认映射到 Agent 当前解释器。目标项目有自己的依赖时，模型可以使用项目中独立虚拟环境的 Python 路径。
- Windows 的 `npm.cmd`、`.bat`、`.ps1` 等入口需要显式使用 `cmd.exe` 或 `powershell.exe`，完整参数仍需你批准。
- 子进程只继承一组基本环境变量，模型密钥不自动传入。项目需要额外变量时使用 `--pass-env`。
- 默认 30 秒，允许 1～120 秒；持续消费 stdout/stderr，分别回传有限长的预览。
- 超时、取消、输出超过预算时停止。Windows 使用 Job Object，POSIX 使用进程组清理所属进程。
- 只支持短命令，后台服务会被清理。不会自动安装依赖或将“启动成功”当作业务验证通过。

**本地命令具有当前账户权限。文件工具的工作区门禁不能隔离命令的文件、网络或系统访问，因此请仅在你信任的项目中启用命令。无需 WSL2 或 Docker，但也不提供容器级隔离。**

## 文件与搜索边界

- 文件工具统一拒绝越界路径、Windows 设备名/备用数据流、符号链接、junction，以及常见凭据目录和秘密文件。
- 文件读取、创建和编辑支持不超过 1 MiB 的 UTF-8 文本；读取可用行范围分段，默认每次 200 行、最多 16000 字符。
- 精确编辑要求来自真实读取的完整文件哈希、唯一旧文本，并在确认后再次核对版本。保留 UTF-8 BOM、已有换行风格和基本权限模式。
- 创建文件采用排他打开，已有同名文件不会被覆盖。
- 搜索区分大小写、按字面量匹配，默认最多返回 30 条，支持文件过滤；只扫描不超过 256 KiB 的 UTF-8 文件，并有文件数量和时间预算。
- Git 仓库根目录且 Git 可用时，搜索使用 Git 的忽略规则；其他目录使用内置排除名单。受保护文件即使被 Git 跟踪，也不会通过文件工具读取。
- 大输出会标记截断；上下文过长时仅移除完整的旧对话轮次，当前轮仍过大则停止。
- 没有内置任意文件删除、自动撤销、跨重启恢复或无人监督发布。命令可能产生文件工具之外的副作用，审批前应审阅。

目录排除和凭据文件名过滤属于基础保护，不是完整的数据泄漏检测；普通源码中包含的秘密仍应由你在发送给模型前处理。

## 源码开发与打包（维护者）

从源码开发时，在仓库根目录执行：

```powershell
uv sync
uv run mini-coding-agent --workspace "D:\projects\my-app" --allow-edit --allow-commands
```

如需把开发后的版本安装到用户工具环境，由你手动执行 `uv tool install --force --python 3.12 .`。普通安装使用源码的副本；后续源码改动需要重新安装才能反映到已安装的命令中。

准备 Release 时，先核对 `pyproject.toml` 中的版本号。当前包版本为 `0.1.0`，可对应 Git 标签 `v0.1.0`。将准备发布的源码及 README 提交、推送到目标分支，再从同一版本源码根目录手动打包：

```powershell
uv build --wheel
uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements-txt --output-file dist/requirements.lock.txt
```

在 GitHub 新建 Release，选择对应标签与目标分支，将 `dist/mini_coding_agent-0.1.0-py3-none-any.whl` 和 `dist/requirements.lock.txt` 作为附件上传，确认版本和附件一致后发布。首次体验版本可标记为 **Pre-release**。标签引用的是远程提交，不包含本地尚未提交或推送的修改；操作说明见 [GitHub Release 官方文档](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。

## 源码阅读顺序

| 顺序 | 文件 | 看什么 |
|---|---|---|
| 1 | `cli.py` | 命令行参数、交互输入和创建 Agent |
| 2 | `agent_loop.py` | messages 如何增长，模型回复如何变成工具执行 |
| 3 | `tool_registry.py` | Schema 校验、JSON 参数和函数分发 |
| 4 | `file_tools.py` | 读取版本、Diff、审批、冲突检测、真实写入 |
| 5 | `search_tools.py` | 如何定位代码并控制返回量 |
| 6 | `command_tools.py` | 参数数组、环境、输出、超时与取消 |
| 7 | `processes.py` | Windows Job Object / POSIX 进程组生命周期 |
| 8 | `model_client.py` | SDK 请求、消息序列化和 API 错误 |
| 9 | `workspace.py` / `permissions.py` | 路径边界和用户确认 |
| 配置 | `config.py` / `credential_store.py` | 隐藏输入、密钥来源优先级、Windows 凭据保存 |

更具体的设计和关键代码说明见 [源码阅读指南](docs/IMPLEMENTATION.md)。[DESIGN.md](DESIGN.md) 保留长期设计；它的 M0～M9 清单并不代表当前 mini 版本已实现所有规划。

## 验证

```powershell
uv run pytest -q
```

测试覆盖真实文件创建/编辑、CRLF/BOM、外部修改冲突、拒绝操作、分段读取、搜索过滤、参数错误、工具预算和多轮上下文；命令测试真实启动 Python 并检查退出码、超时、输出上限和子进程回收。

端到端测试使用真实 OpenAI SDK 和内存 HTTP 传输模拟兼容 API。测试中的文件操作、CLI 和命令是真实执行的，测试不消耗 DeepSeek 额度，也不证明模型对任意任务都能正确决策。受限 Windows 账户无法创建链接时，对应的真实链接测试会跳过。

密钥测试使用假密钥和模拟的 Windows 凭据 API，验证首次配置、恢复保存项、会话内更换及认证请求；不会读写你的真实凭据保存项。

默认系统临时目录不可写时，可以指定一个**新的、专用于测试的临时目录**作为 pytest 的 `--basetemp`。不要把已有项目目录当作 basetemp，pytest 会清理它。
