from __future__ import annotations

import sys

from paperflow_audit import main


if __name__ == "__main__":
    raise SystemExit(main(["footprint", *sys.argv[1:]]))
