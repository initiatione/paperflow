#!/usr/bin/env python3
"""Thin wrapper for the EPI query planner."""

from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts" / "build"))

from epi.query_planner import main


if __name__ == "__main__":
    raise SystemExit(main())
