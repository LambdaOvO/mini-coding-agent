from mini_coding_agent.agent_loop import run_agent
from pathlib import Path
from tool_smoke import ADD_TOOL, MULTIPLY_TOOL
from mini_coding_agent.file_tools import READ_FILE_TOOL, LIST_FILES_TOOL, EDIT_FILE_TOOL
from mini_coding_agent.command_tools import RUN_CHECK_TOOL


if __name__ == "__main__":
    workspace_root = (
            Path(__file__).resolve().parents[2]
            / "experiments-data"
            / "workspace"
    )

    answer = run_agent(
        prompt=(
            "请先读取 demo.py，再调用 run_check。"
            "calculate_total 应计算单价乘以数量。"
            "如果检查失败，请根据源码和错误做最小修改，只修改 demo.py。"
            "编辑时使用读取结果中的 version_id。"
            "如果用户拒绝修改，说明未修改并结束。"
            "修改成功后再次调用 run_check，根据实际检查结果汇报。"
        ),
        tools=[READ_FILE_TOOL, EDIT_FILE_TOOL, RUN_CHECK_TOOL],
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        workspace_root=workspace_root,
        max_model_calls=10,
    )

    print("最终输出：", answer)