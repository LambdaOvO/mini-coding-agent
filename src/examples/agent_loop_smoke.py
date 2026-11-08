from mini_coding_agent.agent_loop import run_agent
from pathlib import Path
from tool_smoke import ADD_TOOL, MULTIPLY_TOOL
from mini_coding_agent.file_tools import READ_FILE_TOOL, LIST_FILES_TOOL


if __name__ == "__main__":
    workspace_root = (
            Path(__file__).resolve().parents[2]
            / "experiments-data"
            / "workspace"
    )

    answer = run_agent(
        prompt=(
            "请先列出工作区根目录，拿到目录结果后，"
            "选择 Python 文件读取，检查总价函数是否实现了单价乘以数量。"
            "只做分析。"
        ),
        tools=[READ_FILE_TOOL, LIST_FILES_TOOL, ADD_TOOL, MULTIPLY_TOOL],
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        workspace_root=workspace_root,
    )

    print("最终输出：", answer)