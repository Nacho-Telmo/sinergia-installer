import subprocess
import shutil
# sinergia_installer/ui/page_partitions.py
import os
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.core.disks import (
    has_partition_manager,
    is_uefi_boot,
    list_partitions,
    validate_assignments,
)
from sinergia_installer.models.install_config import InstallConfig


class PartitionsPage(QWidget):
    def __init__(self, config: InstallConfig) -> None:
        super().__init__()
        self.config = config
        self._pm_process: QProcess | None = None
        self._build_ui()
        self.refresh_partitions()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        mode_text = "Modo de arranque detectado: UEFI" if is_uefi_boot() else "Modo de arranque detectado: BIOS / Legacy"
        self.lbl_boot_mode = QLabel(mode_text)
        layout.addWidget(self.lbl_boot_mode)

        toolbar = QHBoxLayout()
        self.btn_open_pm = QPushButton("Abrir KDE Partition Manager")
        self.btn_open_pm.setEnabled(has_partition_manager())
        self.btn_open_pm.clicked.connect(self.launch_partition_manager)

        self.btn_refresh = QPushButton("Actualizar particiones")
        self.btn_refresh.clicked.connect(self.refresh_partitions)

        toolbar.addWidget(self.btn_open_pm)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        form = QFormLayout()
        self.combo_root = QComboBox()
        self.chk_format_root = QCheckBox("Formatear partición raíz (ext4)")
        self.chk_format_root.setChecked(True)

        self.combo_efi = QComboBox()
        self.chk_format_efi = QCheckBox("Formatear partición EFI (FAT32)")

        self.combo_home = QComboBox()
        self.chk_format_home = QCheckBox("Formatear /home")

        form.addRow("Partición raíz (/):", self.combo_root)
        form.addRow("", self.chk_format_root)
        form.addRow("Partición EFI (/boot/efi):", self.combo_efi)
        form.addRow("", self.chk_format_efi)
        form.addRow("Partición /home (opcional):", self.combo_home)
        form.addRow("", self.chk_format_home)
        layout.addLayout(form)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #c62828;")
        layout.addWidget(self.lbl_error)
        layout.addStretch()

    def launch_partition_manager(self) -> None:
        self.lbl_error.setText("")
        self.btn_open_pm.setEnabled(False)

        self._pm_fallback_tried = False
        self._launch_partition_manager(use_dbus_session=False)

    def _allow_root_xwayland(self, display: str) -> None:
        if not display or not shutil.which("xhost"):
            return
        try:
            st = os.stat("/run/user/1000") if os.path.isdir("/run/user/1000") else None
            if st and shutil.which("runuser"):
                subprocess.run(
                    ["runuser", "-u", f"#{st.st_uid}", "--", "env", f"DISPLAY={display}", "xhost", "+SI:localuser:root"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=False,
                )
            else:
                subprocess.run(
                    ["env", f"DISPLAY={display}", "xhost", "+SI:localuser:root"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                    check=False,
                )
        except Exception:
            pass

    def _build_pm_env(self, use_xcb: bool) -> dict[str, str]:
        is_root = os.geteuid() == 0
        if not is_root:
            return dict(os.environ)

        display = os.environ.get("DISPLAY") or (":0" if os.path.exists("/tmp/.X11-unix/X0") else "")
        if display:
            self._allow_root_xwayland(display)

        runtime_dir = "/run/user/0" if os.path.isdir("/run/user/0") else "/tmp"
        env_vars = {
            "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/bin"),
            "HOME": "/root",
            "XDG_RUNTIME_DIR": runtime_dir,
        }
        if display:
            env_vars["DISPLAY"] = display
            env_vars["QT_QPA_PLATFORM"] = "xcb"
            env_vars["XDG_SESSION_TYPE"] = "x11"
        return env_vars

    def _launch_partition_manager(self, use_dbus_session: bool) -> None:
        is_root = os.geteuid() == 0
        env_vars = self._build_pm_env(use_xcb=True)
        env_args = [f"{k}={v}" for k, v in env_vars.items()]

        if is_root:
            cmd_tail = ["dbus-run-session", "--", "partitionmanager"] if use_dbus_session else ["partitionmanager"]
            program = "env"
            args = [*env_args, *cmd_tail]
        else:
            program = "partitionmanager"
            args = []

        self.lbl_error.clear()
        self._pm_process = QProcess(self)
        self._pm_process.errorOccurred.connect(self._on_pm_error)
        self._pm_process.finished.connect(self._on_pm_exit)
        self._pm_process.start(program, args)

    def _on_pm_error(self, error: QProcess.ProcessError) -> None:
        if os.geteuid() == 0 and not self._pm_fallback_tried:
            self._pm_fallback_tried = True
            self._launch_partition_manager(use_dbus_session=True)
            return
        self.btn_open_pm.setEnabled(has_partition_manager())
        self.lbl_error.setText(f"Error al lanzar KDE Partition Manager ({error.name}).")

    def _on_pm_exit(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        err_out = ""
        if self._pm_process is not None:
            err_out = bytes(self._pm_process.readAllStandardError()).decode("utf-8", errors="ignore").strip()

        if os.geteuid() == 0 and exit_code != 0 and not self._pm_fallback_tried:
            self._pm_fallback_tried = True
            self._launch_partition_manager(use_dbus_session=True)
            return

        self.btn_open_pm.setEnabled(has_partition_manager())
        if exit_code != 0:
            detalle = f": {err_out.splitlines()[-1]}" if err_out else ""
            self.lbl_error.setText(f"KDE Partition Manager cerró con código {exit_code}{detalle}")
        self.refresh_partitions()

    def refresh_partitions(self) -> None:
        partitions = list_partitions()
        self.combo_root.clear()
        self.combo_efi.clear()
        self.combo_home.clear()

        self.combo_efi.addItem("— Ninguna —", "")
        self.combo_home.addItem("— Usar dentro de / —", "")

        for part in partitions:
            label = f"{part.path}  ({part.size} · {part.fstype})"
            self.combo_root.addItem(label, part.path)
            self.combo_efi.addItem(label, part.path)
            self.combo_home.addItem(label, part.path)

    def save_and_validate(self) -> bool:
        root_dev = self.combo_root.currentData() or ""
        efi_dev = self.combo_efi.currentData() or ""
        home_dev = self.combo_home.currentData() or ""
        uefi = is_uefi_boot()

        errors = validate_assignments(root_dev, efi_dev, home_dev, uefi)
        if errors:
            self.lbl_error.setText("\n".join(errors))
            QMessageBox.warning(self, "Revisión de particiones", "\n".join(errors))
            return False

        self.lbl_error.setText("")
        self.config.partitions.root_device = root_dev
        self.config.partitions.format_root = self.chk_format_root.isChecked()
        self.config.partitions.efi_device = efi_dev
        self.config.partitions.format_efi = self.chk_format_efi.isChecked()
        self.config.partitions.home_device = home_dev
        self.config.partitions.format_home = self.chk_format_home.isChecked()
        self.config.partitions.is_uefi = uefi
        return True
