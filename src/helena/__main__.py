"""Entry point for ``python -m helena``."""

import sys

from helena.app import run

if __name__ == "__main__":
    sys.exit(run())
