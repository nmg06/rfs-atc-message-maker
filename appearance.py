"""Thème officiel « Avionique Sobre » : sombre et clair, inspiré de l'aéronautique moderne."""
from PySide6.QtGui import QColor, QPalette
from pathlib import Path


def apply_palette(app, dark: bool) -> None:
    # Replacing the native style repolishes every widget (including hidden
    # dialogs). Install it once; a theme toggle only changes the palette.
    if not app.property('_rfs_fusion_initialized'):
        app.setStyle("Fusion")
        app.setProperty('_rfs_fusion_initialized', True)
    if app.property('_rfs_palette_mode') == ('dark' if dark else 'light'):
        return
    p = QPalette()
    colors = {
        QPalette.ColorRole.Window: "#0B1220" if dark else "#F1F5F9",
        QPalette.ColorRole.WindowText: "#E6EDF7" if dark else "#0F172A",
        QPalette.ColorRole.Base: "#0D1726" if dark else "#FFFFFF",
        QPalette.ColorRole.AlternateBase: "#121D2E" if dark else "#F8FAFC",
        QPalette.ColorRole.Text: "#E6EDF7" if dark else "#0F172A",
        QPalette.ColorRole.Button: "#1C2B40" if dark else "#E2E8F0",
        QPalette.ColorRole.ButtonText: "#E6EDF7" if dark else "#0F172A",
        QPalette.ColorRole.Highlight: "#2563EB",
        QPalette.ColorRole.HighlightedText: "#FFFFFF",
        QPalette.ColorRole.ToolTipBase: "#18263A" if dark else "#FFFFFF",
        QPalette.ColorRole.ToolTipText: "#E6EDF7" if dark else "#0F172A",
        QPalette.ColorRole.PlaceholderText: "#8B9CB3" if dark else "#64748B",
    }
    for role, color in colors.items():
        p.setColor(role, QColor(color))
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#7E8DA3"))
    app.setPalette(p)
    app.setProperty('_rfs_palette_mode', 'dark' if dark else 'light')


