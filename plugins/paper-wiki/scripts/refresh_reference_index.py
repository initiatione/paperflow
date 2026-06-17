from __future__ import annotations

import sys
from pathlib import Path


_BUILD_ROOT = Path(__file__).resolve().parent / "build"
if str(_BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUILD_ROOT))

from paper_wiki import reference_index as _impl


globals().update({name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")})


if __name__ == "__main__":
    raise SystemExit(_impl.main())
