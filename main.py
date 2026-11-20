import os
import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication
from sinergia_installer.ui.main_window import MainWindow


def _apply_dark_theme(app: QApplication) -> None:
    app.setStyle("Fusion")

    palette = QPalette()
    bg_window = QColor("#12161f")
    bg_surface = QColor("#191f2c")
    bg_alt = QColor("#202838")
    text_main = QColor("#e6edf3")
    text_muted = QColor("#9aa6b8")
    accent = QColor("#0ea5e9")
    accent_text = QColor("#081018")
    border_col = QColor("#2c364b")

    palette.setColor(QPalette.ColorRole.Window, bg_window)
    palette.setColor(QPalette.ColorRole.WindowText, text_main)
    palette.setColor(QPalette.ColorRole.Base, bg_surface)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg_alt)
    palette.setColor(QPalette.ColorRole.ToolTipBase, bg_alt)
    palette.setColor(QPalette.ColorRole.ToolTipText, text_main)
    palette.setColor(QPalette.ColorRole.Text, text_main)
    palette.setColor(QPalette.ColorRole.PlaceholderText, text_muted)
    palette.setColor(QPalette.ColorRole.Button, bg_alt)
    palette.setColor(QPalette.ColorRole.ButtonText, text_main)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, accent)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, accent_text)

    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        text_muted,
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        text_muted,
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        text_muted,
    )

    app.setPalette(palette)

    app.setStyleSheet(
        f"""
        QMainWindow, QWidget {{
            background-color: #12161f;
            color: #e6edf3;
            font-size: 10pt;
        }}
        QLabel {{
            background: transparent;
            color: #e6edf3;
        }}
        QPushButton {{
            background-color: #1e2636;
            color: #e6edf3;
            border: 1px solid {border_col.name()};
            border-radius: 6px;
            padding: 7px 14px;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: #273247;
            border-color: #38bdf8;
        }}
        QPushButton:pressed, QPushButton:checked {{
            background-color: #0284c7;
            color: #ffffff;
            border-color: #38bdf8;
        }}
        QPushButton:disabled {{
            background-color: #161b26;
            color: #64748b;
            border-color: #222a3a;
        }}
        QProgressBar {{
            background-color: #191f2c;
            border: 1px solid {border_col.name()};
            border-radius: 6px;
            text-align: center;
            color: #e6edf3;
            min-height: 22px;
            font-weight: bold;
        }}
        QProgressBar::chunk {{
            background-color: #0ea5e9;
            border-radius: 5px;
        }}
        QPlainTextEdit, QTextEdit, QLineEdit, QComboBox, QListWidget, QTreeWidget {{
            background-color: #0e121a;
            color: #dce6f2;
            border: 1px solid {border_col.name()};
            border-radius: 6px;
            selection-background-color: #0284c7;
            selection-color: #ffffff;
        }}
        QMessageBox {{
            background-color: #161b26;
            color: #e6edf3;
        }}
        """
    )


def main() -> int:
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    _apply_dark_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