DARK_STYLESHEET = """
QWidget {
    font-family: "Inter", "Segoe UI";
    font-size: 14px;
    color: #E6EDF7;
    selection-background-color: #284B75;
    selection-color: #FFFFFF;
}
QMainWindow, QDialog, QWidget#appRoot {
    background: #0B1220;
}
QWidget#formBody, QScrollArea > QWidget > QWidget {
    background: #0B1220;
}
QLabel {
    background: transparent;
    border: none;
}
QLabel[role="title"], QLabel#title {
    font-size: 23px;
    font-weight: 700;
    color: #F8FAFC;
}
QLabel[role="section"], QLabel#section {
    font-size: 15px;
    font-weight: 600;
    color: #93C5FD;
}
QLabel[role="muted"], QLabel#muted {
    color: #A7B5C9;
    font-size: 12px;
}
QLabel#badge {
    background-color: #147D59;
    color: #FFFFFF;
    border-radius: 8px;
    padding: 3px 9px;
    font-weight: 700;
    font-size: 12px;
}
QLabel#danger, QLabel[role="error"] {
    color: #FF7B86;
    font-weight: 700;
}
QFrame#card {
    background: #121D2E;
    border: 1px solid #27364B;
    border-radius: 12px;
}
QGroupBox {
    background: #121D2E;
    border: 1px solid #27364B;
    border-radius: 12px;
    margin-top: 15px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
    font-size: 14px;
    color: #93C5FD;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 2px;
    padding: 2px 8px;
    background-color: #18263A;
    border: 1px solid #35465E;
    border-radius: 6px;
    color: #E6EDF7;
    font-size: 12px;
    font-weight: 600;
}
QLineEdit, QComboBox, QAbstractSpinBox {
    background: #0D1726;
    color: #E6EDF7;
    border: 1px solid #35465E;
    border-radius: 8px;
    padding: 7px 11px;
    min-height: 22px;
    selection-background-color: #284B75;
}
QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {
    border-color: #617791;
}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {
    border-color: #60A5FA;
    background: #0F1B2C;
}
QLineEdit[invalid="true"], QComboBox[invalid="true"], QAbstractSpinBox[invalid="true"] {
    border: 1px solid #FF7B86;
    background: #271B29;
}
QComboBox QAbstractItemView {
    background: #18263A;
    color: #E6EDF7;
    border: 1px solid #35465E;
    border-radius: 8px;
    selection-background-color: #284B75;
    selection-color: #FFFFFF;
    outline: 0;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 8px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background: #263951;
}
QPushButton, QToolButton {
    background: #1C2B40;
    color: #E6EDF7;
    border: 1px solid #35465E;
    border-radius: 8px;
    padding: 8px 15px;
    min-height: 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover, QToolButton:hover {
    background: #263951;
    border-color: #617791;
}
QPushButton:pressed, QToolButton:pressed {
    background: #132238;
}
QPushButton:focus, QToolButton:focus {
    border: 1px solid #60A5FA;
}
QPushButton#primary, QPushButton[variant="primary"] {
    background: #2563EB;
    border: 1px solid #3B82F6;
    color: #FFFFFF;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#primary:hover, QPushButton[variant="primary"]:hover {
    background: #1D4ED8;
    border-color: #60A5FA;
}
QPushButton#copy, QPushButton[variant="success"] {
    background: #147D59;
    border: 1px solid #10B981;
    color: #FFFFFF;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#copy:hover, QPushButton[variant="success"]:hover {
    background: #116A4C;
    border-color: #34D399;
}
QPushButton:disabled, QToolButton:disabled,
QPushButton#primary:disabled, QPushButton#copy:disabled,
QPushButton[variant="primary"]:disabled, QPushButton[variant="success"]:disabled {
    background: #151F2D;
    border-color: #27364B;
    color: #7E8DA3;
}
QPlainTextEdit, QTextEdit {
    background: #0D1726;
    color: #F8FAFC;
    border: 1px solid #35465E;
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
}
QPlainTextEdit:focus, QTextEdit:focus {
    border-color: #60A5FA;
}
QTableWidget, QTableView {
    background: #101A29;
    alternate-background-color: #142133;
    color: #E6EDF7;
    border: 1px solid #27364B;
    border-radius: 8px;
    gridline-color: #27364B;
    selection-background-color: #284B75;
    selection-color: #FFFFFF;
}
QTableWidget::item, QTableView::item {
    padding: 8px;
    border: none;
}
QTableWidget::item:hover, QTableView::item:hover {
    background: #1C2E46;
}
QTableWidget::item:selected, QTableView::item:selected {
    background: #284B75;
    color: #FFFFFF;
}
QHeaderView::section {
    background: #18263A;
    color: #A7B5C9;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #27364B;
    font-weight: 600;
}
QTableCornerButton::section {
    background: #18263A;
    border: none;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #43566F;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:horizontal {
    background: #43566F;
    border-radius: 3px;
    min-width: 32px;
}
QScrollBar::handle:hover {
    background: #6B82A0;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    border: none;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QSplitter::handle {
    background: #1E2A3A;
    width: 4px;
}
QSplitter::handle:hover {
    background: #60A5FA;
}
QMenu, QToolTip {
    background: #18263A;
    color: #E6EDF7;
    border: 1px solid #35465E;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 18px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #284B75;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
    color: #E6EDF7;
}
"""

