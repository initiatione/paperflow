from pathlib import Path
import sys

runtime_root = Path(__file__).resolve().parent / "build"
sys.path.insert(0, str(runtime_root))

from epi.wiki_init import main


if __name__ == "__main__":
    raise SystemExit(main())
