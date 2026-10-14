"""Analytics page: forecasts, transfers, categories and anomaly flags."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import core
from ..charts import CashflowChart, SparkbarsChart
from ..format import format_inr, format_month, format_signed_inr
from ..theme import COLORS
from ..widgets import Card, PageHeader, StatCard, badge, hline

LEGEND_DOT = "font-size:14px;"


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


class AnalyticsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._horizon = 6

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        outer.addWidget(PageHeader("Analytics", "Deterministic forecasts — computed locally, nothing leaves this machine."))

        toolbar_host = QWidget()
        toolbar = QHBoxLayout(toolbar_host)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Forecast months:"))
        self.horizon_spin = QSpinBox()
        self.horizon_spin.setRange(1, 12)
        self.horizon_spin.setValue(self._horizon)
        self.horizon_spin.valueChanged.connect(self._on_horizon)
        toolbar.addWidget(self.horizon_spin)
        outer.addWidget(toolbar_host)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 6, 0)
        self.content_layout.setSpacing(18)
        scroll.setWidget(self.content)
        outer.addWidget(scroll, 1)

    def _on_horizon(self, value: int) -> None:
        self._horizon = value
        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        spending = core.get_spending(self._horizon)
        cashflow = core.get_cashflow(self._horizon)
        anomalies = core.get_anomalies()

        _clear_layout(self.content_layout)
        self.content_layout.addWidget(self._build_stats(cashflow))
        missing = cashflow.get("accounts_missing_balance") or []
        if missing:
            self.content_layout.addWidget(self._build_opening_balance(missing))
        self.content_layout.addWidget(self._build_forecast(cashflow))
        self.content_layout.addWidget(self._build_transfers(cashflow))
        self.content_layout.addWidget(self._build_categories(spending))
        self.content_layout.addWidget(self._build_anomalies(anomalies))
        self.content_layout.addStretch(1)

    # ------------------------------------------------------------------ #
    def _build_stats(self, cashflow: dict) -> QWidget:
        forecast = cashflow.get("forecast") or []
        last = forecast[-1] if forecast else None
        projected = last["cumulative"] if last else cashflow.get("current_balance")

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        balance = cashflow.get("current_balance")
        runway = cashflow.get("runway_months")
        current_net = cashflow.get("current_net", 0)

        cards = [
            StatCard("Current balance", format_inr(balance) if balance is not None else "—"),
            StatCard("Runway", f"{runway} months" if runway is not None else "—"),
            StatCard("Current net", format_signed_inr(current_net), "emerald" if current_net >= 0 else "red"),
            StatCard("Projected cumulative", format_inr(projected) if projected is not None else "—",
                     "emerald" if (projected or 0) >= 0 else "red"),
        ]
        for card in cards:
            layout.addWidget(card)
        return row

    def _build_opening_balance(self, missing: list[dict]) -> Card:
        card = Card()
        title = QLabel("Opening balance needed")
        title.setObjectName("SectionTitle")
        note = QLabel("No balance column was found for these accounts. Enter an opening balance so the cumulative cash-flow starts from a real number.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        card.body().addWidget(title)
        card.body().addWidget(note)
        for account in missing:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(f"{account['bank_name']} · {account['account_number']}")
            entry = QLineEdit()
            entry.setPlaceholderText("Opening balance")
            entry.setFixedWidth(160)
            save = QPushButton("Save")
            save.setObjectName("Primary")
            save.clicked.connect(lambda _=False, a=account, e=entry: self._save_opening(a["id"], e.text()))
            layout.addWidget(label, 1)
            layout.addWidget(entry)
            layout.addWidget(save)
            card.body().addWidget(row)
        return card

    def _save_opening(self, account_id: int, raw: str) -> None:
        try:
            value = float(raw.replace(",", "").strip())
        except (ValueError, AttributeError):
            return
        core.set_opening_balance(account_id, value)
        self.refresh()

    def _build_forecast(self, cashflow: dict) -> Card:
        card = Card()
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Cash-Flow Forecast")
        title.setObjectName("SectionTitle")
        legend = QLabel(
            f'<span style="color:{COLORS["emerald"]};{LEGEND_DOT}">●</span> Income&nbsp;&nbsp;'
            f'<span style="color:{COLORS["red"]};{LEGEND_DOT}">●</span> Spending'
        )
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(legend)
        card.body().addWidget(header)

        historical = cashflow.get("historical") or []
        forecast = cashflow.get("forecast") or []
        chart_data = [
            {
                "label": f"{m['month'][5:]}/{m['month'][2:4]}",
                "income": m["income"],
                "spending": m["spending"],
                "net": m["net"],
                "forecast": False,
            }
            for m in historical
        ] + [
            {
                "label": f"{m['month'][5:]}/{m['month'][2:4]}",
                "income": m["income"],
                "spending": m["spending"],
                "net": m["net"],
                "forecast": True,
            }
            for m in forecast
        ]
        chart = CashflowChart()
        chart.set_data(chart_data)
        card.body().addWidget(chart)

        message = cashflow.get("message")
        if message:
            warn = QLabel(message)
            warn.setObjectName("WarnText")
            card.body().addWidget(warn)

        if forecast:
            meta = QWidget()
            meta_layout = QHBoxLayout(meta)
            meta_layout.setContentsMargins(0, 0, 0, 0)
            starting = QLabel(
                f'Starting balance: <b>{format_inr(cashflow.get("starting_balance", 0))}</b>'
            )
            confidence = QLabel(
                f'Confidence: <b>{cashflow.get("confidence")}</b> · {cashflow.get("months_of_history")} months of history'
            )
            confidence.setObjectName("Muted")
            meta_layout.addWidget(starting)
            meta_layout.addStretch(1)
            meta_layout.addWidget(confidence)
            card.body().addWidget(meta)

            table = QTableWidget(len(forecast), 5)
            table.setHorizontalHeaderLabels(["Month", "Income", "Spending", "Net", "Cumulative"])
            table.verticalHeader().setVisible(False)
            table.setShowGrid(False)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionMode(QTableWidget.NoSelection)
            table.setFocusPolicy(Qt.NoFocus)
            header_view = table.horizontalHeader()
            header_view.setSectionResizeMode(0, QHeaderView.Stretch)
            for col in range(1, 5):
                header_view.setSectionResizeMode(col, QHeaderView.ResizeToContents)
            for row_index, m in enumerate(forecast):
                values = [
                    format_month(m["month"]),
                    format_inr(m["income"]),
                    format_inr(-m["spending"]),
                    format_signed_inr(m["net"]),
                    format_inr(m["cumulative"]),
                ]
                for col, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    if col > 0:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if col == 1:
                        item.setForeground(QColor(COLORS["emerald_dark"]))
                    elif col == 2:
                        item.setForeground(QColor(COLORS["red"]))
                    elif col == 3:
                        item.setForeground(QColor(COLORS["emerald_dark"] if m["net"] >= 0 else COLORS["red"]))
                    elif col == 4:
                        item.setForeground(QColor(COLORS["text"]))
                    table.setItem(row_index, col, item)
            table.setFixedHeight(min(len(forecast), 8) * 36 + 42)
            card.body().addWidget(table)

        note = QLabel(cashflow.get("note", ""))
        note.setObjectName("Muted")
        note.setWordWrap(True)
        card.body().addWidget(note)
        return card

    def _build_transfers(self, cashflow: dict) -> Card:
        card = Card()
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Transfers (excluded)")
        title.setObjectName("SectionTitle")
        caption = QLabel("not counted as income or spending")
        caption.setObjectName("Muted")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(caption)
        card.body().addWidget(header)

        transfers = cashflow.get("transfers") or []
        if not transfers:
            empty = QLabel("No internal transfers detected.")
            empty.setObjectName("Muted")
            card.body().addWidget(empty)
            return card

        for transfer in transfers:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 2, 0, 2)
            text = QLabel(
                f'<b>{transfer["description"]}</b><br>'
                f'<span style="color:{COLORS["muted"]};font-size:11px;">{transfer["date"]} · {transfer["category"] or ""}</span>'
            )
            text.setWordWrap(True)
            amount = QLabel(format_inr(transfer["amount"]))
            amount.setObjectName("AmountNeg" if transfer["amount"] < 0 else "AmountPos")
            button = QPushButton("Not a transfer")
            button.setObjectName("Ghost")
            button.clicked.connect(
                lambda _=False, tid=transfer["id"]: self._toggle_transfer(tid, False)
            )
            layout.addWidget(text, 1)
            layout.addWidget(amount)
            layout.addWidget(button)
            card.body().addWidget(row)
        return card

    def _toggle_transfer(self, transaction_id: int, value: bool) -> None:
        core.set_transfer_flag(transaction_id, value)
        self.refresh()

    def _build_categories(self, spending: dict) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Spending by Category")
        title.setObjectName("SectionTitle")
        caption = QLabel("solid = history · faded = forecast")
        caption.setObjectName("Muted")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(caption)
        layout.addWidget(header)

        message = spending.get("message")
        if message:
            warn = QLabel(message)
            warn.setObjectName("WarnText")
            layout.addWidget(warn)

        categories = spending.get("categories") or []
        if not categories:
            empty = Card()
            empty.body().addWidget(QLabel("No spending data to forecast yet."))
            layout.addWidget(empty)
            return section

        grid = QGridLayout()
        grid.setSpacing(16)
        for index, item in enumerate(categories):
            grid.addWidget(self._category_card(item), index // 3, index % 3)
        layout.addLayout(grid)
        return section

    def _category_card(self, item: dict) -> Card:
        card = Card()
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        name = QLabel(item["category"])
        name.setObjectName("SectionTitle")
        header_layout.addWidget(name)
        header_layout.addStretch(1)
        if item.get("confidence"):
            header_layout.addWidget(badge(item["confidence"], "slate"))
        card.body().addWidget(header)

        months = item.get("months_of_history", 0)
        caption = QLabel(f"{months} month{'s' if months != 1 else ''} of history")
        caption.setObjectName("Muted")
        card.body().addWidget(caption)

        series = [
            {"amount": h["amount"], "forecast": False} for h in item.get("history", [])
        ] + [
            {"amount": f["amount"], "forecast": True} for f in item.get("forecast", [])
        ]
        spark = SparkbarsChart()
        spark.set_data(series)
        card.body().addWidget(spark)

        forecast = item.get("forecast") or []
        if forecast:
            card.body().addWidget(hline())
            for entry in forecast:
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                month = QLabel(format_month(entry["month"]))
                month.setObjectName("Muted")
                amount = QLabel(format_inr(entry["amount"]))
                amount.setStyleSheet("font-weight:600;")
                row_layout.addWidget(month)
                row_layout.addStretch(1)
                row_layout.addWidget(amount)
                card.body().addWidget(row)
            if forecast[0].get("low") is not None and forecast[0].get("high") is not None:
                rng = QLabel(
                    f'Range {format_inr(forecast[0]["low"])} – {format_inr(forecast[0]["high"])}'
                )
                rng.setObjectName("Muted")
                card.body().addWidget(rng)
        else:
            card.body().addWidget(hline())
            nodata = QLabel("Not enough data to forecast.")
            nodata.setObjectName("Muted")
            card.body().addWidget(nodata)
        return card

    def _build_anomalies(self, anomalies: dict) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        spikes = anomalies.get("category_spikes") or []
        dups = anomalies.get("duplicates") or []
        first_time = anomalies.get("first_time_large") or []
        total = len(spikes) + len(dups) + len(first_time)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Anomaly Flags")
        title.setObjectName("SectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        if total:
            header_layout.addWidget(badge(f"{total} flagged", "red"))
        layout.addWidget(header)

        if anomalies.get("insufficient_history"):
            card = Card()
            msg = QLabel(anomalies.get("message") or "Not enough history for anomaly detection")
            msg.setObjectName("WarnText")
            card.body().addWidget(msg)
            layout.addWidget(card)
            return section

        if total == 0:
            card = Card()
            ok = QLabel("✓ No anomalies detected.")
            ok.setStyleSheet(f"color:{COLORS['emerald_dark']}; font-size:14px; font-weight:600;")
            ok.setAlignment(Qt.AlignCenter)
            card.body().addWidget(ok)
            layout.addWidget(card)
            return section

        if spikes:
            layout.addWidget(self._anomaly_card("⚠ Category spikes", "amber", [
                (
                    f'<b>{s["category"]}</b> · {s["month"]}',
                    f'{format_inr(s["amount"])}  (mean {format_inr(s["mean_monthly"])} ± {format_inr(s["std"])})',
                )
                for s in spikes
            ]))
        if dups:
            layout.addWidget(self._anomaly_card("© Potential duplicate charges", "amber", [
                (
                    f'{d["count"]}× {d["merchant"]} · {d["date"]}',
                    format_inr(d["amount"]),
                )
                for d in dups
            ]))
        if first_time:
            layout.addWidget(self._anomaly_card("! First-time merchants with large amounts", "red", [
                (
                    f'{w["description"]}<br><span style="color:{COLORS["muted"]};font-size:11px;">{w["date"]}</span>',
                    format_inr(w["amount"]),
                )
                for w in first_time
            ]))
        return section

    def _anomaly_card(self, title: str, tone: str, rows: list[tuple[str, str]]) -> Card:
        card = Card(padding=0)
        header = QLabel(title)
        bg = COLORS["amber"] if tone == "amber" else COLORS["red"]
        header.setStyleSheet(
            f"background:{bg}1a; color:{bg}; padding:12px 18px;"
            "border-top-left-radius:16px; border-top-right-radius:16px; font-weight:600;"
        )
        card.body().addWidget(header)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 12, 18, 16)
        body_layout.setSpacing(10)
        for left, right in rows:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            left_label = QLabel(left)
            left_label.setWordWrap(True)
            right_label = QLabel(right)
            right_label.setObjectName("AmountNeg")
            right_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
            row_layout.addWidget(left_label, 1)
            row_layout.addWidget(right_label)
            body_layout.addWidget(row)
        card.body().addWidget(body)
        return card
