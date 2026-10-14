"""Small reusable UI building blocks: cards, stat tiles, badges, chips."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS

_BADGE_TONES = {
    "neutral": ("#f1f5f9", "#475569"),
    "emerald": ("#d1fae5", "#047857"),
    "red": ("#fee2e2", "#b91c1c"),
    "amber": ("#fef3c7", "#b45309"),
    "blue": ("#dbeafe", "#1d4ed8"),
    "slate": ("#e2e8f0", "#334155"),
}

_BADGE_QSS = (
    "background:{bg}; color:{fg}; border-radius:9px;"
    "padding:2px 9px; font-size:11px; font-weight:600;"
)


def _badge_style(tone: str) -> str:
    bg, fg = _BADGE_TONES.get(tone, _BADGE_TONES["neutral"])
    return _BADGE_QSS.format(bg=bg, fg=fg)


def badge(text: str, tone: str = "neutral") -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(_badge_style(tone))
    label.setAlignment(Qt.AlignCenter)
    return label


class ClickableBadge(QLabel):
    """A badge that emits ``clicked`` (used for the category cells)."""

    clicked = Signal()

    def __init__(self, text: str, tone: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(_badge_style(tone))
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class CategoryPickerDialog(QDialog):
    """Choose a category from a filterable list, or type a brand-new one.

    Typing filters the list below; selecting an item fills the input and
    (double-click/Enter) accepts it. If the typed text matches nothing, it is
    created as a new category on accept.
    """

    def __init__(self, categories: list[str], parent=None, title: str = "Assign category"):
        super().__init__(parent)
        self._categories = list(categories)
        self.setWindowTitle(title)
        self.setMinimumSize(380, 420)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        prompt = QLabel(
            "Type to filter, or pick from the list — choose an existing category, "
            "or type a new name to create it."
        )
        prompt.setObjectName("Muted")
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Filter categories or type a new one…")
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self.accept)
        layout.addWidget(self.input)

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.itemClicked.connect(self._pick)
        self.list.itemActivated.connect(lambda *_: self.accept())
        layout.addWidget(self.list, 1)

        self.hint = QLabel("")
        self.hint.setObjectName("Muted")
        layout.addWidget(self.hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Cancel).setObjectName("Ghost")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._filter("")
        self.input.setFocus()

    def _filter(self, text: str) -> None:
        text = (text or "").strip().lower()
        self.list.clear()
        for name in self._categories:
            if not text or text in name.lower():
                QListWidgetItem(name, self.list)

        typed = self.input.text().strip()
        exact = any(name.lower() == text for name in self._categories)
        if self.list.count() == 0 and typed:
            self.hint.setText(f'No match — “{typed}” will be created as a new category.')
        else:
            count = self.list.count()
            self.hint.setText(f"{count} categor{'y' if count == 1 else 'ies'} shown")
        return exact

    def _pick(self, item: QListWidgetItem) -> None:
        self.input.blockSignals(True)
        self.input.setText(item.text())
        self.input.blockSignals(False)
        self.input.selectAll()

    def selected(self) -> str | None:
        return self.input.text().strip() or None

    def get(self) -> str | None:
        return self.selected() if self.exec() == QDialog.Accepted else None


class Card(QFrame):
    """Rounded white card."""

    def __init__(self, parent: QWidget | None = None, padding: int = 18):
        super().__init__(parent)
        self.setObjectName("Card")
        self._body = QVBoxLayout(self)
        self._body.setContentsMargins(padding, padding, padding, padding)
        self._body.setSpacing(12)

    def body(self) -> QVBoxLayout:
        return self._body

    def add(self, widget: QWidget) -> QWidget:
        self._body.addWidget(widget)
        return widget


class StatCard(Card):
    def __init__(self, label: str, value: str = "—", tone: str = "default", parent=None):
        super().__init__(parent, padding=16)
        self.label = QLabel(label.upper())
        self.label.setObjectName("StatLabel")
        self.value = QLabel(value)
        self.value.setObjectName("StatValue")
        if tone == "emerald":
            self.value.setObjectName("AmountPos")
        elif tone == "red":
            self.value.setObjectName("AmountNeg")
        self._body.addWidget(self.label)
        self._body.addWidget(self.value)
        self._body.setSpacing(4)

    def set_value(self, value: str, tone: str = "default") -> None:
        self.value.setText(value)
        if tone == "emerald":
            self.value.setObjectName("AmountPos")
        elif tone == "red":
            self.value.setObjectName("AmountNeg")
        else:
            self.value.setObjectName("StatValue")
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        layout.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("PageSubtitle")
            layout.addWidget(s)


def hline() -> QFrame:
    line = QFrame()
    line.setObjectName("RowSep")
    line.setFrameShape(QFrame.HLine)
    return line


def row(*widgets: QWidget, spacing: int = 10) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    return container
