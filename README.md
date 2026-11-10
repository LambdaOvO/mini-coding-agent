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

## 快速开始：Windows PowerShell

在这个项目的根目录执行：

```powershell
uv sync
$env:DEEPSEEK_API_KEY = "你的 DeepSeek 密钥"
uv run mini-coding-agent --workspace "D:\projects\my-app" --allow-edit --allow-commands
```

这会进入交互模式。输入任务，例如：

```text
定位订单总价的计算代码，修复单价乘数量的问题。只修改相关文件，
如果项目已有测试就运行相关测试，然后告诉我实际改了什么。
```

模型会自主搜索、读取和提出操作。文件写入前显示 Diff，命令执行前显示完整参数、工作目录和时限。输入 `y` 批准，其他输入或直接回车拒绝。

也可以只执行一次任务：

```powershell
uv run mini-coding-agent "为项目增加一个 CSV 导出功能，并检查实现" --workspace "D:\projects\my-app" --allow-edit --allow-commands
```

只读分析：

```powershell
uv run mini-coding-agent "分析登录逻辑，列出相关文件和调用关系" --workspace "D:\projects\my-app"
```

创建小项目时，先由你准备一个空目录，再将它作为工作区传入。Agent 可以在其中创建文件和子目录。

### 密钥与模型配置

PyCharm 某个运行配置中的环境变量不会自动出现在独立 PowerShell 中。可直接设置当前终端的环境变量，也可显式加载文件：

```powershell
Copy-Item .env.example .env
# 编辑 .env 填入密钥，再启动：
uv run mini-coding-agent --env-file .env --workspace "D:\projects\my-app" --allow-edit --allow-commands
```

只在传入 `--env-file` 时加载；已有进程环境变量优先。环境文件支持简单的 `NAME=value`、引号和独立注释行，不执行脚本，不做变量展开。不要提交真实密钥。

```powershell
uv run mini-coding-agent --model deepseek-flash --base-url https://api.deepseek.com --workspace "D:\projects\my-app"
```

也可设置 `DEEPSEEK_MODEL` 和 `DEEPSEEK_BASE_URL`。默认关闭 thinking，沿用已验证的 Chat Completions 工具协议。

## 交互命令

| 输入 | 作用 |
|---|---|
| 普通文本 | 提交新任务，沿用当前对话上下文 |
| `/diff` | 查看本会话按操作顺序记录的文件修改 |
| `/clear` | 清除内存对话、读取版本和修改记录；不撤销磁盘文件 |
| `/help` | 显示交互命令 |
| `/exit` 或 `/quit` | 退出 |
| Ctrl+C | 中断当前轮；在输入提示处不会直接关闭终端 |
| Ctrl+D / Windows Ctrl+Z 后回车 | 结束输入并退出 |

会话保存在当前进程内存中，退出后不恢复；不会自动重放上次的文件写入或命令。

## 参数

```powershell
uv run mini-coding-agent --help
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

更具体的设计和关键代码说明见 [源码阅读指南](docs/IMPLEMENTATION.md)。[DESIGN.md](DESIGN.md) 保留长期设计；它的 M0～M9 清单并不代表当前 mini 版本已实现所有规划。

## 验证

```powershell
uv run pytest -q
```

测试覆盖真实文件创建/编辑、CRLF/BOM、外部修改冲突、拒绝操作、分段读取、搜索过滤、参数错误、工具预算和多轮上下文；命令测试真实启动 Python 并检查退出码、超时、输出上限和子进程回收。

端到端测试使用真实 OpenAI SDK 和内存 HTTP 传输模拟兼容 API。测试中的文件操作、CLI 和命令是真实执行的，测试不消耗 DeepSeek 额度，也不证明模型对任意任务都能正确决策。受限 Windows 账户无法创建链接时，对应的真实链接测试会跳过。

默认系统临时目录不可写时，可以指定一个**新的、专用于测试的临时目录**作为 pytest 的 `--basetemp`。不要把已有项目目录当作 basetemp，pytest 会清理它。
