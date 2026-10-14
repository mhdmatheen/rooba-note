"""Month-range slider: a custom two-handle widget stepping over distinct months.

Snaps to whole-month boundaries. The default selection is the most recent three
months, but both handles can be dragged freely to any month so arbitrary ranges
are reachable.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .format import format_month
from .theme import COLORS

_MARGIN = 22
_TRACK_H = 6
_HANDLE_R = 8


def _last_day(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


class _Track(QWidget):
    handle_moved = Signal(int, int)   # live during drag -> label update only
    committed = Signal(int, int)      # on release / keyboard step -> reload

    def __init__(self, months: list[str], parent=None):
        super().__init__(parent)
        self._months = months
        self._n = max(1, len(months))
        self._low = 0
        self._high = self._n - 1
        self._drag = None  # "low" | "high" | None
        self._free_x = None  # free cursor x of the handle being dragged
        self.setMinimumHeight(44)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ #
    def set_range(self, low: int, high: int) -> None:
        low = max(0, min(self._n - 1, low))
        high = max(low, min(self._n - 1, high))
        self._free_x = None
        if (low, high) != (self._low, self._high):
            self._low, self._high = low, high
            self.update()

    def update_months(self, months: list[str]) -> None:
        self._months = months
        self._n = max(1, len(months))
        self._low = 0
        self._high = self._n - 1
        self._free_x = None
        self.update()

    @property
    def low(self) -> int:
        return self._low

    @property
    def high(self) -> int:
        return self._high

    def reset_to_last(self, count: int = 3) -> None:
        self._high = self._n - 1
        self._low = max(0, self._high - (count - 1))
        self._free_x = None
        self.update()

    # ------------------------------------------------------------------ #
    def _x(self, index: int) -> float:
        span = max(1, self._n - 1)
        return _MARGIN + index / span * (self.width() - 2 * _MARGIN)

    def _index_for_x(self, x: float) -> int:
        if self._n <= 1:
            return 0
        ratio = (x - _MARGIN) / (self.width() - 2 * _MARGIN)
        idx = round(ratio * (self._n - 1))
        return max(0, min(self._n - 1, idx))

    def _nearest_handle(self, x: float) -> str:
        low_x = self._x(self._low)
        high_x = self._x(self._high)
        return "high" if abs(x - high_x) <= abs(x - low_x) else "low"

    # ------------------------------------------------------------------ #
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cy = self.height() / 2.0

        track = QRectF(_MARGIN, cy - _TRACK_H / 2, self.width() - 2 * _MARGIN, _TRACK_H)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(COLORS["border"]))
        p.drawRoundedRect(track, _TRACK_H / 2, _TRACK_H / 2)

        # fill always reflects the snapped month positions
        low_snap = self._x(self._low)
        high_snap = self._x(self._high)
        selected = QRectF(low_snap, cy - _TRACK_H / 2, max(1.0, high_snap - low_snap), _TRACK_H)
        p.setBrush(QColor(COLORS["emerald"]))
        p.drawRoundedRect(selected, _TRACK_H / 2, _TRACK_H / 2)

        # the handle being dragged follows the cursor freely; the other is snapped
        low_x = self._free_x if (self._drag == "low" and self._free_x is not None) else low_snap
        high_x = self._free_x if (self._drag == "high" and self._free_x is not None) else high_snap

        for x in (low_x, high_x):
            p.setBrush(QColor("#ffffff"))
            p.setPen(QColor(COLORS["emerald"]))
            p.drawEllipse(QRectF(x - _HANDLE_R, cy - _HANDLE_R, _HANDLE_R * 2, _HANDLE_R * 2))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._n > 1 and event.button() == Qt.LeftButton:
            self._drag = self._nearest_handle(event.position().x())
            self._update_from_x(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag and self._n > 1:
            self._update_from_x(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag is not None:
            self._drag = None
            self._free_x = None  # snap back to the month position
            self.update()
            self.committed.emit(self._low, self._high)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._drag is None:
            self._drag = "high"
        delta = 0
        if event.key() in (Qt.Key_Right, Qt.Key_Up):
            delta = 1
        elif event.key() in (Qt.Key_Left, Qt.Key_Down):
            delta = -1
        if delta and self._n > 1:
            self._free_x = None
            self._set_handle(self._drag, self._handle(self._drag) + delta)
            self.committed.emit(self._low, self._high)
            self._drag = None
        super().keyPressEvent(event)

    def _handle(self, which: str) -> int:
        return self._low if which == "low" else self._high

    def _set_handle(self, which: str, value: int) -> None:
        value = max(0, min(self._n - 1, value))
        if which == "low":
            self._low = min(value, self._high)
        else:
            self._high = max(value, self._low)
        self.update()
        self.handle_moved.emit(self._low, self._high)

    def _update_from_x(self, x: float) -> None:
        idx = self._index_for_x(x)
        if self._drag == "low":
            self._low = min(idx, self._high)
            self._free_x = min(max(x, _MARGIN), self._x(self._high))
        else:
            self._high = max(idx, self._low)
            self._free_x = max(min(x, self.width() - _MARGIN), self._x(self._low))
        self.update()
        self.handle_moved.emit(self._low, self._high)


class MonthRangeSlider(QWidget):
    """Vertical stack: range label (top-center), track, and start/end bounds."""

    range_changed = Signal(int, int)  # low_index, high_index into months

    def __init__(self, months: list[str] | None = None, parent=None):
        super().__init__(parent)
        self._months = list(months or [])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.range_label = QLabel("—")
        self.range_label.setAlignment(Qt.AlignCenter)
        self.range_label.setObjectName("SectionTitle")
        layout.addWidget(self.range_label)

        self._track = _Track(self._months)
        self._track.handle_moved.connect(self._on_handle_moved)
        self._track.committed.connect(self._emit_range)
        layout.addWidget(self._track)

        bounds = QWidget()
        bounds_layout = QHBoxLayout(bounds)
        bounds_layout.setContentsMargins(0, 0, 0, 0)
        self.start_label = QLabel("—")
        self.start_label.setObjectName("Muted")
        self.end_label = QLabel("—")
        self.end_label.setObjectName("Muted")
        self.end_label.setAlignment(Qt.AlignRight)
        bounds_layout.addWidget(self.start_label)
        bounds_layout.addStretch(1)
        bounds_layout.addWidget(self.end_label)
        layout.addWidget(bounds)

        self._apply_labels()

    # ------------------------------------------------------------------ #
    def set_months(self, months: list[str]) -> None:
        self._months = list(months or [])
        self._apply_labels()
        self._track.update_months(self._months)
        self.reset_to_last(3)

    def reset_to_last(self, count: int = 3) -> None:
        if not self._months:
            return
        self._track.reset_to_last(count)
        self._on_handle_moved(self._track.low, self._track.high)
        self.range_changed.emit(self._track.low, self._track.high)

    def low_month(self) -> str | None:
        return self._months[self._track.low] if self._months else None

    def high_month(self) -> str | None:
        return self._months[self._track.high] if self._months else None

    def range_dates(self) -> tuple[date, date] | None:
        """Return (from_date, to_date) for the selected month range."""
        if not self._months:
            return None
        low, high = self.low_month(), self.high_month()
        if not low or not high:
            return None
        fy, fm = int(low[:4]), int(low[5:7])
        ty, tm = int(high[:4]), int(high[5:7])
        from_date = date(fy, fm, 1)
        to_date = date(ty, tm, _last_day(ty, tm))
        return from_date, to_date

    def _on_handle_moved(self, low: int, high: int) -> None:
        self._update_range_label()

    def _emit_range(self, low: int, high: int) -> None:
        self.range_changed.emit(low, high)

    def _update_range_label(self) -> None:
        low = self.low_month()
        high = self.high_month()
        if low and high:
            if low == high:
                self.range_label.setText(format_month(low))
            else:
                self.range_label.setText(
                    f"{format_month(low)}  –  {format_month(high)}"
                )
        else:
            self.range_label.setText("Not enough data")

    def _apply_labels(self) -> None:
        if self._months:
            self.start_label.setText(format_month(self._months[0]))
            self.end_label.setText(format_month(self._months[-1]))
            self.start_label.setEnabled(True)
            self.end_label.setEnabled(True)
            self._update_range_label()
        else:
            self.start_label.setText("—")
            self.end_label.setText("—")
            self.range_label.setText("Not enough data")