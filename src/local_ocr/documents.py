from __future__ import annotations

import shutil
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf

from .common import (
    AppError,
    Progress,
    application_command,
    check_cancel,
    emit,
    output_transaction,
    run_process,
    safe_name,
    write_json,
)
from .dependencies import available_languages, ensure_ocr_configs, find_program, runtime_env


@dataclass
class DocumentOptions:
    language: str = "spa+eng"
    mode: str = "auto"
    dpi: int = 300
    rotate: bool = False
    deskew: bool = False
    images: bool = False
    tables: bool = True

    def validate(self):
        if self.mode not in {"auto", "missing", "force"}:
            raise AppError("Modo OCR no válido.")
        if self.dpi not in {200, 300, 400}:
            raise AppError("La resolución debe ser 200, 300 o 400 DPI.")
        if self.deskew and self.mode != "force":
            raise AppError("Enderezar requiere el modo Forzar, que rasteriza las páginas.")
        if not self.language or any(not p.isalpha() for p in self.language.split("+")):
            raise AppError("Idioma OCR no válido.")


def inspect_pdf(path: Path, cancel_file: Path | None = None) -> list[dict]:
    with pymupdf.open(path) as pdf:
        if not pdf.is_pdf:
            raise AppError("El archivo no es un PDF válido.")
        if pdf.is_encrypted or pdf.needs_pass:
            raise AppError("PDF protegido. Exporte una copia sin contraseña desde su aplicación autorizada.")
        if pdf.get_sigflags() > 0:
            raise AppError("PDF con campos de firma: no se modifica para no invalidar firmas digitales.")
        if not 1 <= len(pdf) <= 2000:
            raise AppError("El PDF debe tener entre 1 y 2.000 páginas. Divida documentos mayores.")
        pages = []
        for page in pdf:
            check_cancel(cancel_file)
            pages.append(
                {
                    "page": page.number + 1,
                    "characters": len(page.get_text().strip()),
                    "images": len(page.get_images()),
                }
            )
        return pages


def word_to_pdf(source: Path, work: Path, settings: dict, cancel_file: Path | None) -> Path:
    executable = find_program("soffice", settings.get("soffice", ""))
    if not executable:
        raise AppError("Falta LibreOffice. Instálelo o configure soffice.exe en Ajustes.")
    profile = work / "libreoffice-profile"
    user = profile / "user"
    user.mkdir(parents=True)
    # Perfil aislado, macros bloqueadas y actualización de enlaces deshabilitada.
    (user / "registrymodifications.xcu").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
        '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
        '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
        '<item oor:path="/org.openoffice.Office.Writer/Content/Update">'
        '<prop oor:name="Link" oor:op="fuse"><value>0</value></prop></item>'
        "</oor:items>",
        encoding="utf-8",
    )
    copied = work / ("entrada" + source.suffix.lower())
    shutil.copyfile(source, copied)
    target = work / "converted"
    target.mkdir()
    run_process(
        [
            executable,
            f"-env:UserInstallation={profile.as_uri()}",
            "--headless",
            "--nologo",
            "--nodefault",
            "--norestore",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(target),
            str(copied),
        ],
        cancel_file=cancel_file,
        timeout=600,
    )
    pdf = target / "entrada.pdf"
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise AppError("LibreOffice no generó el PDF. Revise si el documento está protegido o dañado.")
    return pdf


def ocr_helper(job: dict) -> int:
    """Punto de entrada aislado, también funciona dentro del ejecutable empaquetado."""
    import ocrmypdf

    opts = job["options"]
    result = ocrmypdf.ocr(
        job["input"],
        job["output"],
        language=opts["language"].split("+"),
        output_type="pdf",
        mode={"auto": "redo", "missing": "skip", "force": "force"}[opts["mode"]],
        oversample=opts["dpi"],
        rotate_pages=opts["rotate"],
        deskew=opts["deskew"],
        optimize=0,
        jobs=2,
        use_threads=True,
        progress_bar=False,
        tesseract_timeout=300,
        invalidate_digital_signatures=False,
        max_image_mpixels=100,
    )
    return int(result)


