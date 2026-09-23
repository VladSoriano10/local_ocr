"""Genera vistas internas para revisar la interfaz y un PDF de muestra. No usa archivos del usuario."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pymupdf
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from local_ocr.documents import DocumentOptions, convert_document
from local_ocr.gui import THEME, MainWindow
from local_ocr.projects import scan_project


def main():
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "qa").resolve()
    output.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(THEME)
    window = MainWindow()
    window.output_edit.setText(str(output / "resultados"))
    window.show()
    app.processEvents()
    window.grab().save(str(output / "documentos.png"))
    sample = output / "sample-project"
    sample.mkdir(exist_ok=True)
    (sample / "main.py").write_text(
        "def convertir_documento(ruta):\n    return generar_markdown(ruta)\n", encoding="utf-8"
    )
    (sample / "README.md").write_text(
        "# Proyecto de ejemplo\n\nNo se ejecuta durante el análisis.\n", encoding="utf-8"
    )
    window.root_edit.setText(str(sample))
    window.populate_tree(scan_project(sample))
    window.tabs.setCurrentIndex(1)
    window.preview_source(window.project_items["main.py"], 0)
    app.processEvents()
    window.grab().save(str(output / "proyectos.png"))
    window.tabs.setCurrentIndex(2)
    app.processEvents()
    window.grab().save(str(output / "ajustes.png"))
    window.close()

    original = output / "muestra_escaneada.pdf"
    with pymupdf.open() as native:
        page = native.new_page(width=612, height=792)
        page.insert_text((60, 85), "Local OCR verification", fontsize=24)
        page.insert_text((60, 140), "This document contains a scanned image, not native text.", fontsize=13)
        page.insert_text((60, 170), "The output should look the same and allow text selection.", fontsize=13)
        page.insert_text((60, 230), "Sample total: 125.50", fontsize=16)
        raster = page.get_pixmap(dpi=200)
        with pymupdf.open() as scan:
            scan.new_page(width=612, height=792).insert_image(page.rect, pixmap=raster)
            scan.save(original)
    result = convert_document(original, output / "resultados", DocumentOptions(language="eng"))
    with pymupdf.open(result["pdf"]) as pdf:
        pdf[0].get_pixmap(dpi=120).save(output / "pdf_resultado.png")
    print(result["output"])


if __name__ == "__main__":
    main()
