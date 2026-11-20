import shlex
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.core.installer_engine import InstallerEngine
from sinergia_installer.models.install_config import InstallConfig


class SummaryPage(QWidget):
    def __init__(self, config: InstallConfig, engine: InstallerEngine) -> None:
        super().__init__()
        self.config = config
        self.engine = engine
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        grp_summary = QGroupBox("Resumen de instalación")
        sum_layout = QVBoxLayout(grp_summary)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setWordWrap(True)
        sum_layout.addWidget(self.lbl_summary)
        layout.addWidget(grp_summary)

        grp_plan = QGroupBox("Plan de comandos a ejecutar")
        plan_layout = QVBoxLayout(grp_plan)
        self.txt_plan = QPlainTextEdit()
        self.txt_plan.setReadOnly(True)
        self.txt_plan.setMaximumHeight(180)
        plan_layout.addWidget(self.txt_plan)
        layout.addWidget(grp_plan)

        self.chk_dry_run = QCheckBox("Modo simulación (dry-run): mostrar pasos sin tocar los discos")
        self.chk_dry_run.setChecked(self.config.dry_run)
        self.chk_dry_run.toggled.connect(self._on_dry_run_toggled)
        layout.addWidget(self.chk_dry_run)

    def _on_dry_run_toggled(self, checked: bool) -> None:
        self.config.dry_run = checked

    def refresh_summary(self) -> None:
        c = self.config
        p = c.partitions
        self.chk_dry_run.setChecked(c.dry_run)

        efi_line = (
            f"{p.efi_device} (formatear: {'Sí' if p.format_efi else 'No'})"
            if p.is_uefi and p.efi_device
            else "No aplica (BIOS / sin EFI)"
        )
        home_line = (
            f"{p.home_device} (formatear: {'Sí' if p.format_home else 'No'})"
            if p.home_device
            else "Dentro de la partición raíz (/)"
        )

        self.lbl_summary.setText(
            f"<b>Modo arranque:</b> {'UEFI' if p.is_uefi else 'BIOS / Legacy'}<br>"
            f"<b>Raíz (/):</b> {p.root_device} ({p.root_fs}, formatear: {'Sí' if p.format_root else 'No'})<br>"
            f"<b>EFI (/boot/efi):</b> {efi_line}<br>"
            f"<b>/home:</b> {home_line}<br>"
            f"<b>Idioma / Teclado / Zona:</b> {c.locale} · {c.keymap} · {c.timezone}<br>"
            f"<b>Usuario / Hostname:</b> {c.username} ({c.full_name}) en <code>{c.hostname}</code>"
            f"{' · <i>sudo sin contraseña</i>' if c.sudo_nopasswd else ''}"
        )

        steps = self.engine.build_plan(c)
        lines: list[str] = []
        for idx, (label, cmd) in enumerate(steps, start=1):
            lines.append(f"{idx}. {label}")
            lines.append(f"   $ {shlex.join(cmd)}")
        self.txt_plan.setPlainText("\n".join(lines))
