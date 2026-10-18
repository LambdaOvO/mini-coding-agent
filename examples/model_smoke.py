from mini_coding_agent.model_client import generate

if __name__ == "__main__":
    answer = generate(
        prompt="请用介绍一下自己",
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
    )
    print(answer)