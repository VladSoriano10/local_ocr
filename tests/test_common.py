import sys

import pytest

from local_ocr.common import AppError, Cancelled, output_transaction, run_process, safe_name


def test_transaction_rolls_back_and_preserves_existing(tmp_path):
    existing = tmp_path / "keep.txt"
    existing.write_text("untouched")
    with pytest.raises(RuntimeError):
        with output_transaction(tmp_path, "test") as (stage, _):
            (stage / "partial.txt").write_text("partial")
            raise RuntimeError("example error")
    assert list(tmp_path.iterdir()) == [existing]


def test_process_success_and_failure():
    assert "hello" in run_process([sys.executable, "-c", "print('hello')"])
    with pytest.raises(AppError, match="código 3"):
        run_process([sys.executable, "-c", "raise SystemExit(3)"])


def test_process_cancellation(tmp_path):
    cancel = tmp_path / "stop"
    command = [
        sys.executable,
        "-c",
        f"from pathlib import Path; import time; Path({str(cancel)!r}).touch(); time.sleep(30)",
    ]
    with pytest.raises(Cancelled):
        run_process(command, cancel_file=cancel, timeout=10)


def test_safe_names():
    assert safe_name("inva:lid/name?.") == "inva_lid_name_"
    assert safe_name("CON").startswith("resultado_")
    assert "/" not in safe_name("../../file")
