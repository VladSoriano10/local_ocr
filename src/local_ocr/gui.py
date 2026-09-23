from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .common import application_command, write_json

THEME = """
QMainWindow, QWidget { background: #111827; color: #e5e7eb; font-size: 13px; }
QLabel#title { font-size: 30px; font-weight: 700; color: #ffffff; }
QLabel#muted { color: #9ca3af; }
QLabel#badge { color: #6ee7b7; background: #153832; padding: 6px 14px; border-radius: 12px; }
QTabWidget::pane { border: 1px solid #374151; border-radius: 9px; }
QTabBar::tab { padding: 12px 22px; margin-right: 4px; color: #9ca3af; }
QTabBar::tab:selected { background: #253247; color: #6ee7b7; border-bottom: 2px solid #6ee7b7; }
QGroupBox { border: 1px solid #374151; border-radius: 8px; margin-top: 12px; padding: 16px 10px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #d1d5db; }
QPushButton { background: #2d3c52; border: 1px solid #45536a; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background: #3d506c; }
QPushButton#primary { background: #6ee7b7; color: #102d27; border: none; font-weight: 700; }
QPushButton#primary:hover { background: #a7f3d0; }
QPushButton:disabled { background: #1f2937; color: #6b7280; border-color: #374151; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #0b1220; border: 1px solid #374151;
    padding: 7px; border-radius: 5px; selection-background-color: #275c54; }
QTableWidget, QTreeWidget { background: #0b1220; alternate-background-color: #131e30;
    border: 1px solid #374151; border-radius: 5px; selection-background-color: #275c54; }
QHeaderView::section { background: #1f2937; padding: 8px; border: none; color: #cbd5e1; }
QProgressBar { border: 1px solid #374151; border-radius: 5px; text-align: center; min-height: 18px; }
QProgressBar::chunk { background: #34b88a; border-radius: 4px; }
QCheckBox { spacing: 7px; padding: 3px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QScrollArea { border: none; }
QToolTip { color: #e5e7eb; background: #1f2937; border: 1px solid #64748b; }
"""


