from __future__ import annotations

import contextlib
import json
import multiprocessing
import sys
import traceback
from pathlib import Path


def main() -> int:
    multiprocessing.freeze_support()
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        from .worker import main as worker_main

        return worker_main(sys.argv[2])
    if len(sys.argv) > 2 and sys.argv[1] == "--ocr-helper":
        path = Path(sys.argv[2])
        with path.with_suffix(".helper.log").open("w", encoding="utf-8") as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                try:
                    from .documents import ocr_helper

                    return ocr_helper(json.loads(path.read_text(encoding="utf-8")))
                except Exception:
                    traceback.print_exc()
                    return 1
    from .gui import launch

    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
