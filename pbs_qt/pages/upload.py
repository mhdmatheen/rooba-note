"""Upload page: ingest bank statements (PDF / XLS / XLSX)."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import core
from ..theme import COLORS
from ..widgets import Card, PageHeader

SUPPORTED = (".pdf", ".xls", ".xlsx")


class _IngestWorker(QThread):
    finished_with = Signal(dict)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self) -> None:  # noqa: D401
        self.finished_with.emit(core.ingest_statement(self._path))


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setMinimumHeight(220)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)
        icon = QLabel("⬆")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"font-size:34px; color:{COLORS['emerald']};")
        title = QLabel("Drop a bank statement here")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:16px; font-weight:600;")
        subtitle = QLabel("or click to choose a file · ICICI PDF, HDFC XLS/XLSX")
        subtitle.setObjectName("Muted")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(subtitle)

    def _set_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active(True)

    def dragLeaveEvent(self, event):  # noqa: N802
        self._set_active(False)

    def dropEvent(self, event):  # noqa: N802
        self._set_active(False)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.file_dropped.emit(path)
                break

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose bank statement",
                "",
                "Bank statements (*.pdf *.xls *.xlsx);;All files (*)",
            )
            if path:
                self.file_dropped.emit(path)


class UploadPage(QWidget):
    ingested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: _IngestWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(
            PageHeader(
                "Upload Statement",
                "Overlapping uploads are deduplicated automatically. Everything stays on this machine.",
            )
        )

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._handle_file)
        layout.addWidget(self.drop_zone)

        self.status_card = Card()
        self.status_label = QLabel("No file uploaded yet.")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        self.status_card.body().addWidget(self.status_label)
        self.status_card.hide()
        layout.addWidget(self.status_card)
        layout.addStretch(1)

    def _handle_file(self, path: str) -> None:
        filename = os.path.basename(path)
        if not filename.lower().endswith(SUPPORTED):
            self._show_status(f"Unsupported file type: {filename}", error=True)
            return

        self._show_status(f"Importing {filename}…", error=False)
        self.drop_zone.setEnabled(False)
        self._worker = _IngestWorker(path, self)
        self._worker.finished_with.connect(self._on_done)
        self._worker.start()

    def _on_done(self, result: dict) -> None:
        self.drop_zone.setEnabled(True)
        self._worker = None

        if result.get("error"):
            self._show_status(f"Import failed: {result['error']}", error=True)
            return

        inserted = result.get("inserted", 0)
        skipped = result.get("duplicates_skipped", 0)
        bank = result.get("bank", "")
        period = result.get("period") or {}
        period_text = ""
        if period.get("start") and period.get("end"):
            period_text = f" Period: {period['start']} → {period['end']}."
        self._show_status(
            f"Imported {inserted} transaction{'s' if inserted != 1 else ''} "
            f"from {bank} ({result.get('account_number', '')}); "
            f"skipped {skipped} duplicate{'s' if skipped != 1 else ''}.{period_text}",
            error=False,
        )
        self.ingested.emit()

    def _show_status(self, text: str, error: bool) -> None:
        self.status_card.show()
        label = self.status_label
        if error:
            label.setStyleSheet(
                f"color:{COLORS['red']}; background:#fee2e2; border-radius:10px; padding:12px 14px;"
            )
        else:
            label.setStyleSheet(
                f"color:{COLORS['emerald_dark']}; background:#d1fae5; border-radius:10px; padding:12px 14px;"
            )
        label.setText(text)
