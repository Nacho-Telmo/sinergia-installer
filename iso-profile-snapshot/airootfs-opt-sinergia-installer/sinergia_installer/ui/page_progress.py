from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.core.installer_engine import InstallerEngine
from sinergia_installer.models.install_config import InstallConfig


class ProgressPage(QWidget):
    install_finished = pyqtSignal(bool, str)

    def __init__(self, config: InstallConfig, engine: InstallerEngine) -> None:
        super().__init__()
        self.config = config
        self.engine = engine
        self._running = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_status = QLabel("Preparando instalación...")
        self.lbl_status.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        layout.addWidget(self.txt_log)

        actions = QHBoxLayout()
        actions.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._on_cancel)
        actions.addWidget(self.btn_cancel)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self.engine.step_changed.connect(self._on_step_changed)
        self.engine.log_line.connect(self._on_log_line)
        self.engine.finished_install.connect(self._on_finished)

    def start_installation(self) -> None:
        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Iniciando...")
        self._running = True
        self.btn_cancel.setEnabled(True)
        self.engine.start(self.config)

    def _on_cancel(self) -> None:
        if self._running:
            self.lbl_status.setText("Cancelando...")
            self.btn_cancel.setEnabled(False)
            self.engine.cancel()

    def _on_step_changed(self, current: int, total: int, label: str) -> None:
        self.lbl_status.setText(f"Paso {current} de {total}: {label}")
        if total > 0:
            pct = int(((current - 1) / total) * 100)
            self.progress_bar.setValue(pct)

    def _on_log_line(self, line: str) -> None:
        self.txt_log.appendPlainText(line)

    def _on_finished(self, ok: bool, message: str) -> None:
        self._running = False
        self.btn_cancel.setEnabled(False)
        if ok:
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"Listo: {message}")
        else:
            self.lbl_status.setText(f"Detenido: {message}")
        self.install_finished.emit(ok, message)
