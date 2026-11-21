from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, pyqtSignal
from sinergia_installer.models.install_config import InstallConfig

def build_chroot_env(config: InstallConfig) -> dict[str, str]:
    root_pw = config.password if config.same_password_for_root else config.root_password
    return {
        "LOCALE": config.locale, "KEYMAP": config.keymap, "TIMEZONE": config.timezone,
        "HOSTNAME": config.hostname, "USERNAME": config.username, "FULL_NAME": config.full_name,
        "PASSWORD": config.password, "ROOT_PASSWORD": root_pw,
        "SUDO_NOPASSWD": "1" if config.sudo_nopasswd else "0",
        "IS_UEFI": "1" if config.partitions.is_uefi else "0",
    }

def _format_cmd_for_log(cmd: list[str]) -> str:
    return " ".join("PASSWORD=***" if p.startswith("PASSWORD=") else "ROOT_PASSWORD=***" if p.startswith("ROOT_PASSWORD=") else p for p in cmd)

def _format_fs_script(dev: str, fstype: str) -> str:
    fs = (fstype or "ext4").lower()
    return f"set -e; mkfs.btrfs -f {dev}" if fs == "btrfs" else f"set -e; mkfs.ext4 -F {dev}"
    def build_plan(self, config: InstallConfig) -> list[tuple[str, list[str]]]:
        p = config.partitions
        plan: list[tuple[str, list[str]]] = []
        is_auto = p.mode == "auto" and bool(p.target_disk)
        fs = (p.root_fs or "ext4").lower()
        if is_auto:
            plan.append((f"Particionar automáticamente {p.target_disk} (GPT)", ["bash", "-c", self._auto_partition_script(config)]))

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

    def _auto_partition_script(self, config: InstallConfig) -> str:
        pr = config.partitions
        swap_gib = int(pr.auto_swap_gib) if pr.auto_swap else 0
        sep_home = "1" if pr.auto_separate_home else "0"
        uefi = "1" if pr.is_uefi else "0"
        parts = [
            "set -euo pipefail",
            f"DISK=\"{pr.target_disk}\"",
            f"SWAP_GIB=\"{swap_gib}\"",
            f"SEP_HOME=\"{sep_home}\"",
            f"IS_UEFI=\"{uefi}\"",
            "for m in $(lsblk -ln -o MOUNTPOINT \"$DISK\" | awk 'NF' | sort -r); do umount -R \"$m\" 2>/dev/null || true; done",
            "for part in $(lsblk -ln -o PATH \"$DISK\" | tail -n +2); do swapoff \"$part\" 2>/dev/null || true; done",
            "wipefs -af \"$DISK\" && sgdisk --zap-all \"$DISK\"",
            "n=1; EFI_N=''",
            "if [ \"$IS_UEFI\" = \"1\" ]; then sgdisk -n \"${n}:0:+512M\" -t \"${n}:ef00\" -c \"${n}:EFI\" \"$DISK\"; EFI_N=\"$n\"; n=$((n+1)); else sgdisk -n \"${n}:0:+2M\" -t \"${n}:ef02\" -c \"${n}:BIOS_BOOT\" \"$DISK\"; n=$((n+1)); fi",
            "SWAP_N=''",
            "if [ \"$SWAP_GIB\" -gt 0 ]; then sgdisk -n \"${n}:0:+${SWAP_GIB}G\" -t \"${n}:8200\" -c \"${n}:SWAP\" \"$DISK\"; SWAP_N=\"$n\"; n=$((n+1)); fi",
            "ROOT_N=''; HOME_N=''",
            "if [ \"$SEP_HOME\" = \"1\" ]; then G=$(($(blockdev --getsz \"$DISK\") * 512 / 1024 / 1024 / 1024)); RG=40; [ \"$G\" -lt 90 ] && RG=$((G * 40 / 100)); [ \"$RG\" -lt 20 ] && RG=20; sgdisk -n \"${n}:0:+${RG}G\" -t \"${n}:8300\" -c \"${n}:ROOT\" \"$DISK\"; ROOT_N=\"$n\"; n=$((n+1)); sgdisk -n \"${n}:0:0\" -t \"${n}:8302\" -c \"${n}:HOME\" \"$DISK\"; HOME_N=\"$n\"; else sgdisk -n \"${n}:0:0\" -t \"${n}:8300\" -c \"${n}:ROOT\" \"$DISK\"; ROOT_N=\"$n\"; fi",
            "partprobe \"$DISK\" || true; udevadm settle",
            "pp() { case $DISK in *nvme[0-9]*n[0-9]*|*mmcblk[0-9]*) printf \"%sp%s\" \"$DISK\" \"$1\" ;; *) printf \"%s%s\" \"$DISK\" \"$1\" ;; esac; }",
            "mkdir -p /run/sinergia-auto",
            "pp \"$ROOT_N\" > /run/sinergia-auto/root_dev",
            "[ -n \"$EFI_N\" ] && pp \"$EFI_N\" > /run/sinergia-auto/efi_dev || : > /run/sinergia-auto/efi_dev",
            "[ -n \"$SWAP_N\" ] && pp \"$SWAP_N\" > /run/sinergia-auto/swap_dev || : > /run/sinergia-auto/swap_dev",
            "[ -n \"$HOME_N\" ] && pp \"$HOME_N\" > /run/sinergia-auto/home_dev || : > /run/sinergia-auto/home_dev",
        ]
        return chr(10).join(parts) + chr(10)
    def build_plan(self, config: InstallConfig) -> list[tuple[str, list[str]]]:
        pr = config.partitions
        plan: list[tuple[str, list[str]]] = []
        is_auto = pr.mode == "auto" and bool(pr.target_disk)
        fs = (pr.root_fs or "ext4").lower()
        nl = chr(10)
        if is_auto:
            plan.append((f"Particionar automáticamente {pr.target_disk} (GPT)", ["bash", "-c", self._auto_partition_script(config)]))
            prep_parts = [
                "set -euo pipefail",
                'ROOT_DEV="$(cat /run/sinergia-auto/root_dev)"',
                'EFI_DEV="$(cat /run/sinergia-auto/efi_dev)"',
                'HOME_DEV="$(cat /run/sinergia-auto/home_dev)"',
                'SWAP_DEV="$(cat /run/sinergia-auto/swap_dev)"',
                f'FS="{fs}"',
                'if [ "$FS" = "btrfs" ]; then',
                '  mkfs.btrfs -f "$ROOT_DEV"',
                '  if [ -z "$HOME_DEV" ]; then',
                '    mkdir -p /mnt_btrfs && mount -o subvolid=5 "$ROOT_DEV" /mnt_btrfs',
                '    btrfs subvolume create /mnt_btrfs/@ && btrfs subvolume create /mnt_btrfs/@home',
                '    umount /mnt_btrfs && rmdir /mnt_btrfs && mkdir -p /mnt',
                '    mount -o subvol=@,compress=zstd:1,noatime "$ROOT_DEV" /mnt',
                '    mkdir -p /mnt/home && mount -o subvol=@home,compress=zstd:1,noatime "$ROOT_DEV" /mnt/home',
                '  else',
                '    mkdir -p /mnt && mount -o compress=zstd:1,noatime "$ROOT_DEV" /mnt',
                '  fi',
                'else',
                '  mkfs.ext4 -F "$ROOT_DEV" && mkdir -p /mnt && mount "$ROOT_DEV" /mnt',
                'fi',
                'if [ -n "$EFI_DEV" ]; then mkdir -p /mnt/boot/efi && mkfs.fat -F32 "$EFI_DEV" && udevadm settle && mount -t vfat "$EFI_DEV" /mnt/boot/efi; fi',
                'if [ -n "$HOME_DEV" ]; then mkdir -p /mnt/home; if [ "$FS" = "btrfs" ]; then mkfs.btrfs -f "$HOME_DEV" && mount -o compress=zstd:1,noatime "$HOME_DEV" /mnt/home; else mkfs.ext4 -F "$HOME_DEV" && mount "$HOME_DEV" /mnt/home; fi; fi',
                'if [ -n "$SWAP_DEV" ]; then mkswap -f "$SWAP_DEV" && swapon "$SWAP_DEV"; fi',
            ]
            plan.append((f"Formatear y montar particiones ({fs.upper()}) en /mnt", ["bash", "-c", nl.join(prep_parts) + nl]))
        else:
            if pr.format_root and pr.root_device:
                plan.append((f"Formatear raíz ({pr.root_device}) como {fs.upper()}", ["bash", "-c", _format_fs_script(pr.root_device, fs)]))
            if fs == "btrfs" and pr.format_root and pr.root_device and not pr.home_device:
                b_parts = [
                    "set -euo pipefail",
                    f'mkdir -p /mnt_btrfs && mount -o subvolid=5 "{pr.root_device}" /mnt_btrfs',
                    "btrfs subvolume create /mnt_btrfs/@ && btrfs subvolume create /mnt_btrfs/@home",
                    f'umount /mnt_btrfs && rmdir /mnt_btrfs && mkdir -p /mnt && mount -o subvol=@,compress=zstd:1,noatime "{pr.root_device}" /mnt',
                    f'mkdir -p /mnt/home && mount -o subvol=@home,compress=zstd:1,noatime "{pr.root_device}" /mnt/home',
                ]
                plan.append((f"Crear subvolúmenes BTRFS (@ y @home) en {pr.root_device}", ["bash", "-c", nl.join(b_parts) + nl]))
            else:
                m_opts = ["-o", "subvol=@,compress=zstd:1,noatime"] if fs == "btrfs" else []
                plan.append((f"Montar raíz {pr.root_device} en /mnt", ["mount", *m_opts, pr.root_device, "/mnt"]))
            if pr.is_uefi and pr.efi_device:
                plan.append(("Crear /mnt/boot/efi", ["mkdir", "-p", "/mnt/boot/efi"]))
                if pr.format_efi:
                    plan.append((f"Formatear EFI ({pr.efi_device}) en FAT32", ["mkfs.fat", "-F32", pr.efi_device]))
                plan.append((f"Montar EFI {pr.efi_device} en /mnt/boot/efi", ["mount", "-t", "vfat", pr.efi_device, "/mnt/boot/efi"]))
            if pr.home_device:
                plan.append(("Crear /mnt/home", ["mkdir", "-p", "/mnt/home"]))
                if pr.format_home:
                    plan.append((f"Formatear /home ({pr.home_device}) como {fs.upper()}", ["bash", "-c", _format_fs_script(pr.home_device, fs)]))
                h_opts = ["-o", "compress=zstd:1,noatime"] if fs == "btrfs" else []
                plan.append((f"Montar /home {pr.home_device} en /mnt/home", ["bash", "-c", f"set -e; printf %s aW1wb3J0IHN1YnByb2Nlc3MsIHN5cwpkZXYgPSBzeXMuYXJndlsxXQpvcHRzID0gc3lzLmFyZ3ZbMjpdCmZzdCA9IHN1YnByb2Nlc3MucnVuKFsiYmxraWQiLCAiLXMiLCAiVFlQRSIsICItbyIsICJ2YWx1ZSIsIGRldl0sIGNhcHR1cmVfb3V0cHV0PVRydWUsIHRleHQ9VHJ1ZSkuc3Rkb3V0LnN0cmlwKCkKaWYgZnN0ID09ICJzd2FwIjoKICAgIHByaW50KGYiU2FsdGFuZG8gbW9udGFqZSBlbiAvbW50L2hvbWU6IHtkZXZ9IGVzIHN3YXAiKQogICAgc3lzLmV4aXQoMCkKc3VicHJvY2Vzcy5ydW4oWyJtb3VudCIsICpvcHRzLCBkZXYsICIvbW50L2hvbWUiXSwgY2hlY2s9VHJ1ZSkK | base64 -d | python3 - '{pr.home_device}'" + ("".join(f" '{o}'" for o in h_opts))]))
            swap_dev = (getattr(pr, "swap_device", "") or "").strip()
            if swap_dev:
                if bool(getattr(pr, "format_swap", True)):
                    plan.append((f"Formatear swap ({swap_dev})", ["mkswap", "-f", swap_dev]))
                plan.append((f"Activar swap ({swap_dev})", ["swapon", swap_dev]))
        sfs_cmd = "set -e; SFS=/run/archiso/bootmnt/arch/x86_64/airootfs.sfs; [ -f \"$SFS\" ] || SFS=$(find /run/archiso -name airootfs.sfs 2>/dev/null | head -n 1); if [ -n \"$SFS\" ] && [ -f \"$SFS\" ]; then unsquashfs -f -d /mnt \"$SFS\"; else rsync -aAX --exclude=/dev/* --exclude=/proc/* --exclude=/sys/* --exclude=/tmp/* --exclude=/run/* --exclude=/mnt/* --exclude=/media/* --exclude=/var/tmp/* --exclude=/var/cache/pacman/pkg/* --exclude=/lost+found / /mnt/; fi"
        krn_cmd = "set -e; KRN=/run/archiso/bootmnt/arch/boot/x86_64/vmlinuz-linux; [ -f \"$KRN\" ] || KRN=$(find /run/archiso -name 'vmlinuz*' 2>/dev/null | head -n 1); [ -f \"$KRN\" ] || [ ! -f /boot/vmlinuz-linux ] || KRN=/boot/vmlinuz-linux; mkdir -p /mnt/boot && cp \"$KRN\" /mnt/boot/vmlinuz-linux"
        fstab_cmd = 'set -e; printf %s aW1wb3J0IG9zLCBzdWJwcm9jZXNzCgpvcy5tYWtlZGlycygiL21udC9ldGMiLCBleGlzdF9vaz1UcnVlKQpvdXQgPSAiIgp0cnk6CiAgICByID0gc3VicHJvY2Vzcy5ydW4oWyJnZW5mc3RhYiIsICItVSIsICIvbW50Il0sIGNhcHR1cmVfb3V0cHV0PVRydWUsIHRleHQ9VHJ1ZSwgY2hlY2s9VHJ1ZSkKICAgIG91dCA9IHIuc3Rkb3V0CmV4Y2VwdCBFeGNlcHRpb246CiAgICByID0gc3VicHJvY2Vzcy5ydW4oWyJmaW5kbW50IiwgIi1ybiIsICItbyIsICJUQVJHRVQsU09VUkNFLEZTVFlQRSxPUFRJT05TIl0sIGNhcHR1cmVfb3V0cHV0PVRydWUsIHRleHQ9VHJ1ZSwgY2hlY2s9VHJ1ZSkKICAgIHJvd3MgPSBbXQogICAgZm9yIGxpbmUgaW4gci5zdGRvdXQuc3BsaXRsaW5lcygpOgogICAgICAgIHBhcnRzID0gbGluZS5zcGxpdChOb25lLCAzKQogICAgICAgIGlmIGxlbihwYXJ0cykgPCAzOgogICAgICAgICAgICBjb250aW51ZQogICAgICAgIHRndCwgc3JjLCBmc3QgPSBwYXJ0c1swXSwgcGFydHNbMV0sIHBhcnRzWzJdCiAgICAgICAgb3B0cyA9IHBhcnRzWzNdIGlmIGxlbihwYXJ0cykgPiAzIGVsc2UgImRlZmF1bHRzIgogICAgICAgIGlmIHRndCA9PSAiL21udCIgb3IgdGd0LnN0YXJ0c3dpdGgoIi9tbnQvIik6CiAgICAgICAgICAgIHJlbCA9IHRndFs0Ol0gb3IgIi8iCiAgICAgICAgICAgIG9wdHNfY2xlYW4gPSAiLCIuam9pbih4IGZvciB4IGluIG9wdHMuc3BsaXQoIiwiKSBpZiBub3QgeC5zdGFydHN3aXRoKCJzdWJ2b2w9IikpIG9yICJkZWZhdWx0cyIKICAgICAgICAgICAgcm93cy5hcHBlbmQoZiJ7c3JjfVx0e3JlbH1cdHtmc3R9XHR7b3B0c19jbGVhbn1cdDBcdDAiKQogICAgb3V0ID0gIlxuIi5qb2luKHJvd3MpICsgKCJcbiIgaWYgcm93cyBlbHNlICIiKQoKYXNzZXJ0IG91dC5zdHJpcCgpLCAiZnN0YWIgdmFjaW8iCgpmb3IgZCBpbiBzdWJwcm9jZXNzLnJ1bihbImJsa2lkIiwgIi10IiwgIlRZUEU9c3dhcCIsICItbyIsICJkZXZpY2UiXSwgY2FwdHVyZV9vdXRwdXQ9VHJ1ZSwgdGV4dD1UcnVlKS5zdGRvdXQuc3BsaXRsaW5lcygpOgogICAgZCA9IGQuc3RyaXAoKQogICAgaWYgbm90IGQ6CiAgICAgICAgY29udGludWUKICAgIHUgPSBzdWJwcm9jZXNzLnJ1bihbImJsa2lkIiwgIi1zIiwgIlVVSUQiLCAiLW8iLCAidmFsdWUiLCBkXSwgY2FwdHVyZV9vdXRwdXQ9VHJ1ZSwgdGV4dD1UcnVlKS5zdGRvdXQuc3RyaXAoKQogICAgaWYgdSBhbmQgZiJVVUlEPXt1fSIgbm90IGluIG91dDoKICAgICAgICBvdXQgKz0gZiJVVUlEPXt1fVx0bm9uZVx0c3dhcFx0ZGVmYXVsdHNcdDBcdDBcbiIKCndpdGggb3BlbigiL21udC9ldGMvZnN0YWIiLCAidyIsIGVuY29kaW5nPSJ1dGYtOCIpIGFzIGY6CiAgICBmLndyaXRlKG91dCkK | base64 -d | python3 -'
        ml_cmd = 'python3 -c \'from pathlib import Path; p=Path("/mnt/etc/pacman.conf"); t=p.read_text(); nl=chr(10); p.write_text(t.replace("#[multilib]"+nl+"#Include = /etc/pacman.d/mirrorlist", "[multilib]"+nl+"Include = /etc/pacman.d/mirrorlist")) if "#[multilib]" in t else None\' && arch-chroot /mnt pacman -Sy --noconfirm'
        plan.append(("Desplegar sistema base en /mnt", ["bash", "-c", sfs_cmd]))
        plan.append(("Copiar kernel vmlinuz-linux a /mnt/boot", ["bash", "-c", krn_cmd]))
        plan.append(("Generar /mnt/etc/fstab", ["bash", "-c", fstab_cmd]))
        plan.append(("Habilitar repositorio [multilib] en /mnt/etc/pacman.conf", ["bash", "-c", ml_cmd]))
        plan.append(("Asignar permisos de ejecución al script de post-instalación", ["chmod", "0755", "/mnt/usr/local/bin/sinergia-post-install.sh"]))
        env_vars = [f"{k}={v}" for k, v in build_chroot_env(config).items()]
        plan.append(("Configurar zona horaria, usuario y bootloader en /mnt", ["arch-chroot", "/mnt", "env", *env_vars, "bash", "/usr/local/bin/sinergia-post-install.sh"]))
        plan.append(("Sincronizar escrituras en disco", ["sync"]))
        plan.append(("Desmontar /mnt limpiamente", ["umount", "-R", "/mnt"]))
        return plan
    def _run_next_real_step(self) -> None:
        if self._cancelled:
            self.finished_install.emit(False, "Instalación cancelada.")
            return
        total = len(self._steps)
        if self._current_index >= total:
            self.finished_install.emit(True, "Instalación completada.")
            return
        label, cmd = self._steps[self._current_index]
        self.step_changed.emit(self._current_index + 1, total, label)
        self.log_line.emit(f"==> {label}")
        self.log_line.emit(f"$ {_format_cmd_for_log(cmd)}")
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        qenv = QProcessEnvironment.systemEnvironment()
        if cmd[0] == "arch-chroot" and self._active_config is not None:
            for k, v in build_chroot_env(self._active_config).items():
                qenv.insert(k, v)
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
