"""Statements page: all transactions with filters, pagination and balances."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import core
from ..format import format_inr, format_signed_inr
from ..range_slider import MonthRangeSlider
from ..theme import COLORS
from ..widgets import Card, CategoryPickerDialog, ClickableBadge, PageHeader, badge

PAGE_SIZES = [20, 50, 100, 200]


class StatementsPage(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self._page = 1
        self._page_size = 50

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        outer.addWidget(
            PageHeader("Statements", "Every transaction across all uploaded statements.")
        )

        self.range_card = Card(parent=self)
        self.range_label_top = QLabel("Filter by month range")
        self.range_label_top.setObjectName("Muted")
        self.range_slider = MonthRangeSlider()
        self.range_slider.range_changed.connect(self._on_range_changed)
        self.range_card.body().addWidget(self.range_label_top)
        self.range_card.body().addWidget(self.range_slider)
        outer.addWidget(self.range_card)

        filter_card = Card(parent=self)
        self.account_combo = QComboBox()
        self.category_combo = QComboBox()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["All", "Credit (in)", "Debit (out)"])
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search description…")
        reset = QPushButton("Reset")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset_filters)

        filter_body = QWidget(self)
        frow = QHBoxLayout(filter_body)
        frow.setSpacing(10)
        frow.addWidget(self.account_combo)
        frow.addWidget(self.category_combo)
        frow.addWidget(self.type_combo)
        frow.addWidget(self.search, 1)
        frow.addWidget(reset)
        filter_card.body().addWidget(filter_body)
        outer.addWidget(filter_card)

        table_card = Card(parent=self, padding=0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Description", "Category", "Account", "Balance", "Amount"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        table_card.body().addWidget(self.table)
        table_card.body().addWidget(self._build_pagination())
        outer.addWidget(table_card, 1)

        self.search.textChanged.connect(lambda _: self._reload())
        self.account_combo.currentIndexChanged.connect(lambda _: self._reload())
        self.category_combo.currentIndexChanged.connect(lambda _: self._reload())
        self.type_combo.currentIndexChanged.connect(lambda _: self._reload())

    # ------------------------------------------------------------------ #
    def _build_pagination(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 8, 14, 12)
        self.rows_label = QLabel("0 of 0")
        self.rows_label.setObjectName("Muted")
        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setObjectName("Muted")

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems([str(n) for n in PAGE_SIZES])
        self.page_size_combo.setCurrentText("50")
        self.page_size_combo.currentTextChanged.connect(self._change_page_size)

        self.prev_btn = QPushButton("‹ Prev")
        self.prev_btn.setObjectName("Ghost")
        self.prev_btn.clicked.connect(lambda: self._go(self._page - 1))
        self.next_btn = QPushButton("Next ›")
        self.next_btn.setObjectName("Ghost")
        self.next_btn.clicked.connect(lambda: self._go(self._page + 1))

        layout.addWidget(self.rows_label, 1)
        layout.addWidget(QLabel("Rows:"))
        layout.addWidget(self.page_size_combo)
        layout.addSpacing(8)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.page_label)
        layout.addWidget(self.next_btn)
        return bar

    def _reset_filters(self) -> None:
        self.search.clear()
        self.account_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.range_slider.reset_to_last(3)
        self._reload()

    def _change_page_size(self, text: str) -> None:
        self._page_size = int(text)
        self._page = 1
        self._render()

    def _go(self, page: int) -> None:
        total_pages = max(1, (len(self._rows) + self._page_size - 1) // self._page_size)
        self._page = min(max(1, page), total_pages)
        self._render()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        self._reload_combos()
        self._reload_months()
        self._reload()

    def _reload_combos(self) -> None:
        current_account = self.account_combo.currentData()
        current_category = self.category_combo.currentData()
        self.account_combo.blockSignals(True)
        self.category_combo.blockSignals(True)
        self.account_combo.clear()
        self.account_combo.addItem("All accounts", None)
        for account in core.list_accounts():
            self.account_combo.addItem(
                f"{account['bank_name']} {account['account_number']}", account["id"]
            )
        self.category_combo.clear()
        self.category_combo.addItem("All categories", None)
        for category in core.list_categories():
            self.category_combo.addItem(category, category)
        if current_account is not None:
            index = self.account_combo.findData(current_account)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)
        if current_category is not None:
            index = self.category_combo.findData(current_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        self.account_combo.blockSignals(False)
        self.category_combo.blockSignals(False)

    def _reload_months(self) -> None:
        months = core.transaction_months()
        self.range_slider.set_months(months)

    def _on_range_changed(self, low: int, high: int) -> None:
        self._reload()

    def _current_filters(self) -> dict:
        type_text = self.type_combo.currentText()
        filters: dict = {
            "account_id": self.account_combo.currentData(),
            "category": self.category_combo.currentData(),
            "q": self.search.text().strip() or None,
        }
        if type_text.startswith("Credit"):
            filters["type"] = "credit"
        elif type_text.startswith("Debit"):
            filters["type"] = "debit"
        range_dates = self.range_slider.range_dates()
        if range_dates is not None:
            filters["from"], filters["to"] = range_dates
        return filters

    def _reload(self) -> None:
        self._rows = core.list_transactions(self._current_filters())
        self._page = 1
        self._render()

    def _render(self) -> None:
        total = len(self._rows)
        total_pages = max(1, (total + self._page_size - 1) // self._page_size)
        self._page = min(self._page, total_pages)
        start = (self._page - 1) * self._page_size
        page_rows = self._rows[start : start + self._page_size]

        self.table.setRowCount(len(page_rows))
        for row_index, txn in enumerate(page_rows):
            date_item = QTableWidgetItem(txn["date"].strftime("%d %b %Y"))
            date_item.setForeground(QColor(COLORS["muted"]))

            desc = txn["description"]
            if txn["is_internal_transfer"]:
                desc = f"{desc}   ↺ transfer"
            if txn.get("source_file"):
                desc = f"{desc}   [{txn['source_file']}]"
            desc_item = QTableWidgetItem(desc)

            account_item = QTableWidgetItem(txn["account"])
            account_item.setForeground(QColor(COLORS["muted"]))

            balance_item = QTableWidgetItem(
                format_inr(txn["balance_after"]) if txn["balance_after"] is not None else "—"
            )
            balance_item.setForeground(QColor(COLORS["muted"]))
            balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            amount = txn["amount"]
            amount_text = format_signed_inr(amount)
            amount_item = QTableWidgetItem(amount_text)
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            color = COLORS["emerald_dark"] if amount > 0 else COLORS["red"]
            amount_item.setForeground(QColor(color))

            tone = "amber" if txn["is_internal_transfer"] else ("emerald" if amount > 0 else "slate")
            category_label = txn["category"] or "Uncategorized"
            if txn["is_internal_transfer"]:
                category_label = f"{category_label} · transfer"

            is_uncategorized = (txn["category"] in (None, "Uncategorized")) and not txn["is_internal_transfer"]
            if is_uncategorized:
                category_widget = ClickableBadge("Uncategorized ▾", "amber")
                category_widget.clicked.connect(
                    lambda _=False, tid=txn["id"]: self._assign_category(tid)
                )
            else:
                category_widget = badge(category_label, tone)

            self.table.setItem(row_index, 0, date_item)
            self.table.setItem(row_index, 1, desc_item)
            self.table.setCellWidget(row_index, 2, category_widget)
            self.table.setItem(row_index, 3, account_item)
            self.table.setItem(row_index, 4, balance_item)
            self.table.setItem(row_index, 5, amount_item)

        self.rows_label.setText(
            "0 of 0"
            if total == 0
            else f"{start + 1}–{min(start + self._page_size, total)} of {total}"
        )
        self.page_label.setText(f"Page {self._page} of {total_pages}")
        self.prev_btn.setEnabled(self._page > 1)
        self.next_btn.setEnabled(self._page < total_pages)

    # ------------------------------------------------------------------ #
    def _context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if item is None:
            return
        row = item.row()
        start = (self._page - 1) * self._page_size
        txn = self._rows[start + row]

        menu = QMenu(self)
        toggle = menu.addAction(
            "Mark as real spending/income"
            if txn["is_internal_transfer"]
            else "Mark as internal transfer"
        )
        change = menu.addAction("Change category…")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == toggle:
            core.set_transfer_flag(txn["id"], not txn["is_internal_transfer"])
            self.data_changed.emit()
            self._reload()
        elif action == change:
            name = CategoryPickerDialog(
                core.managed_categories(), self, title="Change category"
            ).get()
            if name:
                self._apply_category(txn["id"], name)

    def _assign_category(self, transaction_id: int) -> None:
        name = CategoryPickerDialog(core.managed_categories(), self).get()
        if name:
            self._apply_category(transaction_id, name)

    def _apply_category(self, transaction_id: int, name: str) -> None:
        if name not in core.managed_categories():
            core.add_category(name)
        core.set_category(transaction_id, name)
        self.data_changed.emit()
        self._reload()