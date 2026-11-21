import os
import shutil
import subprocess
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.core.disks import (
    PhysicalDiskInfo,
    has_partition_manager,
    is_uefi_boot,
    list_partitions,
    list_physical_disks,
    validate_assignments,
    validate_auto_assignment,
)
from sinergia_installer.models.install_config import InstallConfig


class PartitionsPage(QWidget):
    def __init__(self, config: InstallConfig) -> None:
        super().__init__()
        self.config = config
        self._pm_process: QProcess | None = None
        self._disks: list[PhysicalDiskInfo] = []
        self._build_ui()
        self.refresh_partitions()
        self._sync_mode_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        mode_text = (
            "Modo de arranque detectado: UEFI"
            if is_uefi_boot()
            else "Modo de arranque detectado: BIOS / Legacy"
        )
        self.lbl_boot_mode = QLabel(mode_text)
        layout.addWidget(self.lbl_boot_mode)

        mode_box = QGroupBox("Esquema de particionado")
        mode_lay = QHBoxLayout(mode_box)
        self.radio_auto = QRadioButton("Particionado automático (borrar disco)")
        self.radio_manual = QRadioButton("Particionado manual")
        self.radio_manual.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_manual)
        self.mode_group.addButton(self.radio_auto)
        mode_lay.addWidget(self.radio_manual)
        mode_lay.addWidget(self.radio_auto)
        mode_lay.addStretch()
        layout.addWidget(mode_box)

        fs_row = QHBoxLayout()
        fs_row.addWidget(QLabel("Sistema de archivos:"))
        self.combo_fs = QComboBox()
        self.combo_fs.addItem("ext4 (clásico y estable)", "ext4")
        self.combo_fs.addItem("BTRFS (subvolúmenes @ / @home y compresión zstd)", "btrfs")
        self.combo_fs.currentIndexChanged.connect(self._on_fs_changed)
        fs_row.addWidget(self.combo_fs)
        fs_row.addStretch()
        layout.addLayout(fs_row)

        self.auto_box = QGroupBox("Opciones de particionado automático")
        auto_layout = QVBoxLayout(self.auto_box)
        auto_form = QFormLayout()

        self.combo_disk = QComboBox()
        self.combo_disk.currentIndexChanged.connect(self._on_disk_changed)
        auto_form.addRow("Disco destino:", self.combo_disk)

        swap_row = QHBoxLayout()
        self.chk_auto_swap = QCheckBox("Crear partición swap")
        self.chk_auto_swap.setChecked(True)
        self.chk_auto_swap.toggled.connect(self._on_auto_swap_toggled)
        self.spin_swap_gib = QSpinBox()
        self.spin_swap_gib.setRange(1, 64)
        self.spin_swap_gib.setValue(4)
        self.spin_swap_gib.setSuffix(" GiB")
        swap_row.addWidget(self.chk_auto_swap)
        swap_row.addWidget(self.spin_swap_gib)
        swap_row.addStretch()
        auto_form.addRow("Swap:", swap_row)

        self.chk_auto_home = QCheckBox("Separar /home en partición propia (el resto del disco)")
        self.chk_auto_home.setChecked(False)
        auto_form.addRow("/home:", self.chk_auto_home)

        auto_layout.addLayout(auto_form)

        self.lbl_auto_warn = QLabel(
            "Advertencia: el particionado automático borrará por completo todas las particiones y datos del disco elegido."
        )
        self.lbl_auto_warn.setWordWrap(True)
        self.lbl_auto_warn.setStyleSheet("color: #c62828; font-weight: bold;")
        auto_layout.addWidget(self.lbl_auto_warn)
        layout.addWidget(self.auto_box)

        self.manual_box = QGroupBox("Asignación manual de particiones")
        manual_layout = QVBoxLayout(self.manual_box)

        toolbar = QHBoxLayout()
        self.btn_open_pm = QPushButton("Abrir KDE Partition Manager")
        self.btn_open_pm.setEnabled(has_partition_manager())
        self.btn_open_pm.clicked.connect(self.launch_partition_manager)

        self.btn_refresh = QPushButton("Actualizar particiones")
        self.btn_refresh.clicked.connect(self.refresh_partitions)

        toolbar.addWidget(self.btn_open_pm)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch()
        manual_layout.addLayout(toolbar)

        form = QFormLayout()
        self.combo_root = QComboBox()
        self.chk_format_root = QCheckBox("Formatear partición raíz (ext4)")
        self.chk_format_root.setChecked(True)

        self.combo_efi = QComboBox()
        self.chk_format_efi = QCheckBox("Formatear partición EFI (FAT32)")

        self.combo_home = QComboBox()
        self.chk_format_home = QCheckBox("Formatear /home")

        self.combo_swap = QComboBox()
        self.chk_format_swap = QCheckBox("Formatear swap (mkswap)")
        self.chk_format_swap.setChecked(True)

        form.addRow("Partición raíz (/):", self.combo_root)
        form.addRow("", self.chk_format_root)
        form.addRow("Partición EFI (/boot/efi):", self.combo_efi)
        form.addRow("", self.chk_format_efi)
        form.addRow("Partición /home (opcional):", self.combo_home)
        form.addRow("", self.chk_format_home)
        form.addRow("Partición swap (opcional):", self.combo_swap)
        form.addRow("", self.chk_format_swap)
        manual_layout.addLayout(form)
        layout.addWidget(self.manual_box)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #c62828;")
        layout.addWidget(self.lbl_error)
        layout.addStretch()

        self.radio_auto.toggled.connect(self._sync_mode_ui)
        self.radio_manual.toggled.connect(self._sync_mode_ui)
        self._on_fs_changed()

    def _current_fs(self) -> str:
        return str(self.combo_fs.currentData() or "ext4")

    def _on_fs_changed(self) -> None:
        fs_label = self._current_fs().upper()
        self.chk_format_root.setText(f"Formatear partición raíz ({fs_label})")
        self.chk_format_home.setText(f"Formatear /home ({fs_label})")

    def _on_auto_swap_toggled(self, checked: bool) -> None:
        self.spin_swap_gib.setEnabled(checked)

    def _on_disk_changed(self) -> None:
        disk = self._selected_disk()
        if disk is not None:
            self.lbl_auto_warn.setText(
                f"Advertencia: se eliminarán todas las particiones y datos de {disk.path} "
                f"({disk.model}, {disk.size_human})."
            )
        else:
            self.lbl_auto_warn.setText(
                "Advertencia: el particionado automático borrará por completo todas las particiones y datos del disco elegido."
            )

    def _selected_disk(self) -> PhysicalDiskInfo | None:
        idx = self.combo_disk.currentIndex()
        if 0 <= idx < len(self._disks):
            return self._disks[idx]
        return None

    def _sync_mode_ui(self) -> None:
        is_auto = self.radio_auto.isChecked()
        self.auto_box.setVisible(is_auto)
        self.manual_box.setVisible(not is_auto)
        self.lbl_error.setText("")

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
        try:
            self._disks = list_physical_disks()
        except Exception:
            self._disks = []

        self.combo_disk.clear()
        for d in self._disks:
            self.combo_disk.addItem(f"{d.path} — {d.model} ({d.size_human}, {d.tran})", d.path)
        self._on_disk_changed()

        partitions = list_partitions()
        self.combo_root.clear()
        self.combo_efi.clear()
        self.combo_home.clear()
        self.combo_swap.clear()

        self.combo_efi.addItem("— Ninguna —", "")
        self.combo_home.addItem("— Usar dentro de / —", "")
        self.combo_swap.addItem("— Ninguna —", "")

        swap_idx = 0
        for part in partitions:
            label = f"{part.path}  ({part.size} · {part.fstype})"
            self.combo_root.addItem(label, part.path)
            self.combo_efi.addItem(label, part.path)
            self.combo_home.addItem(label, part.path)
            self.combo_swap.addItem(label, part.path)
            if (part.fstype or "").lower() in ("swap", "linux-swap"):
                swap_idx = self.combo_swap.count() - 1
        if swap_idx > 0:
            self.combo_swap.setCurrentIndex(swap_idx)

    def save_and_validate(self) -> bool:
        uefi = is_uefi_boot()
        fs = self._current_fs()

        if self.radio_auto.isChecked():
            disk = self._selected_disk()
            target_disk = disk.path if disk else ""
            disk_size = disk.size_bytes if disk else 0
            auto_swap = self.chk_auto_swap.isChecked()
            swap_gib = int(self.spin_swap_gib.value())
            sep_home = self.chk_auto_home.isChecked()

            errors = validate_auto_assignment(target_disk, disk_size, auto_swap, swap_gib, sep_home)
            if errors:
                self.lbl_error.setText("\n".join(errors))
                QMessageBox.warning(self, "Revisión de particionado automático", "\n".join(errors))
                return False

            self.lbl_error.setText("")
            self.config.partitions.mode = "auto"
            self.config.partitions.target_disk = target_disk
            self.config.partitions.auto_swap = auto_swap
            self.config.partitions.auto_swap_gib = swap_gib
            self.config.partitions.auto_separate_home = sep_home
            self.config.partitions.root_fs = fs
            self.config.partitions.format_root = True
            self.config.partitions.format_efi = True
            self.config.partitions.format_home = sep_home
            self.config.partitions.format_swap = auto_swap
            self.config.partitions.is_uefi = uefi
            return True

        root_dev = self.combo_root.currentData() or ""
        efi_dev = self.combo_efi.currentData() or ""
        home_dev = self.combo_home.currentData() or ""
        swap_dev = self.combo_swap.currentData() or ""

        errors = validate_assignments(root_dev, efi_dev, home_dev, uefi, swap_dev)
        if errors:
            self.lbl_error.setText("\n".join(errors))
            QMessageBox.warning(self, "Revisión de particiones", "\n".join(errors))
            return False

        self.lbl_error.setText("")
        self.config.partitions.mode = "manual"
        self.config.partitions.target_disk = ""
        self.config.partitions.root_device = root_dev
        self.config.partitions.format_root = self.chk_format_root.isChecked()
        self.config.partitions.root_fs = fs
        self.config.partitions.efi_device = efi_dev
        self.config.partitions.format_efi = self.chk_format_efi.isChecked()
        self.config.partitions.home_device = home_dev
        self.config.partitions.format_home = self.chk_format_home.isChecked()
        self.config.partitions.swap_device = swap_dev
        self.config.partitions.format_swap = self.chk_format_swap.isChecked()
        self.config.partitions.is_uefi = uefi
        return True
