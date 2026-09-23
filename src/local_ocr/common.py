from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

Progress = Callable[[dict], None]


class AppError(Exception):
    """Error de operación seguro para mostrar al usuario."""


class Cancelled(AppError):
    pass


def check_cancel(cancel_file: Path | None) -> None:
    if cancel_file and cancel_file.exists():
        raise Cancelled("Operación cancelada. Los archivos originales no se modificaron.")


def emit(progress: Progress | None, message: str, current: int = 0, total: int = 0) -> None:
    if progress:
        progress({"type": "progress", "message": message, "current": current, "total": total})


def safe_name(name: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")[:80]
    if not value or value.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }:
        value = "resultado_" + value
    return value


@contextmanager
def output_transaction(output_root: Path, label: str):
    """Publica un directorio completo; nunca reemplaza una salida existente."""
    root = output_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".localocr-", dir=root))
    final = root / f"{safe_name(label)}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    try:
        yield staging, final
        if final.exists():
            raise AppError("La carpeta de salida ya existe; vuelva a intentar.")
        staging.rename(final)
    finally:
        if staging.exists():
            shutil.rmtree(staging)  # Solo el temporal privado creado en esta función.


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def application_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "local_ocr", *args]


def stop_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=15)


def run_process(
    command: list[str], *, cancel_file: Path | None = None, timeout: int = 1800, env: dict | None = None
) -> str:
    """Sin shell, salida acotada y cancelación de todos los procesos hijos."""
    check_cancel(cancel_file)
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
    with tempfile.TemporaryFile() as log:
        try:
            proc = subprocess.Popen(command, stdout=log, stderr=log, env=env, **flags)
        except OSError as exc:
            raise AppError(f"No se pudo iniciar {Path(command[0]).name}: {exc}") from exc
        started = time.monotonic()
        try:
            while proc.poll() is None:
                check_cancel(cancel_file)
                if time.monotonic() - started > timeout:
                    raise AppError(f"El proceso superó el límite de {timeout} segundos.")
                time.sleep(0.15)
            check_cancel(cancel_file)
        except BaseException:
            stop_process_tree(proc)
            raise
        log.seek(0, os.SEEK_END)
        log.seek(max(0, log.tell() - 8000))
        output = log.read().decode("utf-8", errors="replace")
        if proc.returncode:
            raise AppError(f"{Path(command[0]).name} terminó con código {proc.returncode}:\n{output}")
        return output
