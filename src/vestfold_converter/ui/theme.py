"""Farger, stilark og typografi for lyst og mørkt tema."""

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / name


@lru_cache(maxsize=1)
def _load_font() -> str:
    font_id = QFontDatabase.addApplicationFont(str(asset_path("fonts/Nunito-wght.ttf")))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    if "Nunito" not in families:
        raise RuntimeError("Kunne ikke laste Nunito fra programmets fonts-mappe.")
    return "Nunito"


def configure_typography() -> None:
    """Registrer fonten bare i denne appen. Ingen installasjon eller nettverk."""
    font = QFont(_load_font(), 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    QApplication.instance().setFont(font)


LIGHT = {
    "background": "#f3f0ec",
    "surface": "#fffdfa",
    "raised": "#f3f0ec",
    "text": "#20231f",
    "muted": "#62655d",
    "border": "#d3cbc0",
    "accent": "#b70013",
    "primary": "#e40017",
    "primary_hover": "#bc0014",
    "primary_text": "#ffffff",
    "hover": "#eee7df",
    "selected": "#f8e8ec",
    "nav": "#005260",
    "nav_hover": "#08788a",
    "motif_red": "#b7173d",
    "motif_sand": "#dcd3c5",
    "motif_soft": "#f1d1d8",
    "yellow": "#ffcd00",
    "yellow_text": "#302800",
    "status_text": "#005260",
    "status_bg": "#e5eeef",
    "success": "#2c6039",
    "success_bg": "#e2eadb",
    "error": "#b70013",
    "error_bg": "#f6dedf",
    "video": "#005260",
    "video_bg": "#e5eeef",
    "audio": "#b7173d",
    "audio_bg": "#f8e8ec",
}
DARK = {
    "background": "#242422",
    "surface": "#2d2e2b",
    "raised": "#33352f",
    "text": "#f5f2ed",
    "muted": "#c0bdb4",
    "border": "#515149",
    "accent": "#ffcd00",
    "primary": "#e40017",
    "primary_hover": "#bc0014",
    "primary_text": "#ffffff",
    "hover": "#383a33",
    "selected": "#48343a",
    "nav": "#196370",
    "nav_hover": "#08788a",
    "motif_red": "#e2a2b1",
    "motif_sand": "#8a6c3e",
    "motif_soft": "#48343a",
    "yellow": "#ffcd00",
    "yellow_text": "#302800",
    "status_text": "#ccdcdf",
    "status_bg": "#283c3f",
    "success": "#b3d89d",
    "success_bg": "#34432d",
    "error": "#ffb6bb",
    "error_bg": "#4d2d32",
    "video": "#b2cbcf",
    "video_bg": "#283c3f",
    "audio": "#e2a2b1",
    "audio_bg": "#48343a",
}


def is_dark(colors: dict) -> bool:
    return colors["background"] == DARK["background"]


def popup_stylesheet(c: dict) -> str:
    return f"""
        QFrame#comboPopup {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 8px; padding: 4px; }}
        QListView#comboOptions {{ background: {c["surface"]}; color: {c["text"]}; border: 0;
            font-family: 'Nunito'; font-size: 10pt; outline: 0; padding: 4px;
            selection-background-color: {c["selected"]}; selection-color: {c["text"]}; }}
        QListView#comboOptions::item {{ padding: 9px 12px; min-height: 18px;
            margin: 2px; border: 0; border-radius: 6px; }}
        QListView#comboOptions::item:hover, QListView#comboOptions::item:selected {{
            background: {c["selected"]}; color: {c["text"]}; }}
    """


def stylesheet(c: dict) -> str:
    arrow = asset_path("chevron-dark.svg" if is_dark(c) else "chevron-light.svg")
    return f"""
        QWidget {{ font-family: 'Nunito'; font-size: 10pt; color: {c["text"]}; }}
        QMainWindow, QWidget#mainSurface {{ background: {c["background"]}; }}
        QDialog#importBrowser, QDialog#fileDetails {{ background: {c["background"]}; }}
        QScrollArea#detailsScroll, QScrollArea#detailsScroll > QWidget, QWidget#detailsContent {{ background: transparent; border: 0; }}
        QFrame#detailCard {{ background: {c["surface"]}; border: 1px solid {c["border"]}; border-radius: 8px; }}
        QLabel#detailKey {{ color: {c["muted"]}; min-width: 130px; }}
        QLabel#detailError {{ color: {c["accent"]}; font-weight: 600; }}
        QDialog#importBrowser QTreeView, QDialog#importBrowser QListView {{
            background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
            border-radius: 8px; selection-background-color: {c["selected"]};
            selection-color: {c["text"]}; outline: 0; }}
        QListWidget#browserPlaces::item {{ padding: 5px 6px; }}
        QTreeView#browserFiles::item {{ min-height: 26px; padding: 2px 4px; }}
        QListView#browserGrid {{ show-decoration-selected: 1; }}
        QListView#browserGrid::item {{ border: 2px solid transparent; border-radius: 8px; padding: 4px; }}
        QListView#browserGrid::item:selected {{ background: transparent; color: {c["text"]};
            border: 2px solid {c["accent"]}; }}
        QDialog#importBrowser QPushButton:checked {{
            background: {c["yellow"]}; color: {c["yellow_text"]}; border-color: {c["yellow"]}; }}
        QSplitter#importSplitter::handle, QSplitter#importSplitter::handle:hover {{
            background: transparent; border: 0; margin: 0; }}
        QFrame#browserPane {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 8px; }}
        QFrame#browserPane QTreeView, QFrame#browserPane QListView {{ border: 0; }}
        QFrame#browserPane QHeaderView::section {{ padding: 5px 10px; border-radius: 0; }}
        /* Søkelinjen er kompakt: mindre skrift og lavere felt enn resten av appen. */
        QFrame#searchOptions QComboBox, QFrame#searchOptions QLineEdit, QFrame#searchOptions QAbstractSpinBox,
        QFrame#searchOptions QPushButton, QFrame#searchOptions QLabel {{ font-size: 9pt; }}
        QFrame#searchOptions QComboBox {{ padding: 3px 24px 3px 8px; min-height: 16px; border-width: 1px;
            border-radius: 7px; }}
        QFrame#searchOptions QComboBox::drop-down {{ width: 18px; margin-right: 4px; }}
        QFrame#searchOptions QComboBox::down-arrow {{ width: 12px; height: 12px; }}
        QFrame#searchOptions QLineEdit, QFrame#searchOptions QAbstractSpinBox {{ background: {c["surface"]};
            border: 1px solid {c["border"]}; border-radius: 7px; padding: 3px 6px; min-height: 16px; }}
        /* Tekstfeltet inne i tallboksen skal ikke ha egen kant eller luft, ellers forsvinner tallet. */
        QFrame#searchOptions QAbstractSpinBox QLineEdit {{ border: 0; padding: 0 6px; margin: 0; min-height: 0;
            background: transparent; }}
        QFrame#searchOptions QAbstractSpinBox::up-button, QFrame#searchOptions QAbstractSpinBox::down-button {{
            width: 0; border: 0; image: none; }}
        QFrame#searchOptions QLineEdit:focus, QFrame#searchOptions QAbstractSpinBox:focus {{
            border: 1px solid {c["accent"]}; }}
        QPushButton#scopeButton {{ padding: 3px 10px; min-height: 16px; border-radius: 12px; }}
        QLineEdit#browserSearch {{ padding: 4px 6px; min-height: 18px; max-height: 18px; margin: 1px; }}
        QLineEdit#browserSearch:focus {{ border: 1px solid {c["accent"]}; }}
        QPushButton#browserViewButton {{ padding: 0; min-height: 26px; max-height: 26px;
            min-width: 26px; max-width: 26px; margin: 1px;
            qproperty-checkedIconColor: "{c["yellow_text"]}"; }}
        QDialog#importBrowser QPushButton#browserViewButton:focus {{
            border: 1px solid {c["accent"]}; }}
        QPushButton#browserNavButton {{ padding: 0; min-height: 30px; max-height: 30px;
            min-width: 30px; max-width: 30px; }}
        QPushButton#browserNavButton:focus {{ border: 1px solid {c["accent"]}; }}
        QFrame#browserPath {{ background: transparent; border: 0; }}
        QFrame#addressPath {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 8px; }}
        QFrame#addressPath QLineEdit#pathEditor {{ background: transparent; border: 0;
            padding: 0; min-height: 0; }}
        QFrame#browserPath QToolButton#pathPart, QFrame#addressPath QToolButton#pathPart {{ background: transparent;
            border: 0; padding: 2px 4px; min-height: 0; font-size: 9pt; }}
        QFrame#addressPath QToolButton#pathPart {{ font-size: 10pt; }}
        QFrame#browserPath QToolButton#pathPart:hover, QFrame#browserPath QToolButton#pathPart:focus,
        QFrame#addressPath QToolButton#pathPart:hover, QFrame#addressPath QToolButton#pathPart:focus {{
            background: {c["hover"]}; color: {c["accent"]}; }}
        QMenu#pathMenu {{ background: {c["surface"]}; color: {c["text"]};
            border: 1px solid {c["border"]}; padding: 6px; }}
        QMenu#pathMenu::item {{ padding: 6px 12px; border-radius: 4px; }}
        QMenu#pathMenu::item:selected {{ background: {c["selected"]}; }}
        QMenu#pathMenu::separator {{ height: 1px; background: {c["border"]}; margin: 4px; }}
        QLabel {{ background: transparent; }}
        QLabel#title {{ font-size: 21pt; font-weight: 850; }}
        QLabel#subtitle {{ color: {c["muted"]}; font-size: 10pt; }}
        QLabel#sectionTitle {{ font-size: 14pt; font-weight: 800; }}
        QLabel#muted, QLabel#selectionDetail, QLabel#eyebrow {{ color: {c["muted"]}; }}
        QLabel#eyebrow {{ font-size: 9pt; font-weight: 600; }}
        QLabel#selectionName {{ font-weight: 600; font-size: 11pt; }}
        QLabel#countBadge {{ background: {c["yellow"]}; color: {c["yellow_text"]};
            border-radius: 6px; padding: 4px 10px; font-weight: 800; }}
        QLabel#notice {{ background: {c["raised"]}; padding: 10px; border-radius: 8px; }}
        QFrame#themeSwitcher {{ background: {c["raised"]}; border: 1px solid {c["border"]}; border-radius: 11px; }}
        QToolButton#themeOption {{ background: transparent; border: 1px solid transparent;
            border-radius: 7px; padding: 0; min-height: 30px; min-width: 34px; }}
        QToolButton#themeOption:hover {{ background: {c["hover"]}; }}
        QToolButton#themeOption:checked {{ background: {c["yellow"]}; border-color: {c["yellow"]}; }}
        /* Bare valgt modus markeres, med gult. Ingen fokusramme. */
        QToolButton#themeOption:focus {{ border: 1px solid transparent; }}
        QPushButton, QToolButton {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 8px; padding: 9px 13px; min-height: 18px; }}
        QPushButton:hover, QToolButton:hover {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{
            border: 2px solid {c["accent"]}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: {c["muted"]}; background: {c["raised"]}; }}
        QPushButton#previewControl {{ padding: 0; min-height: 30px; max-height: 30px;
            min-width: 30px; max-width: 30px; }}
        QPushButton#previewControl:focus {{ border: 1px solid {c["accent"]}; }}
        QPushButton#filledButton {{ background: {c["nav"]}; color: #ffffff;
            border-color: {c["nav"]}; }}
        QPushButton#filledButton:hover, QPushButton#filledButton:focus {{
            background: {c["nav_hover"]}; border: 1px solid {c["nav_hover"]}; }}
        QPushButton#primary {{ background: {c["primary"]}; color: {c["primary_text"]};
            border: 2px solid {c["primary"]}; border-radius: 6px; font-weight: 850;
            font-size: 12pt; padding: 11px 24px; }}
        QPushButton#primary:hover {{ background: {c["primary_hover"]}; border-color: {c["primary_hover"]}; }}
        QPushButton#primary:focus {{ border: 2px solid {c["yellow"]}; }}
        QPushButton#primary:disabled {{ background: {c["border"]}; border-color: {c["border"]}; color: {c["muted"]}; }}
        QPushButton#softButton {{ background: {c["surface"]}; border-color: {c["border"]};
            color: {c["text"]}; font-weight: 800; }}
        QPushButton#softButton:hover {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QPushButton#quietButton, QToolButton#advancedToggle {{ background: transparent; border: 1px solid transparent; }}
        QPushButton#quietButton:hover, QToolButton#advancedToggle:hover,
        QPushButton#quietButton:checked {{ background: {c["hover"]}; color: {c["accent"]}; }}
        QToolButton#advancedToggle {{ text-align: left; padding-left: 0; }}
        QPushButton#dropArea {{ background: {c["surface"]}; border: 2px dashed {c["border"]};
            border-radius: 10px; min-height: 160px; }}
        QPushButton#dropArea:hover, QPushButton#dropArea:focus {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QLabel#dropTitle {{ font-size: 21pt; font-weight: 850; }}
        QPushButton#dropAction {{ background: {c["primary"]}; color: {c["primary_text"]};
            border: 1px solid {c["primary"]}; border-radius: 6px; padding: 9px 25px; font-weight: 800; }}
        QPushButton#dropAction:hover {{ background: {c["primary_hover"]}; border-color: {c["primary_hover"]}; }}
        QPushButton#dropAction:focus {{ border: 1px solid {c["yellow"]}; }}
        QFrame#queueCard, QFrame#destination, QScrollArea#settingsCard {{ background: {c["surface"]};
            border: 1px solid {c["border"]}; border-radius: 8px; }}
        QTableWidget {{ background: {c["surface"]}; border: 0; selection-background-color: {c["selected"]};
            selection-color: {c["text"]}; outline: 0; }}
        QTableWidget::item {{ border: 0; border-bottom: 1px solid {c["border"]}; }}
        QTableWidget::item:focus {{ border: 1px solid {c["accent"]}; }}
        QHeaderView::section {{ background: {c["raised"]}; color: {c["muted"]}; padding: 11px 14px;
            border: 0; border-bottom: 1px solid {c["border"]}; text-align: left; font-size: 9pt; font-weight: 600; }}
        QHeaderView {{ background: transparent; }}
        QHeaderView::section:first {{ border-top-left-radius: 7px; }}
        QHeaderView::section:last {{ border-top-right-radius: 7px; }}
        QHeaderView::section:hover {{ color: {c["text"]}; }}
        QScrollArea#settingsCard > QWidget > QWidget, QWidget#settingsPanel {{ background: {c["surface"]}; }}
        /* Fanepanelet tegner flaten; firkantet innhold ville dekket de runde hjørnene. */
        QWidget#previewPanel {{ background: {c["surface"]}; }}
        QScrollArea#inspectorScroll, QScrollArea#inspectorScroll > QWidget,
        QScrollArea#inspectorScroll > QWidget > QWidget,
        QScrollArea#inspectorScroll QWidget#settingsPanel, QScrollArea#inspectorScroll QWidget#previewPanel {{
            background: transparent; border: 0; }}
        QTabWidget#inspector::pane {{ background: {c["surface"]}; border: 1px solid {c["border"]}; border-radius: 10px; }}
        QTabBar::tab {{ background: transparent; color: {c["muted"]}; padding: 10px 12px;
            border: 0; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ color: {c["accent"]}; border-bottom-color: {c["accent"]}; font-weight: 600; }}
        QTabBar::tab:focus {{ border: 1px solid {c["accent"]}; }}
        QLabel#previewTime {{ color: {c["muted"]}; font-size: 9pt; }}
        QSlider::groove:horizontal {{ height: 4px; background: {c["border"]}; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: {c["accent"]}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; background: {c["accent"]};
            border-radius: 6px; border: 1px solid {c["surface"]}; }}
        QComboBox, QLineEdit, QSpinBox {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 7px; padding: 8px; min-height: 20px; selection-background-color: {c["selected"]}; }}
        QComboBox {{ border: 2px solid {c["border"]}; border-radius: 9px;
            padding: 8px 38px 8px 12px; min-height: 20px; }}
        QComboBox:hover {{ border-color: {c["muted"]}; }}
        QComboBox:focus, QComboBox:on {{ border-color: {c["accent"]}; }}
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right;
            width: 28px; border: 0; background: transparent; margin-right: 6px; }}
        QComboBox::down-arrow {{ image: url("{arrow.as_posix()}"); width: 16px; height: 16px; }}
        QProgressBar {{ border: 0; border-radius: 3px; background: {c["border"]}; max-height: 6px; min-height: 6px; }}
        QProgressBar::chunk {{ background: {c["primary"]}; border-radius: 3px; }}
        QProgressBar[done="true"]::chunk {{ background: {c["success"]}; }}
        QFrame#divider {{ background: {c["border"]}; border: 0; max-height: 1px; }}
        QSplitter::handle {{ background: transparent; width: 18px; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c["border"]}; border-radius: 4px; min-height: 32px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: {c["border"]}; border-radius: 4px; min-width: 32px; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
        QAbstractScrollArea::corner {{ background: transparent; }}
        QToolTip {{ background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: 5px; }}
        QMainWindow[compact="true"] QLabel#title {{ font-size: 18pt; }}
        QMainWindow[compact="true"] QLabel#subtitle {{ font-size: 9pt; }}
        QMainWindow[compact="true"] QLabel#sectionTitle {{ font-size: 12pt; }}
        QMainWindow[compact="true"] QLabel#dropTitle {{ font-size: 16pt; }}
        QMainWindow[compact="true"] QPushButton, QMainWindow[compact="true"] QToolButton {{
            padding: 7px 10px; min-height: 16px; }}
        QMainWindow[compact="true"] QPushButton#primary {{ font-size: 11pt; padding: 7px 18px; min-height: 18px; }}
        QMainWindow[compact="true"] QPushButton#dropArea {{ min-height: 120px; }}
        /* Qt sizes the clear button to the icon; button padding would push it off-centre. */
        QLineEdit QToolButton, QLineEdit QToolButton:hover, QLineEdit QToolButton:focus,
        QMainWindow[compact="true"] QLineEdit QToolButton {{
            background: transparent; border: 0; padding: 0; margin: 0; min-height: 0; min-width: 0; }}
    """
