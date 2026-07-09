"""Launcher for the human-evaluation UI (Block D.hum) — wraps mprm.ui.server.main()."""
from __future__ import annotations

import sys

from mprm.ui.server import main


if __name__ == "__main__":
    sys.exit(main())
