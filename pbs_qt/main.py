"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import core
from .main_window import MainWindow
from .theme import apply_theme


def main() -> int:
    core.initialize()
    app = QApplication(sys.argv)
    app.setApplicationName("Rooba Note")
    app.setApplicationDisplayName("Rooba Note")
    apply_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