def _escape_cell(value: str | None) -> str:
    return (value or "").replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _table_markdown(rows: list[list[str | None]]) -> str:
    if not rows:
        return ""
    width = max(map(len, rows))
    # No se inventa que la primera fila de datos es encabezado.
    lines = [
        "| " + " | ".join(f"Columna {i + 1}" for i in range(width)) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for row in rows:
        padded = row + [None] * (width - len(row))
        lines.append("| " + " | ".join(_escape_cell(v) for v in padded) + " |")
    return "\n".join(lines)


def pdf_to_markdown(
    pdf_path: Path,
    stage: Path,
    options: DocumentOptions,
    *,
    progress: Progress | None = None,
    cancel_file: Path | None = None,
) -> tuple[str, list[dict], list[str]]:
    parts, pages, warnings = [], [], []
    with pymupdf.open(pdf_path) as pdf:
        total = len(pdf)
        for index, page in enumerate(pdf):
            check_cancel(cancel_file)
            emit(progress, f"Extrayendo Markdown: página {index + 1} de {total}", index + 1, total)
            text = page.get_text("text", sort=True).strip()
            pages.append({"page": index + 1, "characters": len(text)})
            parts.append(f"## Página {index + 1}\n")
            if not text:
                warnings.append(
                    f"Página {index + 1}: sin texto recuperable; puede ser una ilustración o un fallo OCR."
                )
                parts.append("[Sin texto recuperable; revisar esta página en el PDF.]\n")
            flags = pymupdf.TEXTFLAGS_DICT
            if not options.images:
                flags &= ~pymupdf.TEXT_PRESERVE_IMAGES
            data = page.get_text("dict", sort=True, flags=flags)
            sizes = Counter()
            for block in data["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        sizes[round(span["size"], 1)] += len(span["text"])
            body_size = sizes.most_common(1)[0][0] if sizes else 12
            events, table_rects = [], []
            if options.tables and text:
                try:
                    tables = page.find_tables().tables
                    for table in tables:
                        rows = table.extract()
                        if len(rows) >= 2 and table.col_count >= 2:
                            table_rects.append(pymupdf.Rect(table.bbox))
                            events.append((table.bbox[1], table.bbox[0], _table_markdown(rows)))
                except Exception:
                    warnings.append(
                        f"Página {index + 1}: no se pudo analizar tablas; se conserva texto simple."
                    )
            image_index = 0
            for block in data["blocks"]:
                rect = pymupdf.Rect(block["bbox"])
                if block["type"] == 1:
                    if options.images and rect.get_area() < page.rect.get_area() * 0.85:
                        image_index += 1
                        folder = stage / "imagenes"
                        folder.mkdir(exist_ok=True)
                        ext = block.get("ext", "png")
                        if ext not in {"png", "jpeg", "jpg", "webp", "bmp", "tiff", "jpx"}:
                            ext = "bin"
                        name = f"pagina_{index + 1:04}_{image_index:02}.{ext}"
                        (folder / name).write_bytes(block["image"])
                        events.append(
                            (rect.y0, rect.x0, f"![Imagen de la página {index + 1}](imagenes/{name})")
                        )
                    continue
                # Se filtran líneas individuales: un bloque puede cruzar una tabla.
                lines = []
                font_size = 0.0
                for line in block.get("lines", []):
                    line_rect = pymupdf.Rect(line["bbox"])
                    if any(
                        (line_rect & r).get_area() >= max(1, line_rect.get_area()) * 0.7 for r in table_rects
                    ):
                        continue
                    spans = line.get("spans", [])
                    value = "".join(span["text"] for span in spans).strip()
                    if value:
                        lines.append(value)
                        font_size = max(font_size, *(span["size"] for span in spans))
                if lines:
                    content = "\n".join(lines)
                    if font_size >= body_size * 1.25 and len(content) < 160:
                        content = "### " + " ".join(lines)
                    events.append((rect.y0, rect.x0, content))
            parts.extend(content + "\n" for _, _, content in sorted(events, key=lambda e: (e[0], e[1])))
    return "\n".join(parts), pages, warnings


def convert_document(
    source: Path,
    output_root: Path,
    options: DocumentOptions | None = None,
    settings: dict | None = None,
    *,
    progress: Progress | None = None,
    cancel_file: Path | None = None,
) -> dict:
    options, settings = options or DocumentOptions(), settings or {}
    options.validate()
    source = source.expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in {".pdf", ".docx", ".doc"}:
        raise AppError("Seleccione un PDF, DOCX o DOC existente.")
    if source.stat().st_size > 512_000_000:
        raise AppError("El archivo supera 512 MB. Divídalo antes de procesarlo.")
    check_cancel(cancel_file)
    name = safe_name(source.stem)
    warnings = []
    with (
        output_transaction(output_root, name) as (stage, final),
        tempfile.TemporaryDirectory(prefix="localocr-work-") as work_str,
    ):
        work = Path(work_str)
        if source.suffix.lower() == ".pdf":
            # Instantánea: no leer un original que cambie mientras corre el OCR.
            pdf = work / "entrada.pdf"
            shutil.copyfile(source, pdf)
        else:
            emit(progress, "Convirtiendo Word a PDF con LibreOffice…")
            pdf = word_to_pdf(source, work, settings, cancel_file)
            warnings.append(
                "Word convertido por LibreOffice: fuentes y maquetación pueden diferir de Microsoft Word."
            )
        emit(progress, "Analizando páginas y texto existente…")
        before = inspect_pdf(pdf, cancel_file)
        needs_ocr = options.mode == "force" or any(p["characters"] == 0 for p in before)
        if options.mode == "auto":
            needs_ocr |= any(p["images"] > 0 for p in before)
        elif options.mode == "missing" and any(p["images"] and p["characters"] for p in before):
            warnings.append(
                "Modo solo páginas sin texto: las imágenes de páginas con texto no recibieron OCR."
            )
        output_pdf = stage / f"{name}_OCR.pdf"
        if needs_ocr:
            ensure_ocr_configs(settings)
            installed = available_languages(settings)
            missing = set(options.language.split("+")) - set(installed)
            if options.rotate and "osd" not in installed:
                missing.add("osd")
            if missing:
                raise AppError(
                    "Faltan idiomas de Tesseract: "
                    + ", ".join(sorted(missing))
                    + ". Instale los archivos .traineddata o cambie el idioma en Documentos."
                )
            job_file = work / "ocr-job.json"
            write_json(job_file, {"input": str(pdf), "output": str(output_pdf), "options": asdict(options)})
            emit(progress, "Aplicando OCR local (la duración depende del número de páginas)…")
            helper_log = job_file.with_suffix(".helper.log")
            try:
                log = run_process(
                    application_command("--ocr-helper", str(job_file)),
                    cancel_file=cancel_file,
                    timeout=max(600, len(before) * 360),
                    env=runtime_env(settings),
                )
            except AppError as exc:
                from .common import Cancelled

                if isinstance(exc, Cancelled):
                    raise
                detail = (
                    helper_log.read_text(encoding="utf-8", errors="replace")[-6000:]
                    if helper_log.exists()
                    else ""
                )
                raise AppError(f"No se completó el OCR: {exc}\n{detail}") from exc
            if helper_log.exists():
                log += helper_log.read_text(encoding="utf-8", errors="replace")[-8000:]
            if any(term in log.lower() for term in ("timeout", "timed out", "skipped", "warning")):
                warnings.append("El motor OCR emitió avisos; revise ocr_motor.log y las páginas señaladas.")
            (stage / "ocr_motor.log").write_text(log, encoding="utf-8")
        else:
            shutil.copyfile(pdf, output_pdf)
            emit(progress, "El PDF ya contiene texto; se conserva sin rehacer OCR.")
        check_cancel(cancel_file)
        if not output_pdf.is_file():
            raise AppError("El motor no produjo un PDF.")
        after = inspect_pdf(output_pdf, cancel_file)
        if len(after) != len(before):
            raise AppError("Verificación fallida: cambió el número de páginas.")
        if any(a["characters"] == 0 and b["characters"] > 0 for b, a in zip(before, after, strict=True)):
            raise AppError("Verificación fallida: una página perdió todo su texto original.")
        markdown, page_report, md_warnings = pdf_to_markdown(
            output_pdf, stage, options, progress=progress, cancel_file=cancel_file
        )
        warnings += md_warnings
        if options.mode == "force":
            warnings.append(
                "Modo Forzar: se rasterizaron páginas; puede cambiar la calidad de vectores y formularios."
            )
        if options.images:
            warnings.append(
                "Se exportaron imágenes embebidas; se omiten escaneos que ocupan casi toda la página y dibujos vectoriales."
            )
        markdown = f"# {source.stem}\n\n" + markdown
        (stage / f"{name}.md").write_text(markdown, encoding="utf-8")
        report = {
            "source_name": source.name,
            "pdf": output_pdf.name,
            "markdown": f"{name}.md",
            "ocr_applied": needs_ocr,
            "options": asdict(options),
            "pages": page_report,
            "warnings": warnings,
            "markdown_source": "searchable_pdf",
            "limitations": "Orden de lectura, títulos, tablas y fórmulas requieren revisión; no se usa un LLM.",
        }
        write_json(stage / "informe.json", report)
        check_cancel(cancel_file)
    return {
        "output": str(final),
        "pdf": str(final / output_pdf.name),
        "pages": len(after),
        "markdown": str(final / f"{name}.md"),
        "warnings": warnings,
    }
