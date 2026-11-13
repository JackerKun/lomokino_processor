#!/usr/bin/env python3
"""Compatibility entry point for LomoKino Studio."""
import sys

if __name__ == '__main__':
    from lomokino.updates import WORKER_FLAG, fetch_latest_release

    if sys.argv[1:2] == [WORKER_FLAG]:
        raise SystemExit(fetch_latest_release(sys.argv[2]) if len(sys.argv) == 3 else 2)

from lomokino.ui import LomoKinoGUI, main

if __name__ == '__main__':
    raise SystemExit(main())
