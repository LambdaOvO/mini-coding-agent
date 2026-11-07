from mini_coding_agent.agent_loop import run_agent
from tool_smoke import ADD_TOOL


if __name__ == "__main__":
    answer = run_agent(
        prompt=(
            "请使用 add 工具，先计算 19 + 23。"
            "拿到工具结果后，再将该结果加 8，最后告诉我答案。"
        ),
        tools=[ADD_TOOL],
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
    )

    print("最终输出：", answer)