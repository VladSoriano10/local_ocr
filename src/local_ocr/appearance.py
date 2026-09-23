"""Identidad visual nativa: alas, color y tipografía sin recursos de red."""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

# SVG propio: plumas y halo a la izquierda, membrana y cuerno a la derecha.
# Se incluye en Python para que funcione también en el ejecutable sin rutas externas.
WINGS = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 170">
<defs>
 <linearGradient id="light" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="#e1f5ff"/><stop offset=".5" stop-color="#6bbdda"/>
  <stop offset="1" stop-color="#32617c"/>
 </linearGradient>
 <linearGradient id="fire" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="#ffb184"/><stop offset=".5" stop-color="#d46565"/>
  <stop offset="1" stop-color="#673849"/>
 </linearGradient>
</defs>
<g fill="none" stroke="#9a879f" stroke-width=".7" opacity=".35">
 <circle cx="210" cy="91" r="67"/><circle cx="210" cy="91" r="54"/>
 <path d="M122 91H298M210 8V165M154 35L266 147M154 147L266 35"/>
</g>
<g fill="url(#light)" stroke="#b5dce9" stroke-width=".6" stroke-linejoin="round">
 <path d="M201 132C170 126 148 91 130 69C105 40 61 37 23 16C31 47 70 72 119 80C89 72 50 56 19 39C30 73 78 96 130 96C91 96 55 84 28 65C43 100 94 116 146 110C106 121 68 110 45 96C66 124 111 133 163 124C134 136 105 139 80 128C104 151 159 154 201 132Z"/>
 <path d="M38 30C111 61 140 61 192 126M42 56C89 87 143 77 181 122M52 87C96 111 132 94 169 119"
  fill="none" stroke="#172f48" stroke-width="2"/>
</g>
<ellipse cx="164" cy="31" rx="31" ry="9" transform="rotate(-14 164 31)"
 fill="none" stroke="#dbbb7b" stroke-width="2.3"/>
<g fill="url(#fire)" stroke="#ef9d86" stroke-width=".8" stroke-linejoin="round">
 <path d="M220 134C236 104 238 80 266 67L394 19L371 54L402 75C374 64 344 76 337 109C315 94 286 107 279 134C257 116 236 125 220 134Z"/>
 <path d="M222 133C251 81 305 63 394 19M267 68C292 74 318 87 337 109M267 68C274 91 276 114 279 134M300 57C336 54 377 58 402 75"
  fill="none" stroke="#512633" stroke-width="2.5"/>
 <path d="M238 63C254 54 263 26 251 12C255 36 238 39 228 47Z"/>
</g>
<path d="M184 68L210 141L236 68H223L210 111L197 68Z" fill="#ece4d8"/>
<path d="M210 141L210 111L223 68H236Z" fill="#d1a9ac"/>
<path d="M210 52L215 59L210 66L205 59Z" fill="#dbbb7b"/>
</svg>"""


def emblem(size: int = 96) -> QPixmap:
    pixmap = QPixmap(size * 2, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(WINGS.encode())).render(painter)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    return QIcon(emblem(128))


PALETTES = (
    ("#91d5ed", "#15323e", "#bceafa", "#122330"),
    ("#efaa92", "#402c32", "#ffd0b7", "#2a1c27"),
    ("#c4b5ec", "#2d2740", "#e2d6ff", "#201e32"),
)


def theme_for(index: int = 0) -> str:
    accent, selected, hover, glow = PALETTES[min(max(index, 0), 2)]
    return (
        """
QMainWindow, QWidget { background: #0c1019; color: #e4e7ef; font-size: 13px;
    font-family: "Segoe UI", "DejaVu Sans", sans-serif; }
QWidget#central { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
    stop:0 #111b28, stop:0.4 #0c1019, stop:1 #211621); }
QWidget#page, QWidget#panel, QWidget#scrollBody { background: transparent; }
QLabel { background: transparent; }
QLabel#brand { font-family: "Georgia", "DejaVu Serif", serif; font-size: 25px;
    font-weight: 700; letter-spacing: 4px; color: #f5eee5; }
QLabel#muted { color: #a1abbc; }
QLabel#eyebrow { color: ACCENT; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#sectionTitle { font-size: 15px; font-weight: 600; color: #f0eae5; }
QLabel#badge { color: #b9d4c4; background: #172923; border: 1px solid #2c473e;
    padding: 6px 12px; border-radius: 13px; font-size: 11px; }
