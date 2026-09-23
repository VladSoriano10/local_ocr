from __future__ import annotations

import importlib.metadata
import os
import shutil
from pathlib import Path

from .common import AppError, run_process


def find_program(name: str, custom: str = "") -> str | None:
    if custom:
        p = Path(custom).expanduser()
        return str(p.resolve()) if p.is_file() else None
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        tail = {"tesseract": "Tesseract-OCR/tesseract.exe", "soffice": "LibreOffice/program/soffice.exe"}
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(variable)
            if base and name in tail:
                for folder in (Path(base), Path(base) / "Programs"):
                    path = folder / tail[name]
                    if path.is_file():
                        return str(path)
    return None


def runtime_env(settings: dict) -> dict:
    env = os.environ.copy()
    tesseract = find_program("tesseract", settings.get("tesseract", ""))
    if tesseract:
        env["PATH"] = str(Path(tesseract).parent) + os.pathsep + env.get("PATH", "")
    tessdata = settings.get("tessdata", "")
    if tessdata:
        if not Path(tessdata).is_dir():
            raise AppError("La carpeta tessdata configurada no existe.")
        env["TESSDATA_PREFIX"] = str(Path(tessdata).resolve())
    return env


def available_languages(settings: dict) -> list[str]:
    exe = find_program("tesseract", settings.get("tesseract", ""))
    if not exe:
        raise AppError("Falta Tesseract OCR. Instálelo o seleccione tesseract.exe en Ajustes.")
    output = run_process([exe, "--list-langs"], env=runtime_env(settings), timeout=20)
    return sorted(
        line.strip()
        for line in output.splitlines()
        if line.strip() and " " not in line.strip() and not line.strip().endswith(":")
    )


def diagnose(settings: dict) -> dict:
    result = {"programs": {}, "packages": {}, "languages": [], "warnings": []}
    for name in ("tesseract", "soffice"):
        result["programs"][name] = find_program(name, settings.get(name, ""))
    for name in ("PySide6", "PyMuPDF", "ocrmypdf", "pathspec"):
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = "No disponible"
    try:
        result["languages"] = available_languages(settings)
    except AppError as exc:
        result["warnings"].append(str(exc))
    if not result["programs"]["soffice"]:
        result["warnings"].append("LibreOffice no encontrado: Word a PDF requiere instalarlo.")
    return result
