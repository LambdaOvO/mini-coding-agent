from pathlib import Path
from mini_coding_agent.file_tools import read_file

if __name__ == "__main__":

    workspace_root = (
        Path(__file__).resolve().parents[2]
        / "experiments-data"
        / "workspace"
    )

    result =read_file(workspace_root, "demo.py")
    print(result)