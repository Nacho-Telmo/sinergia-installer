from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal
from sinergia_installer.models.install_config import InstallConfig


def build_chroot_env(config: InstallConfig) -> dict[str, str]:
    root_pw = config.password if config.same_password_for_root else config.root_password
    return {
        "LOCALE": config.locale,
        "KEYMAP": config.keymap,
        "TIMEZONE": config.timezone,
        "HOSTNAME": config.hostname,
        "USERNAME": config.username,
        "FULL_NAME": config.full_name,
        "PASSWORD": config.password,
        "ROOT_PASSWORD": root_pw,
        "SUDO_NOPASSWD": "1" if config.sudo_nopasswd else "0",
        "IS_UEFI": "1" if config.partitions.is_uefi else "0",
    }


def _format_cmd_for_log(cmd: list[str]) -> str:
    sanitized: list[str] = []
    for part in cmd:
        if part.startswith("PASSWORD="):
            sanitized.append("PASSWORD=***")
        elif part.startswith("ROOT_PASSWORD="):
            sanitized.append("ROOT_PASSWORD=***")
        else:
            sanitized.append(part)
    return " ".join(sanitized)


class InstallerEngine(QObject):
    log_line = pyqtSignal(str)
    step_changed = pyqtSignal(int, int, str)
    finished_install = pyqtSignal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._steps: list[tuple[str, list[str]]] = []
        self._current_index = 0
        self._cancelled = False
        self._active_config: InstallConfig | None = None

    def build_plan(self, config: InstallConfig) -> list[tuple[str, list[str]]]:
        p = config.partitions
        plan: list[tuple[str, list[str]]] = []

        if p.format_root and p.root_device:
            plan.append((f"Formatear raíz ({p.root_device}) como {p.root_fs}", ["mkfs.ext4", "-F", p.root_device]))

        plan.append((f"Montar raíz {p.root_device} en /mnt", ["mount", p.root_device, "/mnt"]))

        if p.is_uefi and p.efi_device:
            plan.append(("Crear /mnt/boot/efi", ["mkdir", "-p", "/mnt/boot/efi"]))
            if p.format_efi:
                plan.append((f"Formatear EFI ({p.efi_device}) en FAT32", ["mkfs.fat", "-F32", p.efi_device]))
            plan.append((f"Montar EFI {p.efi_device} en /mnt/boot/efi", ["mount", p.efi_device, "/mnt/boot/efi"]))

        if p.home_device:
            plan.append(("Crear /mnt/home", ["mkdir", "-p", "/mnt/home"]))
            if p.format_home:
                plan.append((f"Formatear /home ({p.home_device})", ["mkfs.ext4", "-F", p.home_device]))
            plan.append((f"Montar /home {p.home_device} en /mnt/home", ["mount", p.home_device, "/mnt/home"]))

        swap_dev = (getattr(p, "swap_device", "") or "").strip()
        format_swap = bool(getattr(p, "format_swap", True))
        if swap_dev:
            if format_swap:
                plan.append((f"Formatear swap ({swap_dev})", ["mkswap", "-f", swap_dev]))
            plan.append((f"Activar swap ({swap_dev})", ["swapon", swap_dev]))

        plan.append((
            "Desplegar sistema base en /mnt",
            [
                "bash",
                "-c",
                "set -e; "
                "SFS='/run/archiso/bootmnt/arch/x86_64/airootfs.sfs'; "
                "if [ ! -f \"$SFS\" ]; then SFS=$(find /run/archiso -name airootfs.sfs 2>/dev/null | head -n 1); fi; "
                "if [ -n \"$SFS\" ] && [ -f \"$SFS\" ]; then "
                "  unsquashfs -f -d /mnt \"$SFS\"; "
                "else "
                "  rsync -aAX --exclude='/dev/*' --exclude='/proc/*' --exclude='/sys/*' "
                "--exclude='/tmp/*' --exclude='/run/*' --exclude='/mnt/*' --exclude='/media/*' "
                "--exclude='/var/tmp/*' --exclude='/var/cache/pacman/pkg/*' --exclude='/lost+found' "
                "/ /mnt/; "
                "fi"
            ],
        ))
        plan.append((
            "Copiar kernel vmlinuz-linux a /mnt/boot",
            [
                "bash",
                "-c",
                "set -e; "
                "KRN='/run/archiso/bootmnt/arch/boot/x86_64/vmlinuz-linux'; "
                "if [ ! -f \"$KRN\" ]; then KRN=$(find /run/archiso -name 'vmlinuz*' 2>/dev/null | head -n 1); fi; "
                "if [ ! -f \"$KRN\" ] && [ -f /boot/vmlinuz-linux ]; then KRN='/boot/vmlinuz-linux'; fi; "
                "mkdir -p /mnt/boot && cp \"$KRN\" /mnt/boot/vmlinuz-linux"
            ],
        ))
        plan.append((
            "Generar /mnt/etc/fstab",
            [
                "bash",
                "-c",
                "set -e; "
                "genfstab -U /mnt > /mnt/etc/fstab && test -s /mnt/etc/fstab; "
                "for dev in $(blkid -t TYPE=swap -o device 2>/dev/null || true); do "
                "  UUID=$(blkid -s UUID -o value \"$dev\" 2>/dev/null || true); "
                "  if [ -n \"$UUID\" ] && ! grep -q \"UUID=$UUID\" /mnt/etc/fstab; then "
                "    printf 'UUID=%s none swap defaults 0 0\\n' \"$UUID\" >> /mnt/etc/fstab; "
                "  fi; "
                "done",
            ],
        ))
        multilib_cmd = """
python3 - <<'PY'
from pathlib import Path

conf_path = Path("/mnt/etc/pacman.conf")
lines = conf_path.read_text(encoding="utf-8").splitlines()
out = []
has_active = any(line.strip() == "[multilib]" for line in lines)
uncommented = False
i = 0

while i < len(lines):
    s = lines[i].strip()
    if not has_active and s.startswith("#") and s.lstrip("#").strip() == "[multilib]":
        out.append("[multilib]")
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt.startswith("#") and "Include" in nxt and "/etc/pacman.d/mirrorlist" in nxt:
                out.append("Include = /etc/pacman.d/mirrorlist")
                i += 2
                uncommented = True
                continue
        out.append("Include = /etc/pacman.d/mirrorlist")
        uncommented = True
    else:
        out.append(lines[i])
    i += 1

if not has_active and not uncommented:
    if out and out[-1] != "":
        out.append("")
    out.extend(["[multilib]", "Include = /etc/pacman.d/mirrorlist"])

conf_path.write_text(chr(10).join(out) + chr(10), encoding="utf-8")
PY
arch-chroot /mnt pacman -Sy --noconfirm
"""

        plan.append((
            "Habilitar repositorio [multilib] en /mnt/etc/pacman.conf",
            ["bash", "-c", multilib_cmd],
        ))
        plan.append((
            "Asignar permisos de ejecución al script de post-instalación",
            ["chmod", "0755", "/mnt/usr/local/bin/sinergia-post-install.sh"],
        ))

        env_vars = [f"{k}={v}" for k, v in build_chroot_env(config).items()]
        plan.append((
            "Configurar zona horaria, usuario y bootloader en /mnt",
            ["arch-chroot", "/mnt", "env", *env_vars, "bash", "/usr/local/bin/sinergia-post-install.sh"],
        ))
        plan.append(("Sincronizar escrituras en disco", ["sync"]))
        plan.append(("Desmontar /mnt limpiamente", ["umount", "-R", "/mnt"]))
        return plan

    def start(self, config: InstallConfig) -> None:
        self._cancelled = False
        self._active_config = config
        self._steps = self.build_plan(config)
        self._current_index = 0

        if not self._steps:
            self.finished_install.emit(False, "No hay pasos definidos para ejecutar.")
            return

        if config.dry_run:
            self._run_dry_run()
        else:
            self._run_next_real_step()

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _run_dry_run(self) -> None:
        total = len(self._steps)
        for idx, (label, cmd) in enumerate(self._steps, start=1):
            if self._cancelled:
                self.finished_install.emit(False, "Simulación cancelada por el usuario.")
                return
            self.step_changed.emit(idx, total, label)
            self.log_line.emit(f"[DRY-RUN] {label}")
            self.log_line.emit(f"          $ {_format_cmd_for_log(cmd)}")
        self.finished_install.emit(True, "Simulación completada sin modificar discos.")

    def _run_next_real_step(self) -> None:
        if self._cancelled:
            self.finished_install.emit(False, "Instalación cancelada.")
            return

        total = len(self._steps)
        if self._current_index >= total:
            self.finished_install.emit(True, "Instalación completada.")
            return

        label, cmd = self._steps[self._current_index]
        step_num = self._current_index + 1
        self.step_changed.emit(step_num, total, label)
        self.log_line.emit(f"==> {label}")
        self.log_line.emit(f"$ {_format_cmd_for_log(cmd)}")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        qenv = QProcessEnvironment.systemEnvironment()
        if cmd[0] == "arch-chroot" and self._active_config is not None:
            for key, val in build_chroot_env(self._active_config).items():
                qenv.insert(key, val)
        self._process.setProcessEnvironment(qenv)

        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_step_finished)
        self._process.start(cmd[0], cmd[1:])

    def _on_output(self) -> None:
        if not self._process:
            return
        text = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in text.splitlines():
            if line.strip():
                self.log_line.emit(line)

    def _on_step_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if exit_status != QProcess.ExitStatus.NormalExit or exit_code != 0:
            self.finished_install.emit(False, f"Error en el paso {self._current_index + 1} (código {exit_code}).")
            return

        self._current_index += 1
        self._run_next_real_step()
