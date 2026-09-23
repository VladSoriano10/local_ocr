from __future__ import annotations

import json
import sys
from pathlib import Path

from .common import AppError, Cancelled, check_cancel

_event_file: Path | None = None


def send(event: dict) -> None:
    line = json.dumps(event, ensure_ascii=True) + "\n"
    if _event_file:
        with _event_file.open("a", encoding="utf-8") as stream:
            stream.write(line)
    elif sys.stdout:
        print(line, end="", flush=True)


def run_job(job: dict, cancel_file: Path | None = None) -> dict:
    operation = job["operation"]
    check_cancel(cancel_file)
    if operation == "diagnose":
        from .dependencies import diagnose

        return diagnose(job.get("settings", {}))
    if operation == "documents":
        from .documents import DocumentOptions, convert_document

        results, errors = [], []
        sources = job["sources"]
        for index, source in enumerate(sources):
            check_cancel(cancel_file)
            send({"type": "file_start", "index": index, "source": source})
            try:
                result = convert_document(
                    Path(source),
                    Path(job["output"]),
                    DocumentOptions(**job["options"]),
                    job.get("settings", {}),
                    progress=send,
                    cancel_file=cancel_file,
                )
                results.append(result)
                send({"type": "file_done", "index": index, "result": result})
            except Cancelled:
                raise
            except Exception as exc:
                errors.append({"source": Path(source).name, "message": str(exc)})
                send({"type": "file_error", "index": index, "message": str(exc)})
        return {"results": results, "errors": errors}
    if operation == "scan":
        from .projects import ProjectOptions, scan_project

        return scan_project(
            Path(job["root"]),
            ProjectOptions(**job["options"]),
            progress=send,
            cancel_file=cancel_file,
            exclude_roots=[Path(job["output"])],
        )
    if operation == "export":
        from .projects import export_project

        return export_project(
            job["scan"], job["selected"], Path(job["output"]), progress=send, cancel_file=cancel_file
        )
    raise AppError("Operación desconocida.")


def main(job_path: str) -> int:
    global _event_file
    path = Path(job_path)
    _event_file = path.with_suffix(".events.jsonl")
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
        result = run_job(job, path.with_suffix(".cancel"))
        # El análisis puede ser grande: se pasa por archivo temporal, no por una señal Qt enorme.
        result_file = path.with_suffix(".result.json")
        result_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        send({"type": "done", "result_file": str(result_file)})
        return 0
    except Cancelled as exc:
        send({"type": "cancelled", "message": str(exc)})
        return 2
    except Exception as exc:
        send({"type": "error", "message": str(exc)})
        if sys.stderr:
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
