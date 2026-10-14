"""Main window: dark sidebar + stacked content pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .pages.analytics import AnalyticsPage
from .pages.dashboard import DashboardPage
from .pages.settings import SettingsPage
from .pages.statements import StatementsPage
from .pages.upload import UploadPage

NAV_ITEMS = [
    ("Dashboard", "▤"),
    ("Statements", "≣"),
    ("Analytics", "◔"),
    ("Upload Statement", "⬆"),
    ("Settings", "⚙"),
]


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rooba Note · Personal Budgeting System")
        self.resize(1200, 800)
        self.setMinimumSize(940, 620)

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        self._root = root  # keep Python refs alive (Shiboken ownership)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_sidebar())

        content = QWidget()
        self._content = content
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(26, 24, 26, 24)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.statements = StatementsPage()
        self.analytics = AnalyticsPage()
        self.upload = UploadPage()
        self.settings = SettingsPage()
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.statements)
        self.stack.addWidget(self.analytics)
        self.stack.addWidget(self.upload)
        self.stack.addWidget(self.settings)
        content_layout.addWidget(self.stack)
        layout.addWidget(content, 1)

        # page data flow
        self.dashboard.data_changed.connect(self.analytics.refresh)
        self.dashboard.data_changed.connect(self.statements.refresh)
        self.statements.data_changed.connect(self.dashboard.refresh)
        self.statements.data_changed.connect(self.analytics.refresh)
        self.upload.ingested.connect(self._on_ingested)
        self.settings.data_changed.connect(self.dashboard.refresh)
        self.settings.data_changed.connect(self.statements.refresh)
        self.settings.data_changed.connect(self.analytics.refresh)

    # ------------------------------------------------------------------ #
    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(6)

        logo = QLabel("₹  Rooba Note")
        logo.setObjectName("SidebarLogo")
        caption = QLabel("Personal Budgeting System")
        caption.setObjectName("SidebarCaption")
        layout.addWidget(logo)
        layout.addWidget(caption)
        layout.addSpacing(22)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, (name, glyph) in enumerate(NAV_ITEMS):
            button = QPushButton(f"  {glyph}   {name}")
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, i=index: self._switch(i))
            self.nav_group.addButton(button, index)
            layout.addWidget(button)

        layout.addStretch(1)

        note = QFrame()
        note.setObjectName("SidebarNote")
        note_layout = QVBoxLayout(note)
        note_layout.setContentsMargins(12, 10, 12, 10)
        note_text = QLabel("Local only · deterministic\nNo data ever leaves this machine")
        note_text.setObjectName("SidebarCaption")
        note_text.setWordWrap(True)
        note_layout.addWidget(note_text)
        layout.addWidget(note)

        self.nav_group.button(0).setChecked(True)
        return sidebar

    def _switch(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _on_ingested(self) -> None:
        self.dashboard.refresh()
        self.statements.refresh()
        self.analytics.refresh()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self.dashboard.refresh()
