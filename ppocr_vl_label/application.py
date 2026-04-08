import sys
import tkinter as tk

try:
    from .tools import DEFAULT_TOOL_ID, get_tool_registry
except ImportError:
    from pathlib import Path

    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from tools import DEFAULT_TOOL_ID, get_tool_registry


def create_root():
    return tk.Tk()


def create_app(tool_id: str = DEFAULT_TOOL_ID, root: tk.Tk | None = None):
    registry = get_tool_registry()
    tool = registry.get(tool_id)
    root = root or create_root()
    app = tool.create_app(root)
    return root, app


def main(tool_id: str = DEFAULT_TOOL_ID):
    root, _ = create_app(tool_id=tool_id)
    root.mainloop()
