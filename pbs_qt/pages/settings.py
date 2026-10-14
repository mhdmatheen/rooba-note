"""Settings page: manage the category list the user can assign transactions to."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import core
from ..theme import COLORS
from ..widgets import Card, PageHeader, hline


class SettingsPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        outer.addWidget(
            PageHeader(
                "Settings",
                "Manage the categories you can assign transactions to.",
            )
        )

        add_card = Card()
        add_label = QLabel("Add a new category")
        add_label.setObjectName("SectionTitle")
        add_card.body().addWidget(add_label)
        add_host = QWidget()
        add_row = QHBoxLayout(add_host)
        add_row.setContentsMargins(0, 0, 0, 0)
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("e.g. Groceries, Medical, Investments…")
        self.add_input.returnPressed.connect(self._add)
        add_btn = QPushButton("Add")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add)
        add_row.addWidget(self.add_input, 1)
        add_row.addWidget(add_btn)
        add_card.body().addWidget(add_host)
        outer.addWidget(add_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(8)
        scroll.setWidget(self.list_host)
        outer.addWidget(scroll, 1)

    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for name in core.managed_categories():
            self.list_layout.addWidget(self._row(name))
        self.list_layout.addStretch(1)

    # ------------------------------------------------------------------ #
    def _row(self, name: str) -> Card:
        card = Card(padding=12)
        inner = QHBoxLayout()
        inner.setContentsMargins(0, 0, 0, 0)

        label = QLabel(name)
        label.setStyleSheet("font-weight:600;")
        inner.addWidget(label, 1)

        rename = QPushButton("Rename")
        rename.setObjectName("Ghost")
        rename.clicked.connect(lambda _=False, n=name: self._rename(n))
        delete = QPushButton("Delete")
        delete.setObjectName("Ghost")
        delete.clicked.connect(lambda _=False, n=name: self._delete(n))
        inner.addWidget(rename)
        inner.addWidget(delete)

        card.body().addLayout(inner)
        return card

    def _add(self) -> None:
        name = self.add_input.text().strip()
        if not name:
            return
        if name not in core.managed_categories():
            core.add_category(name)
        self.add_input.clear()
        self.data_changed.emit()
        self.refresh()

    def _rename(self, old: str) -> None:
        new, ok = QInputDialog.getText(self, "Rename category", "New name:", text=old)
        new = new.strip()
        if not ok or not new or new == old:
            return
        if core.rename_category(old, new):
            self.data_changed.emit()
            self.refresh()
        else:
            QMessageBox.warning(self, "Rename", f"Could not rename to '{new}' (maybe it already exists).")

    def _delete(self, name: str) -> None:
        answer = QMessageBox.question(
            self,
            "Delete category",
            f"Delete '{name}'? Existing transactions in this category will be marked Uncategorized.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            core.delete_category(name)
            self.data_changed.emit()
            self.refresh()