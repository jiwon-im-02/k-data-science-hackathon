"""Run integration checks with an isolated state file, preserving user dispatches."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="routeone-tests-") as temporary:
        # Set before importing Flask/config so every test uses disposable state.
        os.environ["DISPATCH_STATE_FILE"] = str(Path(temporary) / "dispatch_state.json")
        import test_app

        tests = [
            getattr(test_app, name)
            for name in sorted(dir(test_app))
            if name.startswith("test_") and callable(getattr(test_app, name))
        ]
        for test in tests:
            test()
            print(f"PASS  {test.__name__}")
        print(f"\n{len(tests)} integration tests passed. User dispatch data was not modified.")


if __name__ == "__main__":
    main()

