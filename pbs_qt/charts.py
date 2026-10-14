"""Custom QPainter charts — flat, rounded, modern (no QtCharts dependency)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .format import format_inr_compact
from .theme import COLORS


def _top_rounded_path(x: float, y: float, w: float, h: float, radius: float) -> QPainterPath:
    radius = max(0.0, min(radius, w / 2, h))
    path = QPainterPath()
    path.moveTo(x, y + h)
    path.lineTo(x, y + radius)
    path.quadTo(x, y, x + radius, y)
    path.lineTo(x + w - radius, y)
    path.quadTo(x + w, y, x + w, y + radius)
    path.lineTo(x + w, y + h)
    path.closeSubpath()
    return path


class CashflowChart(QWidget):
    """Grouped monthly bars: income (emerald) vs spending (red)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self.setMinimumHeight(250)

    def set_data(self, data: list[dict]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(COLORS["card"]))

        data = self._data
        if not data:
            painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data yet")
            return

        pad_l, pad_r, pad_t, pad_b = 14, 14, 28, 38
        plot_w = max(1, self.width() - pad_l - pad_r)
        plot_h = max(1, self.height() - pad_t - pad_b)
        base_y = pad_t + plot_h

        max_value = max(
            [max(d.get("income", 0), d.get("spending", 0)) for d in data] + [1]
        )

        # Grid lines
        painter.setPen(QPen(QColor("#eef0f3"), 1))
        for i in range(5):
            y = pad_t + plot_h * i / 4
            painter.drawLine(QPointF(pad_l, y), QPointF(pad_l + plot_w, y))

        slot = plot_w / len(data)
        bar_w = max(6.0, min(16.0, slot * 0.30))
        gap = 4.0

        # Highlight forecast region
        forecast_indices = [i for i, d in enumerate(data) if d.get("forecast")]
        if forecast_indices:
            start_x = pad_l + slot * forecast_indices[0]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(16, 185, 129, 14))
            painter.drawRoundedRect(QRectF(start_x, pad_t, pad_l + plot_w - start_x, plot_h), 8, 8)

        painter.setFont(QFont(self.font().family(), 8))
        text_metrics = painter.fontMetrics()

        for index, d in enumerate(data):
            center_x = pad_l + slot * index + slot / 2
            is_forecast = bool(d.get("forecast"))
            income = d.get("income", 0)
            spending = d.get("spending", 0)

            income_h = (income / max_value) * plot_h
            spend_h = (spending / max_value) * plot_h

            income_color = QColor(COLORS["emerald"])
            spend_color = QColor(COLORS["red"])
            if is_forecast:
                income_color.setAlpha(120)
                spend_color.setAlpha(120)

            painter.setPen(Qt.NoPen)
            painter.setBrush(income_color)
            painter.drawPath(
                _top_rounded_path(center_x - bar_w - gap / 2, base_y - income_h, bar_w, income_h, 4)
            )
            painter.setBrush(spend_color)
            painter.drawPath(
                _top_rounded_path(center_x + gap / 2, base_y - spend_h, bar_w, spend_h, 4)
            )

            # Month label
            painter.setPen(QColor(COLORS["muted"]))
            label = d.get("label", "")
            label_w = text_metrics.horizontalAdvance(label)
            painter.drawText(QPointF(center_x - label_w / 2, base_y + 16), label)

            # Net label
            net = d.get("net")
            if net is not None:
                net_text = format_inr_compact(net)
                net_w = text_metrics.horizontalAdvance(net_text)
                net_y = base_y - max(income_h, spend_h) - 7
                painter.setPen(QColor(COLORS["red"] if net < 0 else COLORS["emerald_dark"]))
                painter.drawText(QPointF(center_x - net_w / 2, max(net_y, 12)), net_text)


class SparkbarsChart(QWidget):
    """Tiny per-category bars (history solid, forecast faded)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self.setMinimumHeight(64)
        self.setMaximumHeight(64)

    def set_data(self, data: list[dict]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        data = self._data
        if not data:
            return

        pad = 4
        track_h = self.height() - 12
        base_y = self.height() - 4
        max_value = max([d.get("amount", 0) for d in data] + [1])
        slot = (self.width() - pad * 2) / len(data)
        bar_w = max(4.0, min(16.0, slot * 0.5))

        painter.setPen(Qt.NoPen)
        for index, d in enumerate(data):
            h = (d.get("amount", 0) / max_value) * track_h
            x = pad + slot * index + (slot - bar_w) / 2
            color = QColor(COLORS["emerald"] if d.get("forecast") else "#94a3b8")
            if d.get("forecast"):
                color.setAlpha(130)
            painter.setBrush(color)
            painter.drawPath(_top_rounded_path(x, base_y - h, bar_w, h, 3))
