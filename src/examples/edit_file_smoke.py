from pathlib import Path
from mini_coding_agent.file_tools import read_file, edit_file

if __name__ == "__main__":

    workspace_root = (
        Path(__file__).resolve().parents[2]
        / "experiments-data"
        / "workspace"
    )

    snapshot = read_file(workspace_root,"demo.py")

    result = edit_file(
        workspace_root=workspace_root,
        path="demo.py",
        base_version=snapshot["result"]["version_id"],
        old_text="return price + quantity",
        new_text="return price * quantity",
    )

    print(result)