def label(text: str, muted: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if muted:
        widget.setObjectName("muted")
    return widget


def button(text: str, callback, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName("primary")
    return widget


def scroll_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    layout = QVBoxLayout(body)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)
    scroll.setWidget(body)
    return scroll, layout


class FileTable(QTableWidget):
    paths_dropped = Signal(list)

    def __init__(self):
        super().__init__(0, 2)
        self.setHorizontalHeaderLabels(["Documento", "Estado"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAcceptDrops(True)
        self.setMinimumHeight(155)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        self.paths_dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("LocalOCR", "LocalOCR")
        self.setWindowTitle(f"Local OCR {__version__}")
        self.resize(1080, 840)
        self.setMinimumSize(820, 640)
        self.process: QProcess | None = None
        self.job_temp = None
        self.job_path = None
        self.scan_result = None
        self.project_items = {}
        self.buffer = b""
        self.event_offset = 0
        self.event_timer = QTimer(self)
        self.event_timer.setInterval(100)
        self.event_timer.timeout.connect(self.read_events)
        self.had_terminal = False
        self.last_output = ""
        self.document_results = {}
        self.current_operation = ""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        heading = QHBoxLayout()
        title = label("Local OCR")
        title.setObjectName("title")
        heading.addWidget(title)
        heading.addStretch()
        badge = label("LOCAL · SIN APIs DE IA")
        badge.setWordWrap(False)
        badge.setObjectName("badge")
        heading.addWidget(badge)
        layout.addLayout(heading)
        layout.addWidget(
            label(
                "Documentos buscables y contexto de código. Tus archivos permanecen en tu computadora.", True
            )
        )
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.build_documents()
        self.build_projects()
        self.build_settings()
        output = QHBoxLayout()
        output.addWidget(label("Guardar en"))
        default_output = str(Path.home() / "Documents" / "Local OCR")
        self.output_edit = QLineEdit(str(self.settings.value("output", default_output)))
        self.output_edit.setReadOnly(True)
        output.addWidget(self.output_edit, 1)
        output.addWidget(button("Elegir carpeta", self.choose_output))
        self.output_row = QWidget()
        self.output_row.setLayout(output)
        layout.addWidget(self.output_row)
        self.status = label("Listo. Agrega documentos o selecciona un proyecto.", True)
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        actions.addWidget(self.progress, 1)
        self.cancel_button = button("Cancelar", self.cancel_job)
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        self.open_button = button("Abrir resultados", self.open_output)
        self.open_button.setEnabled(False)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(105)
        self.log.setPlaceholderText(
            "Aquí aparecerán resultados, avisos y errores. No se envían a ningún servidor."
        )
        self.log.document().setMaximumBlockCount(250)
        layout.addWidget(self.log)

    def build_documents(self):
        page, layout = scroll_page()
        self.tabs.addTab(page, "Documentos")
        layout.addWidget(label("PDF o Word → PDF con texto seleccionable + Markdown"))
        layout.addWidget(
            label(
                "Arrastra archivos a la lista. Cada conversión crea una carpeta nueva con sus dos salidas y un informe.",
                True,
            )
        )
        row = QHBoxLayout()
        row.addWidget(button("Agregar documentos", self.choose_documents))
        row.addWidget(button("Quitar seleccionados", self.remove_documents))
        row.addWidget(button("Vaciar lista", lambda: self.clear_documents()))
        row.addStretch()
        row.addWidget(button("Generar PDF + Markdown", self.start_documents, True))
        layout.addLayout(row)
        self.files = FileTable()
        self.files.paths_dropped.connect(self.add_documents)
        self.files.cellDoubleClicked.connect(self.open_document_result)
        layout.addWidget(self.files, 1)
        options = QGroupBox("Opciones de conversión")
        form = QFormLayout(options)
        self.language = QComboBox()
        for title, value in (("Español + inglés", "spa+eng"), ("Español", "spa"), ("Inglés", "eng")):
            self.language.addItem(title, value)
        form.addRow("Idioma", self.language)
        self.mode = QComboBox()
        self.mode.addItem("Automático: texto nativo e imágenes (recomendado)", "auto")
        self.mode.addItem("Solo páginas sin texto (omite imágenes de páginas mixtas)", "missing")
        self.mode.addItem("Forzar OCR: rasteriza todas las páginas", "force")
        form.addRow("Modo", self.mode)
        self.dpi = QComboBox()
        for value in (200, 300, 400):
            self.dpi.addItem(f"{value} DPI", value)
        self.dpi.setCurrentIndex(1)
        form.addRow("Resolución OCR", self.dpi)
        self.rotate = QCheckBox("Corregir páginas giradas (requiere idioma osd)")
        self.deskew = QCheckBox("Enderezar escaneos; solo disponible en modo Forzar")
        self.deskew.setEnabled(False)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.extract_images = QCheckBox("Extraer imágenes al Markdown (excepto escaneos de página completa)")
        self.tables = QCheckBox("Intentar reconocer tablas; revisar el resultado")
        self.tables.setChecked(True)
        for box in (self.rotate, self.deskew, self.extract_images, self.tables):
            form.addRow(box)
        layout.addWidget(options)
        layout.addWidget(
            label(
                "El PDF conserva su aspecto en el modo automático; Markdown reconstruye el contenido, no el diseño exacto. "
                "El OCR y el orden de lectura pueden requerir correcciones. Word necesita LibreOffice.",
                True,
            )
        )

    def build_projects(self):
        page, layout = scroll_page()
        self.tabs.addTab(page, "Proyectos de código")
        layout.addWidget(label("Elige el contexto que realmente necesita tu LLM"))
        row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setReadOnly(True)
        self.root_edit.setPlaceholderText("Selecciona una carpeta; no se ejecutará su código")
        row.addWidget(self.root_edit, 1)
        row.addWidget(button("Seleccionar proyecto", self.choose_project))
        layout.addLayout(row)
        opts = QHBoxLayout()
        opts.addWidget(label("Tokens estimados / parte"))
        self.token_budget = QSpinBox()
        self.token_budget.setRange(1000, 500000)
        self.token_budget.setSingleStep(1000)
        self.token_budget.setValue(12000)
        opts.addWidget(self.token_budget)
        opts.addWidget(label("Máximo MB / archivo"))
        self.file_limit = QSpinBox()
        self.file_limit.setRange(1, 20)
        self.file_limit.setValue(1)
        self.file_limit.valueChanged.connect(self.invalidate_scan)
        opts.addWidget(self.file_limit)
        self.include_locks = QCheckBox("Incluir lockfiles")
        self.include_locks.toggled.connect(self.invalidate_scan)
        opts.addWidget(self.include_locks)
        layout.addLayout(opts)
        self.exclusions = QLineEdit()
        self.exclusions.setPlaceholderText(
            "Exclusiones adicionales separadas por ;   ej.: tests/; *.csv; public/assets/"
        )
        self.exclusions.textChanged.connect(self.invalidate_scan)
        layout.addWidget(self.exclusions)
        actions = QHBoxLayout()
        actions.addWidget(button("Analizar proyecto", self.start_scan, True))
        self.export_button = button("Exportar a Markdown", self.start_export, True)
        self.export_button.setEnabled(False)
        actions.addWidget(self.export_button)
        actions.addWidget(button("Marcar todos", lambda: self.check_all(True)))
        actions.addWidget(button("Desmarcar todos", lambda: self.check_all(False)))
        actions.addStretch()
        layout.addLayout(actions)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtrar archivos por ruta (no cambia la selección)")
        self.filter_edit.textChanged.connect(self.filter_tree)
        layout.addWidget(self.filter_edit)
        splitter = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Archivos incluidos", "Tokens ≈"])
        self.tree.setColumnWidth(0, 330)
        self.tree.setMinimumHeight(180)
        self.tree.itemChanged.connect(self.selection_changed)
        self.tree.itemClicked.connect(self.preview_source)
        self.tree.setAlternatingRowColors(True)
        splitter.addWidget(self.tree)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setPlaceholderText(
            "Selecciona un archivo para revisar su contenido antes de exportarlo."
        )
        splitter.addWidget(self.preview)
        splitter.setSizes([530, 450])
        layout.addWidget(splitter, 1)
        self.selection_label = label("Sin analizar.", True)
        layout.addWidget(self.selection_label)
        layout.addWidget(
            label(
                "Se respetan .gitignore, límites de tamaño y exclusiones de secretos. La detección no es infalible: "
                "revisa los Markdown antes de compartirlos. Los tokens son aproximados, no una garantía del límite del modelo.",
                True,
            )
        )

    def build_settings(self):
        page, layout = scroll_page()
        self.tabs.addTab(page, "Ajustes y diagnóstico")
        layout.addWidget(label("Componentes locales"))
        layout.addWidget(
            label(
                "Deja las rutas vacías para detección automática. No necesitas claves API. "
                "El módulo de código funciona sin Tesseract ni LibreOffice.",
                True,
            )
        )
        self.setting_fields = {}
        for key, title in (
            ("tesseract", "Tesseract OCR"),
            ("soffice", "LibreOffice"),
            ("tessdata", "Carpeta de idiomas tessdata"),
        ):
            row = QHBoxLayout()
            row.addWidget(label(title))
            field = QLineEdit(str(self.settings.value(key, "")))
            field.setPlaceholderText("Detectar automáticamente")
            self.setting_fields[key] = field
            field.editingFinished.connect(self.save_settings)
            row.addWidget(field, 1)
            row.addWidget(button("Buscar…", lambda checked=False, k=key: self.choose_dependency(k)))
            layout.addLayout(row)
        layout.addWidget(button("Comprobar componentes e idiomas", self.start_diagnosis, True))
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMinimumHeight(200)
        layout.addWidget(self.diagnostics)
        layout.addWidget(label("Privacidad y límites", False))
        layout.addWidget(
            label(
                "• El programa no sube documentos ni código y no usa servicios de IA.\n"
                "• La instalación inicial sí descarga dependencias; después puede funcionar sin internet.\n"
                "• Procesa solamente documentos de confianza; no es un sandbox de seguridad.\n"
                "• No modifica PDFs protegidos o con campos de firma digital.\n"
                "• Un PDF con OCR no garantiza reconocimiento perfecto ni reconstrucción de fórmulas.\n"
                "• Los archivos se procesan en un proceso separado y las salidas completas se publican al terminar.",
                True,
            )
        )
        layout.addStretch()

    def save_settings(self):
        for key, field in self.setting_fields.items():
            self.settings.setValue(key, field.text().strip())
        self.settings.setValue("output", self.output_edit.text())

    def dependency_settings(self):
        return {key: field.text().strip() for key, field in self.setting_fields.items()}

    def choose_dependency(self, key):
        if key == "tessdata":
            value = QFileDialog.getExistingDirectory(self, "Carpeta con archivos .traineddata")
        else:
            value, _ = QFileDialog.getOpenFileName(self, "Seleccionar ejecutable")
        if value:
            self.setting_fields[key].setText(value)
            self.save_settings()

    def choose_output(self):
        directory = QFileDialog.getExistingDirectory(self, "Guardar resultados", self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)
            self.save_settings()
            self.invalidate_scan()

    def choose_documents(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Agregar documentos", "", "Documentos (*.pdf *.docx *.doc)"
        )
        self.add_documents(files)

    def add_documents(self, paths):
        current = {self.files.item(i, 0).data(Qt.ItemDataRole.UserRole) for i in range(self.files.rowCount())}
        for value in paths:
            path = Path(value)
            if path.suffix.lower() not in {".pdf", ".docx", ".doc"} or not path.is_file():
                continue
            full = str(path.resolve())
            if full in current:
                continue
            current.add(full)
            index = self.files.rowCount()
            self.files.insertRow(index)
            item = QTableWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, full)
            item.setToolTip(full)
            self.files.setItem(index, 0, item)
            self.files.setItem(index, 1, QTableWidgetItem("Pendiente"))

    def remove_documents(self):
        for index in sorted({i.row() for i in self.files.selectedIndexes()}, reverse=True):
            self.files.removeRow(index)
        self.document_results.clear()

    def clear_documents(self):
        self.files.setRowCount(0)
        self.document_results.clear()

    def mode_changed(self):
        force = self.mode.currentData() == "force"
        self.deskew.setEnabled(force)
        if not force:
            self.deskew.setChecked(False)

    def start_documents(self):
        if self.files.rowCount() == 0:
            self.info("Agrega al menos un documento.")
            return
        if self.mode.currentData() == "force":
            if (
                QMessageBox.question(
                    self,
                    "Forzar OCR",
                    "Este modo rasteriza las páginas: vectores y formularios pueden perder propiedades. "
                    "El original se conserva. ¿Continuar?",
                )
                != QMessageBox.StandardButton.Yes
            ):
                return
        self.document_results.clear()
        for index in range(self.files.rowCount()):
            self.files.item(index, 1).setText("Pendiente")
        self.start_job(
            {
                "operation": "documents",
                "sources": [
                    self.files.item(i, 0).data(Qt.ItemDataRole.UserRole) for i in range(self.files.rowCount())
                ],
                "output": self.output_edit.text(),
                "settings": self.dependency_settings(),
                "options": {
                    "language": self.language.currentData(),
                    "mode": self.mode.currentData(),
                    "dpi": self.dpi.currentData(),
                    "rotate": self.rotate.isChecked(),
                    "deskew": self.deskew.isChecked(),
                    "images": self.extract_images.isChecked(),
                    "tables": self.tables.isChecked(),
                },
            }
        )

    def choose_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar proyecto")
        if directory:
            self.root_edit.setText(directory)
            self.invalidate_scan()

    def invalidate_scan(self, *_):
        self.scan_result = None
        self.project_items = {}
        if hasattr(self, "tree"):
            self.tree.clear()
            self.preview.clear()
            self.export_button.setEnabled(False)
            self.selection_label.setText("Vuelve a analizar para actualizar los archivos y las exclusiones.")

    def start_scan(self):
        if not self.root_edit.text():
            self.info("Selecciona una carpeta de proyecto.")
            return
        self.invalidate_scan()
        self.start_job(
            {
                "operation": "scan",
                "root": self.root_edit.text(),
                "output": self.output_edit.text(),
                "options": {
                    "max_file_bytes": self.file_limit.value() * 1_000_000,
                    "chunk_tokens": self.token_budget.value(),
                    "include_locks": self.include_locks.isChecked(),
                    "extra_excludes": self.exclusions.text().replace(";", "\n"),
                },
            }
        )

    def populate_tree(self, result):
        self.scan_result = result
        self.tree.blockSignals(True)
        self.tree.clear()
        self.project_items = {}
        folders = {"": self.tree.invisibleRootItem()}
        for info in result["files"]:
            parts = info["path"].split("/")
            parent = folders[""]
            for i, folder in enumerate(parts[:-1]):
                key = "/".join(parts[: i + 1])
                if key not in folders:
                    item = QTreeWidgetItem(parent, [folder])
                    item.setFlags(
                        item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable
                    )
                    item.setCheckState(0, Qt.CheckState.Checked)
                    folders[key] = item
                parent = folders[key]
            item = QTreeWidgetItem(parent, [parts[-1], f"{info['tokens']:,}"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setData(0, Qt.ItemDataRole.UserRole, info)
            item.setToolTip(0, info["path"])
            item.setCheckState(0, Qt.CheckState.Checked)
            self.project_items[info["path"]] = item
        self.tree.expandToDepth(0)
        self.tree.blockSignals(False)
        self.selection_changed()
        self.filter_tree(self.filter_edit.text())
        excluded = result["excluded"]
        self.log.appendPlainText(
            f"Análisis: {len(result['files'])} archivos; {len(excluded)} exclusiones. No se ejecutó código."
        )
        for item in excluded[:40]:
            self.log.appendPlainText(f"Omitido: {item['path']} — {item['reason']}")
        if len(excluded) > 40:
            self.log.appendPlainText("El informe de exportación incluirá las demás exclusiones.")

    def check_all(self, checked):
        self.tree.blockSignals(True)
        for item in self.project_items.values():
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self.selection_changed()

    def selection_changed(self, *_):
        selected = [
            item.data(0, Qt.ItemDataRole.UserRole)
            for item in self.project_items.values()
            if item.checkState(0) == Qt.CheckState.Checked
        ]
        total = sum(info["tokens"] for info in selected)
        self.selection_label.setText(
            f"{len(selected)} archivos seleccionados · {total:,} tokens estimados de código (sin encabezados)"
        )
        self.export_button.setEnabled(bool(selected) and self.process is None)

    def filter_tree(self, text):
        text = text.casefold()

        def visit(item):
            info = item.data(0, Qt.ItemDataRole.UserRole)
            if info:
                visible = text in info["path"].casefold()
            else:
                children = [visit(item.child(i)) for i in range(item.childCount())]
                visible = any(children)
            item.setHidden(not visible)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            visit(self.tree.topLevelItem(i))

    def preview_source(self, item, _column):
        info = item.data(0, Qt.ItemDataRole.UserRole)
        if not info or not self.scan_result:
            return
        from .projects import ProjectOptions, checked_text

        try:
            text = checked_text(
                Path(self.scan_result["root"]), info, ProjectOptions(**self.scan_result["options"])
            )
            self.preview.setPlainText(
                text[:100000]
                + (
                    "\n\n[VISTA PREVIA TRUNCADA; la exportación conserva el archivo completo]"
                    if len(text) > 100000
                    else ""
                )
            )
        except Exception as exc:
            self.preview.setPlainText(str(exc))

    def start_export(self):
        if not self.scan_result:
            return
        self.scan_result["options"]["chunk_tokens"] = self.token_budget.value()
        selected = [
            path for path, item in self.project_items.items() if item.checkState(0) == Qt.CheckState.Checked
        ]
        self.start_job(
            {
                "operation": "export",
                "scan": self.scan_result,
                "selected": selected,
                "output": self.output_edit.text(),
            }
        )

    def start_diagnosis(self):
        self.save_settings()
        self.start_job({"operation": "diagnose", "settings": self.dependency_settings()})

    def start_job(self, job):
        if self.process is not None:
            return
        self.save_settings()
        self.current_operation = job["operation"]
        self.job_temp = tempfile.TemporaryDirectory(prefix="localocr-job-")
        self.job_path = Path(self.job_temp.name) / "job.json"
        write_json(self.job_path, job)
        self.buffer = b""
        self.event_offset = 0
        self.had_terminal = False
        self.process = QProcess(self)
        command = application_command("--worker", str(self.job_path))
        self.process.setProgram(command[0])
        self.process.setArguments(command[1:])
        self.process.readyReadStandardError.connect(self.read_errors)
        self.process.finished.connect(self.job_finished)
        self.process.errorOccurred.connect(self.process_error)
        self.tabs.setEnabled(False)
        self.output_row.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status.setText("Iniciando proceso local…")
        self.progress.setRange(0, 0)
        self.process.start()
        self.event_timer.start()

    def read_errors(self):
        if self.process:
            value = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
            if value:
                self.log.appendPlainText(value[-4000:])

    def read_events(self):
        if not self.process:
            return
        path = self.job_path.with_suffix(".events.jsonl")
        if not path.exists():
            return
        with path.open("rb") as stream:
            stream.seek(self.event_offset)
            self.buffer += stream.read()
            self.event_offset = stream.tell()
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                self.log.appendPlainText(line.decode("utf-8", errors="replace")[:1000])
                continue
            self.handle_event(event)

    def handle_event(self, event):
        kind = event.get("type")
        if kind == "progress":
            self.status.setText(event["message"])
            total = event.get("total", 0)
            self.progress.setRange(0, total)
            if total:
                self.progress.setValue(event.get("current", 0))
        elif kind == "file_start":
            self.files.item(event["index"], 1).setText("Procesando…")
        elif kind == "file_done":
            result = event["result"]
            self.files.item(event["index"], 1).setText("Listo con avisos" if result["warnings"] else "Listo")
            self.document_results[event["index"]] = result
            self.set_output(result["output"])
            self.log.appendPlainText("Generado: " + result["output"])
            for warning in result["warnings"]:
                self.log.appendPlainText("Aviso: " + warning)
        elif kind == "file_error":
            self.files.item(event["index"], 1).setText("Error")
            self.files.item(event["index"], 1).setToolTip(event["message"])
            self.log.appendPlainText(event["message"])
        elif kind in {"error", "cancelled"}:
            self.had_terminal = True
            self.status.setText(event["message"].splitlines()[0][:200])
            self.log.appendPlainText(event["message"])
            for i in range(self.files.rowCount()):
                if self.files.item(i, 1).text() == "Procesando…":
                    self.files.item(i, 1).setText("Cancelado" if kind == "cancelled" else "Error")
        elif kind == "done":
            self.had_terminal = True
            # Solo aceptar la ruta de resultado dentro de nuestro directorio temporal.
            expected = self.job_path.with_suffix(".result.json")
            if Path(event["result_file"]) != expected:
                self.status.setText("Respuesta de proceso no válida.")
                return
            try:
                result = json.loads(expected.read_text(encoding="utf-8"))
                if self.current_operation == "scan":
                    self.populate_tree(result)
                    self.status.setText("Análisis terminado. Revisa y selecciona los archivos.")
                elif self.current_operation == "export":
                    self.set_output(result["output"])
                    self.status.setText(
                        f"Exportados {result['files']} archivos en {result['parts']} parte(s)."
                    )
                    self.log.appendPlainText("Generado: " + result["output"])
                elif self.current_operation == "diagnose":
                    self.diagnostics.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
                    self.status.setText("Diagnóstico terminado. Revisa componentes e idiomas.")
                else:
                    self.status.setText(
                        f"Lote terminado: {len(result['results'])} documento(s) generado(s), {len(result['errors'])} error(es)."
                    )
                self.progress.setRange(0, 100)
                self.progress.setValue(100)
            except Exception as exc:
                self.log.appendPlainText(str(exc))
                self.status.setText("No se pudo leer el resultado del proceso.")

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.had_terminal = True
            self.status.setText("No se pudo iniciar el proceso local.")
            self.job_finished(-1, QProcess.ExitStatus.CrashExit)

    def job_finished(self, _code, _status):
        self.event_timer.stop()
        self.read_events()
        self.read_errors()
        if not self.had_terminal:
            self.status.setText(
                "El proceso terminó inesperadamente. Revisa el registro; los originales se conservan."
            )
        self.tabs.setEnabled(True)
        self.output_row.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setRange(0, 100)
        if self.process:
            self.process.deleteLater()
            self.process = None
        if self.job_temp:
            self.job_temp.cleanup()
            self.job_temp = None
        self.selection_changed()

    def cancel_job(self):
        if self.process and self.job_path:
            self.job_path.with_suffix(".cancel").touch()
            self.status.setText("Cancelando de forma segura; puede tardar hasta terminar la página actual…")
            self.cancel_button.setEnabled(False)

    def set_output(self, value):
        self.last_output = value
        self.open_button.setEnabled(True)

    def open_output(self):
        if self.last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output))

    def open_document_result(self, row, _column):
        result = self.document_results.get(row)
        if result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(result["output"]))

    def info(self, message):
        QMessageBox.information(self, "Local OCR", message)

    def closeEvent(self, event: QCloseEvent):
        if self.process:
            self.info("Hay una operación en curso. Cancélala y espera a que termine antes de cerrar.")
            event.ignore()
            return
        self.save_settings()
        event.accept()


def launch() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Local OCR")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(THEME)
    window = MainWindow()
    window.show()
    return app.exec()
