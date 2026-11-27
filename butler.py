#!/usr/bin/env python3
"""Token 管家快捷入口: python3 butler.py <sources|add|test|status|stats>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tpm.butler import main

if __name__ == "__main__":
    sys.exit(main())