LIGHT_STYLESHEET = """
QWidget {
    font-family: "Inter", "Segoe UI";
    font-size: 14px;
    color: #0F172A;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}
QMainWindow, QDialog, QWidget#appRoot {
    background: #F1F5F9;
}
QWidget#formBody, QScrollArea > QWidget > QWidget {
    background: #F1F5F9;
}
QLabel {
    background: transparent;
    border: none;
}
QLabel[role="title"], QLabel#title {
    font-size: 23px;
    font-weight: 700;
    color: #0F172A;
}
QLabel[role="section"], QLabel#section {
    font-size: 15px;
    font-weight: 600;
    color: #1D4ED8;
}
QLabel[role="muted"], QLabel#muted {
    color: #64748B;
    font-size: 12px;
}
QLabel#badge {
    background-color: #DCFCE7;
    color: #166534;
    border: 1px solid #86EFAC;
    border-radius: 8px;
    padding: 3px 9px;
    font-weight: 700;
    font-size: 12px;
}
QLabel#danger, QLabel[role="error"] {
    color: #DC2626;
    font-weight: 700;
}
QFrame#card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
}
QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    margin-top: 15px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
    font-size: 14px;
    color: #1D4ED8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 2px;
    padding: 2px 8px;
    background-color: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    color: #334155;
    font-size: 12px;
    font-weight: 600;
}
QLineEdit, QComboBox, QAbstractSpinBox {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 7px 11px;
    min-height: 22px;
    selection-background-color: #2563EB;
}
QLineEdit:hover, QComboBox:hover, QAbstractSpinBox:hover {
    border-color: #94A3B8;
}
QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {
    border-color: #2563EB;
    background: #FCFDFE;
}
QLineEdit[invalid="true"], QComboBox[invalid="true"], QAbstractSpinBox[invalid="true"] {
    border: 1px solid #EF4444;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
    outline: 0;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 8px;
    border-radius: 4px;
}
QComboBox QAbstractItemView::item:hover {
    background: #F1F5F9;
}
QPushButton, QToolButton {
    background: #F1F5F9;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 8px 15px;
    min-height: 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover, QToolButton:hover {
    background: #E2E8F0;
    border-color: #94A3B8;
}
QPushButton:pressed, QToolButton:pressed {
    background: #CBD5E1;
}
QPushButton#primary, QPushButton[variant="primary"] {
    background: #2563EB;
    border: 1px solid #1D4ED8;
    color: #FFFFFF;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#primary:hover, QPushButton[variant="primary"]:hover {
    background: #1D4ED8;
}
QPushButton#copy, QPushButton[variant="success"] {
    background: #147D59;
    border: 1px solid #047857;
    color: #FFFFFF;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 700;
}
QPushButton#copy:hover, QPushButton[variant="success"]:hover {
    background: #116A4C;
}
QPushButton:disabled, QToolButton:disabled,
QPushButton#primary:disabled, QPushButton#copy:disabled,
QPushButton[variant="primary"]:disabled, QPushButton[variant="success"]:disabled {
    background: #F8FAFC;
    color: #94A3B8;
    border-color: #E2E8F0;
}
QPlainTextEdit, QTextEdit {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
}
QPlainTextEdit:focus, QTextEdit:focus {
    border-color: #2563EB;
}
QTableWidget, QTableView {
    background: #FFFFFF;
    alternate-background-color: #F8FAFC;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    gridline-color: #E2E8F0;
    selection-background-color: #2563EB;
    selection-color: #FFFFFF;
}
QTableWidget::item, QTableView::item {
    padding: 8px;
    border: none;
}
QTableWidget::item:hover, QTableView::item:hover {
    background: #F1F5F9;
}
QTableWidget::item:selected, QTableView::item:selected {
    background: #2563EB;
    color: #FFFFFF;
}
QHeaderView::section {
    background: #F8FAFC;
    color: #475569;
    padding: 10px 8px;
    border: none;
    border-bottom: 1px solid #CBD5E1;
    font-weight: 600;
}
QTableCornerButton::section {
    background: #F8FAFC;
    border: none;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 2px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 9px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:horizontal {
    background: #43566F;
    border-radius: 3px;
    min-width: 32px;
}
QScrollBar::handle:hover {
    background: #94A3B8;
}
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0;
    height: 0;
    border: none;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QSplitter::handle {
    background: #E2E8F0;
    width: 4px;
}
QSplitter::handle:hover {
    background: #2563EB;
}
QMenu, QToolTip {
    background: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 18px;
    border-radius: 4px;
}
QMenu::item:selected {
    background: #2563EB;
    color: #FFFFFF;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
    color: #0F172A;
}
"""

_STYLESHEET_CACHE: dict[bool, str] = {}