QLabel#counter { color: ACCENT; font-size: 11px; padding: 4px 8px;
    background: SELECTED; border-radius: 5px; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { padding: 12px 20px; margin: 0 16px 6px 0; color: #a1abbc;
    border: none; border-bottom: 2px solid transparent; background: transparent; }
QTabBar::tab:selected { color: ACCENT; border-bottom: 2px solid ACCENT; }
QTabBar::tab:hover { color: #ffffff; background: #182132; }
QGroupBox { background: #111722; border: 1px solid #2a3343; border-radius: 9px;
    margin-top: 9px; padding: 16px 12px 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px;
    color: ACCENT; font-size: 11px; font-weight: 600; }
QPushButton { background: #1b2535; border: 1px solid #354359; border-radius: 6px;
    padding: 8px 12px; color: #dee5f0; }
QPushButton:hover { background: #29374b; border-color: #60758b; }
QPushButton:focus { border: 1px solid ACCENT; }
QPushButton:pressed { background: SELECTED; }
QPushButton#primary { background: ACCENT; color: #151d28; border: 1px solid ACCENT;
    font-weight: 700; padding: 10px 14px; }
QPushButton#primary:hover { background: HOVER; }
QPushButton:disabled, QPushButton#primary:disabled { background: #18202c;
    color: #697688; border-color: #273344; }
QPushButton#quiet { background: transparent; border: 1px solid #303d50; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #0c121d;
    border: 1px solid #303c50; padding: 7px; border-radius: 5px;
    selection-background-color: SELECTED; selection-color: #ffffff; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid ACCENT; }
QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #182235; selection-background-color: SELECTED; }
QTableWidget, QTreeWidget { background: #0b111b; alternate-background-color: #101a28;
    border: 1px solid #2b3749; border-radius: 6px; selection-background-color: SELECTED;
    selection-color: #ffffff; }
QTableWidget::item, QTreeWidget::item { padding: 5px 4px; border: none; }
QHeaderView::section { background: #172132; padding: 9px 8px; border: none;
    color: #aebdd1; font-size: 11px; }
QTableCornerButton::section { background: #172132; border: none; }
QProgressBar { border: none; background: #1b2738; border-radius: 3px; max-height: 6px; }
QProgressBar::chunk { background: ACCENT; border-radius: 3px; }
QCheckBox { spacing: 7px; padding: 3px 0; background: transparent; }
QCheckBox::indicator { width: 15px; height: 15px; }
QCheckBox::indicator:checked { background: ACCENT; border: 3px solid #35495b; border-radius: 3px; }
QCheckBox::indicator:unchecked { background: #0d1520; border: 1px solid #54647c; border-radius: 3px; }
QCheckBox:disabled { color: #788394; }
QSplitter::handle { background: #253147; width: 1px; height: 1px; margin: 4px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 9px; background: transparent; margin: 0; }
QScrollBar::handle:vertical { background: #3c4b62; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 9px; background: transparent; margin: 0; }
QScrollBar::handle:horizontal { background: #3c4b62; border-radius: 4px; min-width: 25px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QToolTip { color: #e5e7eb; background: #1f2937; border: 1px solid #64748b; }
""".replace("ACCENT", accent)
        .replace("SELECTED", selected)
        .replace("HOVER", hover)
        .replace("GLOW", glow)
    )


THEME = theme_for()


class DualityBanner(QWidget):
    def __init__(self, index: int, eyebrow: str, title: str, description: str):
        super().__init__()
        self.index = index
        self.setObjectName("panel")
        self.setFixedHeight(116)
        self.renderer = QSvgRenderer(QByteArray(WINGS.encode()), self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 12, 20, 14)
        words = QVBoxLayout()
        words.setSpacing(5)
        for text, style in ((eyebrow, "eyebrow"), (title, "heroTitle"), (description, "muted")):
            item = QLabel(text)
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setObjectName(style)
            if style == "heroTitle":
                item.setStyleSheet('font-family: "Georgia", "DejaVu Serif", serif; font-size: 26px;')
            words.addWidget(item)
        layout.addLayout(words)
        layout.addStretch(1)
        layout.addSpacing(240)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(PALETTES[self.index][3]))
        gradient.setColorAt(0.6, QColor("#111823"))
        gradient.setColorAt(1, QColor("#271a27"))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor("#354051"), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 9, 9)
        painter.setOpacity(0.9)
        self.renderer.render(painter, QRectF(self.width() - 300, 0, 278, 115))
        painter.end()
