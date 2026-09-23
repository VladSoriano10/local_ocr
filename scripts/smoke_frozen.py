"""Prueba el trabajador empaquetado, su OCR y su comunicación sin consola."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf


def run(executable: Path, work: Path, job: dict):
    job_file = work / "job.json"
    job_file.write_text(json.dumps(job), encoding="utf-8")
    proc = subprocess.run([str(executable), "--worker", str(job_file)], timeout=180, check=False)
    events = job_file.with_suffix(".events.jsonl").read_text(encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(events)
    result = json.loads(job_file.with_suffix(".result.json").read_text(encoding="utf-8"))
    if result.get("errors"):
        raise RuntimeError(result["errors"])
    return result


def main():
    executable = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="localocr-frozen-test-") as directory:
        work = Path(directory)
        project = work / "project"
        project.mkdir()
        (project / "main.py").write_text("print('hello from frozen app')\n")
        output = work / "out"
        scan = run(
            executable,
            work,
            {"operation": "scan", "root": str(project), "output": str(output), "options": {}},
        )
        assert scan["files"][0]["path"] == "main.py"
        export = run(
            executable,
            work,
            {"operation": "export", "scan": scan, "selected": ["main.py"], "output": str(output)},
        )
        assert (Path(export["output"]) / "proyecto_completo.md").is_file()
        with pymupdf.open() as source:
            page = source.new_page()
            page.insert_text((50, 90), "FROZEN APPLICATION OCR TEST", fontsize=22)
            image = page.get_pixmap(dpi=200).tobytes("png")
            with pymupdf.open() as scanned:
                target = scanned.new_page()
                target.insert_image(target.rect, stream=image)
                scanned.save(work / "scan.pdf")
        result = run(
            executable,
            work,
            {
                "operation": "documents",
                "sources": [str(work / "scan.pdf")],
                "output": str(output),
                "options": {"language": "eng"},
                "settings": {},
            },
        )
        markdown = Path(result["results"][0]["markdown"]).read_text(encoding="utf-8")
        assert "FROZEN APPLICATION OCR TEST" in markdown
        print("Frozen smoke: proyecto, exportación y OCR real correctos.")


if __name__ == "__main__":
    main()