def get_stylesheet(dark: bool) -> str:
    if dark in _STYLESHEET_CACHE:
        return _STYLESHEET_CACHE[dark]
    base = DARK_STYLESHEET if dark else LIGHT_STYLESHEET
    check_icon = (Path(__file__).resolve().parent / 'assets' / 'check.svg').as_posix()
    surface, fg, muted, border = ('#121D2E', '#E6EDF7', '#A7B5C9', '#35465E') if dark else ('#FFFFFF', '#0F172A', '#475569', '#CBD5E1')
    result = base + (
        "    QWidget#formBody { background:transparent; }\n"
        "    QComboBox { padding-right:28px; }\n"
        "    QComboBox QLineEdit { border:none; background:transparent; padding:0; }\n"
        '    QPlainTextEdit#discordPreview { font-family:"JetBrains Mono", "Consolas"; font-size:14px; }\n'
        f"    QLabel#section {{ color:{fg}; font-size:16px; }}\n"
        f"    QLabel#muted {{ color:{muted}; }}\n"
        "    QSplitter::handle { background:transparent; }\n"
        f"    QSplitter::handle:hover {{ background:{border}; }}\n"
        f"    QTabWidget::pane {{ background:{surface}; border:1px solid {border}; border-radius:8px; padding:8px; }}\n"
        f"    QTabBar::tab {{ background:{surface}; color:{muted}; padding:10px 14px; border-bottom:2px solid transparent; }}\n"
        f"    QTabBar::tab:selected {{ color:{fg}; border-bottom:2px solid #60A5FA; }}\n"
        "    QPushButton#copy { background:#2563EB; border-color:#2563EB; color:#FFFFFF; }\n"
        "    QPushButton#copy:hover { background:#1D4ED8; border-color:#1D4ED8; }\n"
        "    QPushButton#copy:pressed { background:#1E40AF; }\n"
        "    QPushButton#copy:focus, QPushButton#primary:focus { border-color:#B5D7FF; }\n"
        f"    QPushButton#copy:disabled {{ background:{surface}; color:{muted}; border-color:{border}; }}\n"
        f"    QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{ background:{surface}; color:{muted}; border-color:{border}; }}\n"
        f"    QCheckBox::indicator {{ width:16px; height:16px; background:{surface}; border:1px solid {muted}; border-radius:4px; }}\n"
        f"    QCheckBox::indicator:checked {{ background:#2563EB; border-color:#2563EB; image:url(\"{check_icon}\"); }}\n"
        "    QCheckBox::indicator:hover, QCheckBox::indicator:focus { border-color:#60A5FA; }\n"
        f"    QCheckBox::indicator:disabled {{ background:{border}; border-color:{border}; }}\n"
    )
    result += modern_style(dark)
    _STYLESHEET_CACHE[dark] = result
    return result


def extra_style(dark: bool) -> str:
    return ""


def modern_style(dark: bool) -> str:
    chevron = (Path(__file__).resolve().parent / 'assets' / 'chevron.svg').as_posix()
    surface, text, muted, border, tinted = (
        ('#121D2E', '#E6EDF7', '#A7B5C9', '#27364B', '#152B45') if dark
        else ('#FFFFFF', '#0F172A', '#475569', '#D5DFEB', '#EFF6FF')
    )
    return f"""
    QComboBox::drop-down {{ subcontrol-origin:padding; subcontrol-position:top right; width:26px; border:0; background:transparent; }}
    QComboBox::down-arrow {{ image:url("{chevron}"); width:12px; height:12px; }}
    QLabel#title {{ font-size:26px; font-weight:700; }}
    QFrame#settingsPanel {{ background:{surface}; border:1px solid {border}; border-radius:10px; }}
    QLabel#routeSummary {{ background:{tinted}; color:{text}; border:1px solid {border}; border-radius:8px; padding:12px; font-size:14px; font-weight:600; }}
    QToolButton#presentationToggle {{ background:transparent; border:1px solid transparent; padding:6px; }}
    QToolButton#presentationToggle:hover, QToolButton#presentationToggle:focus {{ background:{surface}; border-color:#60A5FA; }}
    QPushButton[variant="quiet"] {{ background:transparent; color:{muted}; border-color:transparent; }}
    QPushButton[variant="quiet"]:hover, QPushButton[variant="quiet"]:focus {{ color:{text}; border-color:{border}; }}
    QGroupBox {{ border:0; border-top:1px solid {border}; border-radius:0; padding-top:16px; margin-top:18px; }}
    QGroupBox::title {{ background:{surface}; border:0; border-radius:0; padding:2px 6px; color:{muted}; }}
    QPlainTextEdit#discordPreview {{ border-color:{border}; font-size:14px; }}
    QLabel#emptyState {{ color:{muted}; background:{tinted}; border:1px solid {border}; border-radius:8px; padding:18px; }}
    """
