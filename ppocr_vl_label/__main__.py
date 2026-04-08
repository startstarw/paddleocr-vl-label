import sys

try:
    from .application import main
except ImportError:
    from pathlib import Path

    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from application import main


if __name__ == "__main__":
    main()
