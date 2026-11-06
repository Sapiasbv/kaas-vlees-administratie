"""Start de Kaas & Vlees administratie vanuit de projectmap: python administratie.py <opdracht>"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from kva.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
