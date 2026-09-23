from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, QSettings, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QColor, QDesktopServices, QFont, QPainter
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
from .appearance import THEME, DualityBanner, app_icon, emblem, theme_for
from .common import application_command, write_json


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
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        widget.setObjectName("primary")
    return widget


def scroll_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    body.setObjectName("scrollBody")
    layout = QVBoxLayout(body)
    layout.setContentsMargins(2, 2, 8, 2)
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
        self.setMinimumHeight(130)
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.verticalHeader().setDefaultSectionSize(36)
        self.setAlternatingRowColors(True)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor("#9aadc5"))
            painter.drawText(
                self.viewport().rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Arrastra aquí tus PDF o Word\n\nO pulsa «Agregar documentos» para comenzar.",
            )
            painter.end()

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
        self.setWindowTitle(f"VladTor · Local OCR {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1240, 860)
        self.setMinimumSize(980, 700)
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
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(emblem(36))
        mark.setAccessibleName("Ala de ángel y ala de demonio")
        heading.addWidget(mark)
        identity = QVBoxLayout()
        identity.setSpacing(2)
        title = label("VLADTOR")
        title.setObjectName("brand")
        identity.addWidget(title)
        subtitle = label(f"LOCAL OCR  /  DUALIDAD  /  {__version__}", True)
        subtitle.setWordWrap(False)
        subtitle.setStyleSheet("font-size: 10px; letter-spacing: 2px;")
        identity.addWidget(subtitle)
        heading.addLayout(identity)
        heading.addStretch()
        badge = label("LOCAL  ·  SIN APIs DE IA")
        badge.setWordWrap(False)
        badge.setObjectName("badge")
        badge.setFixedHeight(28)
        heading.addWidget(badge)
        layout.addLayout(heading)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        layout.addWidget(self.tabs, 1)
        self.build_documents()
        self.build_projects()
        self.build_settings()
        self.tabs.currentChanged.connect(self.change_realm)
        output = QHBoxLayout()
        output.setContentsMargins(0, 2, 0, 0)
        output.addWidget(label("Guardar en", True))
        default_output = str(Path.home() / "Documents" / "Local OCR")
        self.output_edit = QLineEdit(str(self.settings.value("output", default_output)))
        self.output_edit.setReadOnly(True)
        output.addWidget(self.output_edit, 1)
        output.addWidget(button("Elegir carpeta", self.choose_output))
        self.output_row = QWidget()
        self.output_row.setObjectName("panel")
        self.output_row.setLayout(output)
        layout.addWidget(self.output_row)
        actions = QHBoxLayout()
        self.status = label("Listo. Agrega documentos o selecciona un proyecto.", True)
        actions.addWidget(self.status, 1)
        self.cancel_button = button("Cancelar", self.cancel_job)
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        self.open_button = button("Abrir resultados", self.open_output)
        self.open_button.setEnabled(False)
        actions.addWidget(self.open_button)
        self.log_toggle = button("Ver registro", self.toggle_log)
        self.log_toggle.setCheckable(True)
        self.log_toggle.setObjectName("quiet")
        actions.addWidget(self.log_toggle)
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        self.log.setPlaceholderText("Resultados, avisos y errores del procesamiento local.")
        self.log.document().setMaximumBlockCount(250)
        self.log.setVisible(False)
        layout.addWidget(self.log)
        self.change_realm(0)

    def change_realm(self, index):
        self.setStyleSheet(theme_for(index))

    def toggle_log(self, checked):
        self.log.setVisible(checked)
        self.log_toggle.setText("Ocultar registro" if checked else "Ver registro")

    def make_page(self, title, index, eyebrow, hero, description):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(14)
        self.tabs.addTab(page, title)
        layout.addWidget(DualityBanner(index, eyebrow, hero, description))
        scroll, content = scroll_page()
        content.setContentsMargins(0, 0, 0, 2)
        layout.addWidget(scroll, 1)
        return content

    def build_documents(self):
        layout = self.make_page(
            "01   Documentos OCR",
            0,
            "ÁNGEL  /  REVELAR",
            "Del papel a las palabras.",
            "PDF y Word → PDF con texto seleccionable + Markdown",
        )
        columns = QSplitter()
        columns.setChildrenCollapsible(False)
        columns.setMinimumHeight(430)
        layout.addWidget(columns, 1)
        left = QWidget()
        left.setObjectName("panel")
        left.setMinimumWidth(310)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(10)
        options_scroll, options_layout = scroll_page()
        options = QGroupBox("01 / CONFIGURACIÓN")
        form = QVBoxLayout(options)
        form.setSpacing(8)
        self.language = QComboBox()
        for title, value in (("Español + inglés", "spa+eng"), ("Español", "spa"), ("Inglés", "eng")):
            self.language.addItem(title, value)
        form.addWidget(label("Idioma del documento", True))
        form.addWidget(self.language)
        self.mode = QComboBox()
        self.mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.mode.setMinimumContentsLength(16)
        self.mode.addItem("Automático · recomendado", "auto")
        self.mode.addItem("Solo páginas sin texto", "missing")
        self.mode.addItem("Forzar OCR en todas las páginas", "force")
        form.addWidget(label("Tratamiento del texto", True))
        form.addWidget(self.mode)
        self.mode_hint = label("Conserva texto nativo y reconoce el texto de imágenes.", True)
        self.mode_hint.setStyleSheet("font-size: 11px;")
        form.addWidget(self.mode_hint)
        self.dpi = QComboBox()
        for value in (200, 300, 400):
            self.dpi.addItem(f"{value} DPI", value)
        self.dpi.setCurrentIndex(1)
        form.addWidget(label("Resolución OCR", True))
        form.addWidget(self.dpi)
        self.rotate = QCheckBox("Corregir páginas giradas")
        self.rotate.setToolTip("Requiere el idioma osd instalado en Tesseract.")
        self.deskew = QCheckBox("Enderezar escaneos")
        self.deskew.setToolTip("Disponible en modo Forzar OCR.")
        self.deskew.setEnabled(False)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        self.extract_images = QCheckBox("Extraer imágenes al Markdown")
        self.extract_images.setToolTip("Omite los escaneos de página completa.")
        self.tables = QCheckBox("Reconocer tablas")
        self.tables.setToolTip("Reconocimiento básico; revisa las tablas complejas.")
        self.tables.setChecked(True)
        for box in (self.rotate, self.deskew, self.extract_images, self.tables):
            form.addWidget(box)
        options_layout.addWidget(options)
        options.setToolTip(
            "El PDF conserva su aspecto en modo automático; Markdown reconstruye el contenido. "
            "Word necesita LibreOffice."
        )
        options_layout.addStretch()
        left_layout.addWidget(options_scroll, 1)
        self.documents_button = button("Generar PDF + Markdown", self.start_documents, True)
        left_layout.addWidget(self.documents_button)
        columns.addWidget(left)
        right = QWidget()
        right.setObjectName("panel")
        right.setMinimumWidth(440)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)
        row = QHBoxLayout()
        row.addWidget(button("Agregar documentos", self.choose_documents))
        row.addWidget(button("Quitar", self.remove_documents))
        row.addWidget(button("Vaciar", self.clear_documents))
        row.addStretch()
        self.document_count = label("0 documentos")
        self.document_count.setObjectName("counter")
        row.addWidget(self.document_count)
        right_layout.addLayout(row)
        self.files = FileTable()
        self.files.paths_dropped.connect(self.add_documents)
        self.files.cellDoubleClicked.connect(self.open_document_result)
        self.files.itemSelectionChanged.connect(self.show_document_result)
        right_layout.addWidget(self.files, 1)
        results = QGroupBox("02 / RESULTADO · MARKDOWN")
        results_layout = QVBoxLayout(results)
        self.document_result_label = label(
            "Selecciona un documento terminado para revisar su resultado.", True
        )
        results_layout.addWidget(self.document_result_label)
        self.document_preview = QPlainTextEdit()
        self.document_preview.setReadOnly(True)
        self.document_preview.setFont(QFont("Consolas", 10))
        self.document_preview.setStyleSheet('font-family: "Consolas", "DejaVu Sans Mono", monospace;')
        self.document_preview.setMinimumHeight(100)
        self.document_preview.setPlaceholderText(
            "Aquí verás el Markdown real de tu documento.\n\n"
            "El PDF buscable y el archivo .md se guardan juntos en una carpeta nueva."
        )
        results_layout.addWidget(self.document_preview, 1)
        result_actions = QHBoxLayout()
        self.pdf_button = button("Abrir PDF", lambda: self.open_result_file("pdf"))
        self.markdown_button = button("Abrir Markdown", lambda: self.open_result_file("markdown"))
        self.copy_markdown_button = button("Copiar texto visible", self.copy_document_preview)
        self.copy_markdown_button.setToolTip(
            "Copia solo la vista previa; los documentos largos se muestran truncados."
        )
        for action in (self.pdf_button, self.markdown_button, self.copy_markdown_button):
            action.setEnabled(False)
            result_actions.addWidget(action)
        result_actions.addStretch()
        results_layout.addLayout(result_actions)
        right_layout.addWidget(results, 2)
        columns.addWidget(right)
        columns.setSizes([340, 810])

    def build_projects(self):
        layout = self.make_page(
            "02   Proyectos de código",
            1,
            "DEMONIO  /  FORJAR",
            "Código convertido en contexto.",
            "Selecciona lo esencial. Exporta tu proyecto a Markdown para LLM.",
        )
        row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.setReadOnly(True)
        self.root_edit.setPlaceholderText("Selecciona una carpeta de código, en cualquier lenguaje")
        row.addWidget(self.root_edit, 1)
        row.addWidget(button("Seleccionar proyecto", self.choose_project))
        row.addWidget(button("Analizar proyecto", self.start_scan, True))
        layout.addLayout(row)
        columns = QSplitter()
        columns.setChildrenCollapsible(False)
        columns.setMinimumHeight(420)
        layout.addWidget(columns, 1)
        left = QWidget()
        left.setObjectName("panel")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(9)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtrar archivos por ruta…")
        self.filter_edit.setToolTip("El filtro visual no cambia los archivos seleccionados.")
        self.filter_edit.textChanged.connect(self.filter_tree)
        left_layout.addWidget(self.filter_edit)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Archivos del proyecto", "Tokens ≈"])
        self.tree.setColumnWidth(0, 280)
        self.tree.setMinimumHeight(150)
        self.tree.itemChanged.connect(self.selection_changed)
        self.tree.itemClicked.connect(self.preview_source)
        self.tree.setAlternatingRowColors(True)
        left_layout.addWidget(self.tree, 1)
        checks = QHBoxLayout()
        checks.addWidget(button("Marcar todos", lambda: self.check_all(True)))
        checks.addWidget(button("Desmarcar todos", lambda: self.check_all(False)))
        checks.addStretch()
        left_layout.addLayout(checks)
        filters = QGroupBox("FILTROS DE ANÁLISIS")
        form = QVBoxLayout(filters)
        limits = QHBoxLayout()
        limits.addWidget(label("MB / archivo", True))
        self.file_limit = QSpinBox()
        self.file_limit.setRange(1, 20)
        self.file_limit.setValue(1)
        self.file_limit.valueChanged.connect(self.invalidate_scan)
        limits.addWidget(self.file_limit)
        self.include_locks = QCheckBox("Incluir lockfiles")
        self.include_locks.toggled.connect(self.invalidate_scan)
        limits.addWidget(self.include_locks)
        form.addLayout(limits)
        self.exclusions = QLineEdit()
        self.exclusions.setPlaceholderText("Excluir: tests/; *.csv; public/assets/")
        self.exclusions.setToolTip("Patrones adicionales separados por punto y coma.")
        self.exclusions.textChanged.connect(self.invalidate_scan)
        form.addWidget(self.exclusions)
        note = label("Respeta .gitignore y omite binarios, dependencias y posibles secretos.", True)
        note.setStyleSheet("font-size: 11px;")
        form.addWidget(note)
        left_layout.addWidget(filters)
        columns.addWidget(left)
        right = QWidget()
        right.setObjectName("panel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)
        self.preview_path = label("VISTA PREVIA / SELECCIONA UN ARCHIVO")
        self.preview_path.setObjectName("eyebrow")
        right_layout.addWidget(self.preview_path)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setStyleSheet('font-family: "Consolas", "DejaVu Sans Mono", monospace;')
        self.preview.setPlaceholderText(
            "Revisa el contenido antes de exportarlo.\n\n"
            "Conservamos texto, comentarios e indentación.\n"
            "Tu proyecto se analiza sin ejecutar su código."
        )
        right_layout.addWidget(self.preview, 1)
        self.selection_label = label("Sin analizar. Selecciona un proyecto para comenzar.", True)
        right_layout.addWidget(self.selection_label)
        export = QHBoxLayout()
        export.addWidget(label("Tokens ≈ / parte", True))
        self.token_budget = QSpinBox()
        self.token_budget.setRange(1000, 500000)
        self.token_budget.setSingleStep(1000)
        self.token_budget.setValue(12000)
        self.token_budget.setToolTip(
            "Estimación local, incluye formato al exportar. Reserva margen para tu LLM."
        )
        export.addWidget(self.token_budget)
        export.addStretch()
        self.export_button = button("Exportar a Markdown", self.start_export, True)
        self.export_button.setEnabled(False)
        export.addWidget(self.export_button)
        right_layout.addLayout(export)
        hint = label(
            "El ahorro de tokens viene de seleccionar contexto relevante. "
            "Revisa el Markdown antes de compartirlo; los tokens y la detección de secretos son aproximados.",
            True,
        )
        hint.setStyleSheet("font-size: 11px;")
        right_layout.addWidget(hint)
        columns.addWidget(right)
        columns.setSizes([450, 700])

    def build_settings(self):
        layout = self.make_page(
            "03   Ajustes y diagnóstico",
            2,
            "EQUILIBRIO  /  CONFIGURAR",
            "Todo, en tu computadora.",
            "Configura los componentes que convierten tus documentos.",
        )
        page, content = scroll_page()
        layout.addWidget(page, 1)
        settings_group = QGroupBox("RUTAS DE COMPONENTES")
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(12)
        self.setting_fields = {}
        for key, title in (
            ("tesseract", "Tesseract OCR"),
            ("soffice", "LibreOffice"),
            ("tessdata", "Idiomas tessdata"),
        ):
            row = QHBoxLayout()
            field = QLineEdit(str(self.settings.value(key, "")))
            field.setPlaceholderText("Detectar automáticamente")
            self.setting_fields[key] = field
            field.editingFinished.connect(self.save_settings)
            row.addWidget(field, 1)
            row.addWidget(button("Buscar…", lambda checked=False, k=key: self.choose_dependency(k)))
            settings_layout.addRow(title, row)
        content.addWidget(settings_group)
        content.addWidget(
            label(
                "Tesseract reconoce escaneos; LibreOffice convierte Word. "
                "El módulo de código funciona sin estos programas. No necesitas claves API.",
                True,
            )
        )
        actions = QHBoxLayout()
        actions.addWidget(button("Comprobar componentes e idiomas", self.start_diagnosis, True))
        actions.addStretch()
        content.addLayout(actions)
        self.diagnostics = QPlainTextEdit()
        self.diagnostics.setReadOnly(True)
        self.diagnostics.setMinimumHeight(130)
        self.diagnostics.setPlaceholderText(
            "Pulsa «Comprobar componentes» para consultar el estado real y los idiomas instalados."
        )
        content.addWidget(self.diagnostics, 1)
        content.addWidget(
            label(
                "La instalación inicial descarga dependencias; luego puedes trabajar sin internet. "
                "Procesa documentos de confianza y revisa el reconocimiento de cifras, tablas y fórmulas. "
                "No se modifican los originales ni los PDF protegidos o firmados.",
                True,
            )
        )

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
        count = self.files.rowCount()
        self.document_count.setText(f"{count} documento" + ("s" if count != 1 else ""))

    def remove_documents(self):
        removed = {i.row() for i in self.files.selectedIndexes()}
        remaining = [i for i in range(self.files.rowCount()) if i not in removed]
        results = {
            new: self.document_results[old]
            for new, old in enumerate(remaining)
            if old in self.document_results
        }
        self.files.blockSignals(True)
        for index in sorted(removed, reverse=True):
            self.files.removeRow(index)
        self.document_results = results
        self.files.blockSignals(False)
        count = self.files.rowCount()
        self.document_count.setText(f"{count} documento" + ("s" if count != 1 else ""))
        self.show_document_result()

    def clear_documents(self):
        self.files.setRowCount(0)
        self.document_results.clear()
        self.document_count.setText("0 documentos")
        self.show_document_result()

    def mode_changed(self):
        force = self.mode.currentData() == "force"
        self.mode_hint.setText(
            {
                "auto": "Conserva texto nativo y reconoce el texto de imágenes.",
                "missing": "Omite imágenes si la página ya tiene texto. Revisa los PDF mixtos.",
                "force": "Rasteriza todas las páginas. Puede perder vectores y propiedades de formularios.",
            }[self.mode.currentData()]
        )
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
        self.show_document_result()
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

    def show_document_result(self):
        result = self.document_results.get(self.files.currentRow())
        for action in (self.pdf_button, self.markdown_button, self.copy_markdown_button):
            action.setEnabled(bool(result))
        self.document_preview.clear()
        if not result:
            self.document_result_label.setText("Selecciona un documento terminado para revisar su resultado.")
            return
        try:
            # Limitar solo la vista: el Markdown en disco conserva el contenido completo.
            with Path(result["markdown"]).open(encoding="utf-8") as stream:
                text = stream.read(100001)
            self.document_preview.setPlainText(text[:100000])
            name = Path(result["markdown"]).name
            suffix = " · vista truncada a 100.000 caracteres" if len(text) > 100000 else ""
            self.document_result_label.setText(name + suffix)
        except OSError as exc:
            self.document_result_label.setText("No se pudo cargar la vista previa.")
            self.log.appendPlainText(str(exc))
            self.copy_markdown_button.setEnabled(False)

    def open_result_file(self, key):
        result = self.document_results.get(self.files.currentRow())
        if result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(result[key]))

    def copy_document_preview(self):
        QApplication.clipboard().setText(self.document_preview.toPlainText())

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
            self.preview_path.setText("VISTA PREVIA / SELECCIONA UN ARCHIVO")
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
        self.preview_path.setText(info["path"])
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
            self.files.setCurrentCell(event["index"], 0)
            self.show_document_result()
            self.set_output(result["output"])
            self.log.appendPlainText("Generado: " + result["output"])
            for warning in result["warnings"]:
                self.log.appendPlainText("Aviso: " + warning)
        elif kind == "file_error":
            self.files.item(event["index"], 1).setText("Error")
            self.files.item(event["index"], 1).setToolTip(event["message"])
            self.log.appendPlainText(event["message"])
            self.log_toggle.setChecked(True)
            self.toggle_log(True)
        elif kind in {"error", "cancelled"}:
            self.had_terminal = True
            self.status.setText(event["message"].splitlines()[0][:200])
            self.log.appendPlainText(event["message"])
            self.log_toggle.setChecked(True)
            self.toggle_log(True)
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
