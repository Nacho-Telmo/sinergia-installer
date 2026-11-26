from pathlib import Path
from PyQt6.QtCore import Qt
import subprocess
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)
from sinergia_installer.core.installer_engine import InstallerEngine
from sinergia_installer.models.install_config import InstallConfig
from sinergia_installer.ui.page_locale import LocalePage
from sinergia_installer.ui.page_partitions import PartitionsPage
from sinergia_installer.ui.page_progress import ProgressPage
from sinergia_installer.ui.page_summary import SummaryPage
from sinergia_installer.ui.page_user import UserPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Arkea — Sinergia Linux")
        self.resize(840, 650)
        self.config = InstallConfig(dry_run=False)
        self.engine = InstallerEngine(self)
        self._in_progress = False

        logo_path = Path(__file__).resolve().parent.parent / "assets" / "logo_puntillismo.png"
        if logo_path.is_file():
            self.setWindowIcon(QIcon(str(logo_path)))

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        header_bar = QHBoxLayout()
        header_bar.setSpacing(10)
        self.lbl_app_logo = QLabel()
        if logo_path.is_file():
            pm = QPixmap(str(logo_path))
            if not pm.isNull():
                self.lbl_app_logo.setPixmap(pm.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_bar.addWidget(self.lbl_app_logo)

        self.lbl_step = QLabel()
        header_bar.addWidget(self.lbl_step, stretch=1)
        root_layout.addLayout(header_bar)

        self.stack = QStackedWidget()
        self.page_partitions = PartitionsPage(self.config)
        self.page_locale = LocalePage(self.config)
        self.page_user = UserPage(self.config)
        self.page_summary = SummaryPage(self.config, self.engine)
        self.page_progress = ProgressPage(self.config, self.engine)
        self.page_progress.install_finished.connect(self._on_install_finished)

        for page in (
            self.page_partitions, self.page_locale, self.page_user,
            self.page_summary, self.page_progress,
        ):
            self.stack.addWidget(page)
        root_layout.addWidget(self.stack)

        nav = QHBoxLayout()
        self.btn_back = QPushButton("Anterior")
        self.btn_next = QPushButton("Siguiente")
        self.btn_back.clicked.connect(self.go_back)
        self.btn_next.clicked.connect(self.go_next)
        nav.addWidget(self.btn_back)
        nav.addStretch()
        nav.addWidget(self.btn_next)
        root_layout.addLayout(nav)
        self._sync_buttons()

    def go_back(self) -> None:
        if not self._in_progress and self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
            self._sync_buttons()

    def go_next(self) -> None:
        if self._in_progress:
            return
        current = self.stack.currentWidget()
        if isinstance(current, (PartitionsPage, LocalePage, UserPage)) and not current.save_and_validate():
            return
        idx = self.stack.currentIndex()
        if idx + 1 < self.stack.count():
            next_idx = idx + 1
            self.stack.setCurrentIndex(next_idx)
            next_widget = self.stack.widget(next_idx)
            if next_widget is self.page_summary:
                self.page_summary.refresh_summary()
            elif next_widget is self.page_progress:
                if self.config.partitions.mode == "auto" and not self.config.dry_run:
                    confirm = QMessageBox.warning(
                        self,
                        "Confirmación final de borrado de disco",
                        f"Se borrarán TODAS las particiones y datos de {self.config.partitions.target_disk} "
                        f"para instalar Sinergia Linux ({self.config.partitions.root_fs.upper()}).\n\n"
                        "Esta acción no se puede deshacer. ¿Deseás continuar?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if confirm != QMessageBox.StandardButton.Yes:
                        self.stack.setCurrentIndex(idx)
                        self._sync_buttons()
                        return
                self._in_progress = True
                self.page_progress.start_installation()
            self._sync_buttons()

    def _on_install_finished(self, ok: bool, message: str) -> None:
        self._in_progress = False
        self._sync_buttons()
        if ok:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle("Instalación completada")
            box.setText("Sinergia Linux se instaló con éxito.")
            info = message.strip() if message else "El sistema base y su configuración ya están listos."
            box.setInformativeText(f"{info}\n\n¿Deseás reiniciar el equipo ahora para iniciar Sinergia Linux?")
            btn_reboot = box.addButton("Reiniciar ahora", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Seguir aquí", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_reboot)
            box.exec()
            if box.clickedButton() == btn_reboot:
                self._reboot_system()

    def _reboot_system(self) -> None:
        for cmd in (["systemctl", "reboot"], ["pkexec", "systemctl", "reboot"], ["reboot"]):
            try:
                subprocess.Popen(cmd)
                return
            except OSError:
                continue

    def _sync_buttons(self) -> None:
        idx = self.stack.currentIndex()
        total = self.stack.count()
        self.btn_next.setText("Instalar" if self.stack.currentWidget() is self.page_summary else "Siguiente")
        self.lbl_step.setText(f"Paso {idx + 1} de {total}")
        self.btn_back.setEnabled(not self._in_progress and idx > 0)
        self.btn_next.setEnabled(not self._in_progress and idx + 1 < total)
