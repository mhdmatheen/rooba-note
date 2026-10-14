"""Modern light theme: palette + Qt style sheet."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

COLORS = {
    "bg": "#f4f5f7",
    "sidebar": "#0f172a",
    "sidebar_hover": "#1e293b",
    "sidebar_active": "#10b981",
    "sidebar_text": "#94a3b8",
    "sidebar_text_active": "#ffffff",
    "card": "#ffffff",
    "border": "#e5e7eb",
    "text": "#111827",
    "muted": "#6b7280",
    "emerald": "#10b981",
    "emerald_dark": "#059669",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "blue": "#3b82f6",
    "slate_badge": "#f1f5f9",
}

QSS = f"""
* {{
    font-family: "Inter", "Segoe UI", "Ubuntu", "Cantarell", "Noto Sans", sans-serif;
    outline: none;
}}

QMainWindow, QWidget#Root {{
    background: {COLORS['bg']};
    color: {COLORS['text']};
}}

/* ---------------- Sidebar ---------------- */
QFrame#Sidebar {{
    background: {COLORS['sidebar']};
    border: none;
}}
QLabel#SidebarLogo {{
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
}}
QLabel#SidebarCaption {{
    color: {COLORS['sidebar_text']};
    font-size: 11px;
}}
QPushButton#Nav {{
    text-align: left;
    padding: 10px 14px;
    border: none;
    border-radius: 10px;
    color: {COLORS['sidebar_text']};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#Nav:hover {{
    background: {COLORS['sidebar_hover']};
    color: #e2e8f0;
}}
QPushButton#Nav:checked {{
    background: {COLORS['sidebar_active']};
    color: #ffffff;
    font-weight: 600;
}}
QFrame#SidebarNote {{
    background: {COLORS['sidebar_hover']};
    border-radius: 10px;
}}

/* ---------------- Cards ---------------- */
QFrame#Card {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 16px;
}}

/* ---------------- Typography ---------------- */
QLabel#PageTitle {{
    font-size: 24px;
    font-weight: 700;
    color: {COLORS['text']};
}}
QLabel#PageSubtitle {{
    font-size: 13px;
    color: {COLORS['muted']};
}}
QLabel#SectionTitle {{
    font-size: 16px;
    font-weight: 600;
    color: {COLORS['text']};
}}
QLabel#Muted {{
    color: {COLORS['muted']};
    font-size: 12px;
}}
QLabel#StatLabel {{
    color: {COLORS['muted']};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}}
QLabel#StatValue {{
    font-size: 22px;
    font-weight: 700;
    color: {COLORS['text']};
}}
QLabel#AmountPos {{ color: {COLORS['emerald_dark']}; font-weight: 600; }}
QLabel#AmountNeg {{ color: {COLORS['red']}; font-weight: 600; }}
QLabel#WarnText {{ color: {COLORS['amber']}; font-size: 13px; }}

/* ---------------- Buttons ---------------- */
QPushButton#Primary {{
    background: {COLORS['emerald']};
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#Primary:hover {{ background: {COLORS['emerald_dark']}; }}
QPushButton#Primary:disabled {{ background: #a7f3d0; color: #ecfdf5; }}

QPushButton#Ghost {{
    background: {COLORS['slate_badge']};
    color: #334155;
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 500;
    font-size: 13px;
}}
QPushButton#Ghost:hover {{ background: #e2e8f0; }}
QPushButton#Ghost:disabled {{ color: #cbd5e1; }}

QPushButton#LinkBtn {{
    background: transparent;
    color: {COLORS['emerald_dark']};
    border: none;
    font-weight: 600;
    font-size: 12px;
    text-align: left;
}}
QPushButton#LinkBtn:hover {{ color: {COLORS['emerald']}; }}

/* ---------------- Inputs ---------------- */
QLineEdit, QComboBox, QDateEdit, QSpinBox {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    border-radius: 9px;
    padding: 7px 10px;
    font-size: 13px;
    color: {COLORS['text']};
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
    border: 1px solid {COLORS['emerald']};
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: #ffffff;
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    selection-background-color: {COLORS['emerald']};
    selection-color: #ffffff;
    padding: 4px;
}}

/* ---------------- Tables ---------------- */
QTableView {{
    background: #ffffff;
    border: none;
    gridline-color: transparent;
    font-size: 13px;
    selection-background-color: #ecfdf5;
    selection-color: {COLORS['text']};
}}
QHeaderView::section {{
    background: #ffffff;
    color: {COLORS['muted']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 10px 12px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}}
QTableView::item {{
    border-bottom: 1px solid #f1f3f5;
    padding: 8px 12px;
}}

/* ---------------- Scrollbars ---------------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #94a3b8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #cbd5e1; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ---------------- Drop zone ---------------- */
QFrame#DropZone {{
    background: #ffffff;
    border: 2px dashed #cbd5e1;
    border-radius: 16px;
}}
QFrame#DropZone[dragActive="true"] {{
    border: 2px dashed {COLORS['emerald']};
    background: #f0fdf9;
}}

/* ---------------- Rows ---------------- */
QFrame#RowSep {{ background: #f1f3f5; max-height: 1px; border: none; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Inter", 10))
    app.setStyleSheet(QSS)
