"""Finder-like search bar: choose where to search and add extra criteria rows."""

from pathlib import Path

from PySide6.QtCore import QDate, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..system.search import SearchCriterion
from .icons import IconButton
from .widgets import RoundedComboBox

FIELDS = (
    ("Type", "kind", (("er", "is"), ("er ikke", "is_not"))),
    ("Filtype", "extension", (("er", "is"), ("er ikke", "is_not"))),
    ("Størrelse", "size", (("større enn", "gt"), ("mindre enn", "lt"))),
    ("Endret", "modified", (("siste", "within"), ("før", "before"), ("etter", "after"))),
    (
        "Navn",
        "name",
        (("inneholder", "contains"), ("inneholder ikke", "not_contains"), ("begynner med", "starts")),
    ),
)


def _combo(items, colors):
    widget = RoundedComboBox()
    # Bredden følger teksten, så ingen valg kuttes.
    widget.setSizeAdjustPolicy(RoundedComboBox.SizeAdjustPolicy.AdjustToContents)
    for label, value in items:
        widget.addItem(label, value)
    if colors:
        widget.set_popup_colors(colors)
    return widget


class CriterionRow(QFrame):
    changed = Signal()
    removed = Signal(object)

    def __init__(self, colors=None):
        super().__init__()
        self.setObjectName("searchCriterion")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.field = _combo([(label, key) for label, key, _ in FIELDS], colors)
        self.field.setAccessibleName("Søkekriterium")
        self.operator = _combo([], colors)
        self.operator.setAccessibleName("Sammenligning")
        self.values = QStackedWidget()
        self.kind = _combo([("Video", "video"), ("Lyd", "audio")], colors)
        self.text = QLineEdit()
        self.text.setMaxLength(200)
        self.size = QDoubleSpinBox()
        self.size.setRange(0.1, 1_000_000)
        self.size.setDecimals(1)
        self.size.setValue(100)
        self.size_unit = _combo([("KB", "KB"), ("MB", "MB"), ("GB", "GB")], colors)
        self.size_unit.setCurrentIndex(1)
        self.age = QSpinBox()
        self.age.setRange(1, 10_000)
        self.age.setValue(7)
        self.age_unit = _combo(
            [("dager", "days"), ("uker", "weeks"), ("måneder", "months"), ("år", "years")], colors
        )
        # Pilene skjules i stilarket; NoButtons sammen med stilark gir et tekstfelt på 1 px i Qt.
        for number in (self.size, self.age):
            number.setFixedWidth(64)
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd.MM.yyyy")
        for widgets in (
            (self.kind,),
            (self.text,),
            (self.size, self.size_unit),
            (self.age, self.age_unit),
            (self.date,),
        ):
            page = QWidget()
            page_layout = QHBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(6)
            for widget in widgets:
                page_layout.addWidget(widget, 1 if widget in (self.text, self.date, self.kind) else 0)
            page_layout.addStretch()
            self.values.addWidget(page)
        self.remove = IconButton("close", "Fjern kriteriet")
        self.remove.setObjectName("browserViewButton")
        self.remove.setIconSize(QSize(14, 14))
        layout.addWidget(self.field)
        layout.addWidget(self.operator)
        layout.addWidget(self.values, 1)
        layout.addWidget(self.remove)
        self.field.currentIndexChanged.connect(self._field_changed)
        self.operator.currentIndexChanged.connect(self._operator_changed)
        for signal in (
            self.kind.currentIndexChanged,
            self.size_unit.currentIndexChanged,
            self.age_unit.currentIndexChanged,
            self.size.valueChanged,
            self.age.valueChanged,
            self.date.dateChanged,
            self.text.textChanged,
        ):
            signal.connect(self.changed)
        self.remove.clicked.connect(lambda: self.removed.emit(self))
        self._field_changed()

    def _field_changed(self):
        key = self.field.currentData()
        operators = next(ops for _, k, ops in FIELDS if k == key)
        self.operator.blockSignals(True)
        self.operator.clear()
        for label, value in operators:
            self.operator.addItem(label, value)
        self.operator.blockSignals(False)
        self.text.setPlaceholderText("jpg" if key == "extension" else "Tekst i filnavnet")
        self._operator_changed()

    def _operator_changed(self):
        key, operator = self.field.currentData(), self.operator.currentData()
        page = {"kind": 0, "extension": 1, "name": 1, "size": 2}.get(key)
        if key == "modified":
            page = 3 if operator == "within" else 4
        self.values.setCurrentIndex(page)
        self.changed.emit()

    def criterion(self) -> SearchCriterion | None:
        """None while the row is incomplete, so a half-typed row does not break the search."""
        key, operator = self.field.currentData(), self.operator.currentData()
        if key == "kind":
            return SearchCriterion(key, operator, self.kind.currentData())
        if key in {"extension", "name"}:
            value = self.text.text().strip()
            return SearchCriterion(key, operator, value) if value else None
        if key == "size":
            return SearchCriterion(key, operator, f"{self.size.value():g}", self.size_unit.currentData())
        if operator == "within":
            return SearchCriterion(key, operator, str(self.age.value()), self.age_unit.currentData())
        return SearchCriterion(key, operator, self.date.date().toString("yyyy-MM-dd"))


class SearchOptions(QFrame):
    """Shown only while a search is active, like the search bar in macOS Finder."""

    changed = Signal()

    def __init__(self, colors=None):
        super().__init__()
        self.setObjectName("searchOptions")
        self.colors = colors
        self.folder = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        scope = QHBoxLayout()
        scope.setSpacing(6)
        label = QLabel("Søk i:")
        label.setObjectName("muted")
        scope.addWidget(label)
        self.scope_group = QButtonGroup(self)
        self.this_pc = QPushButton("Denne PC-en")
        self.this_folder = QPushButton()
        for index, button in enumerate((self.this_folder, self.this_pc)):
            button.setObjectName("scopeButton")
            button.setCheckable(True)
            button.setAutoDefault(False)
            self.scope_group.addButton(button, index)
            scope.addWidget(button)
        self.this_folder.setChecked(True)
        scope.addStretch()
        self.add = IconButton("plus", "Legg til søkekriterium")
        self.add.setObjectName("browserViewButton")
        self.add.setIconSize(QSize(16, 16))
        scope.addWidget(self.add)
        layout.addLayout(scope)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(6)
        layout.addLayout(self.rows_layout)
        self.rows = []
        self.scope_group.idClicked.connect(lambda _: self.changed.emit())
        self.add.clicked.connect(self.add_row)

    def set_folder(self, path: str):
        self.folder = Path(path)
        name = self.folder.name or str(self.folder).rstrip("\\/")
        self.this_folder.setText(f"«{name}»")
        self.this_folder.setToolTip(f"Søk i {self.folder} med undermapper")
        self.this_pc.setToolTip("Søk i alle filene Windows har indeksert på maskinen")

    def scope(self) -> Path | None:
        return self.folder if self.this_folder.isChecked() else None

    def add_row(self):
        row = CriterionRow(self.colors)
        row.changed.connect(self.changed)
        row.removed.connect(self.remove_row)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        row.field.setFocus()
        self.changed.emit()
        return row

    def remove_row(self, row):
        self.rows.remove(row)
        row.hide()
        row.deleteLater()
        self.changed.emit()

    def criteria(self) -> tuple[SearchCriterion, ...]:
        return tuple(c for c in (row.criterion() for row in self.rows) if c)

    def reset(self):
        """A new search starts in the current folder without extra criteria."""
        for row in list(self.rows):
            self.rows.remove(row)
            row.deleteLater()
        self.this_folder.setChecked(True)
