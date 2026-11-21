import json
import os
import shutil
import subprocess
from dataclasses import dataclass


MIN_AUTO_DISK_BYTES = 16 * 1024**3
MIN_SEPARATE_HOME_DISK_BYTES = 32 * 1024**3
MIN_ROOT_GIB = 20
EFI_MIB = 512


@dataclass
class PartitionInfo:
    name: str
    path: str
    size: str
    fstype: str
    mountpoint: str | None


@dataclass
class PhysicalDiskInfo:
    name: str
    path: str
    size_bytes: int
    size_human: str
    model: str
    tran: str


def is_uefi_boot() -> bool:
    return os.path.exists("/sys/firmware/efi")


def has_partition_manager() -> bool:
    return shutil.which("partitionmanager") is not None


def _human_size(num_bytes: int) -> str:
    gib = num_bytes / (1024**3)
    if gib >= 1000:
        return f"{gib / 1024:.2f} TiB"
    return f"{gib:.1f} GiB"


def _protected_root_disks() -> set[str]:
    protected: set[str] = set()
    for mp in ("/run/archiso/bootmnt", "/"):
        if not os.path.exists(mp):
            continue
        try:
            src = subprocess.run(
                ["findmnt", "-n", "-o", "SOURCE", mp],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if not src or not src.startswith("/dev/"):
                continue
            pk = subprocess.run(
                ["lsblk", "-no", "PKNAME", src],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            for line in pk.splitlines():
                dev_name = line.strip()
                if dev_name:
                    protected.add(f"/dev/{dev_name}")
            base = os.path.basename(src)
            if base.startswith(("sd", "vd", "xvd")):
                protected.add(f"/dev/{base.rstrip('0123456789')}")
        except Exception:
            continue
    return protected


def list_physical_disks() -> list[PhysicalDiskInfo]:
    cmd = ["lsblk", "-J", "-b", "-d", "-o", "NAME,PATH,SIZE,MODEL,TRAN,TYPE,RO"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    protected = _protected_root_disks()

    disks: list[PhysicalDiskInfo] = []
    for dev in data.get("blockdevices", []):
        if dev.get("type") != "disk" or bool(dev.get("ro")):
            continue
        path = dev.get("path", "")
        if not path or path in protected:
            continue
        size_bytes = int(dev.get("size") or 0)
        if size_bytes < MIN_AUTO_DISK_BYTES:
            continue
        disks.append(
            PhysicalDiskInfo(
                name=dev.get("name", ""),
                path=path,
                size_bytes=size_bytes,
                size_human=_human_size(size_bytes),
                model=(dev.get("model") or "Disco").strip(),
                tran=(dev.get("tran") or "disco").strip().upper(),
            )
        )
    return disks


def list_partitions() -> list[PartitionInfo]:
    cmd = ["lsblk", "-J", "-o", "NAME,PATH,SIZE,FSTYPE,MOUNTPOINT,TYPE"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    result: list[PartitionInfo] = []

    def walk(devices: list[dict]) -> None:
        for dev in devices:
            if dev.get("type") == "part":
                result.append(
                    PartitionInfo(
                        name=dev.get("name", ""),
                        path=dev.get("path", ""),
                        size=dev.get("size", ""),
                        fstype=dev.get("fstype") or "sin formato",
                        mountpoint=dev.get("mountpoint"),
                    )
                )
            if "children" in dev:
                walk(dev["children"])

    walk(data.get("blockdevices", []))
    return result


def validate_assignments(
    root_dev: str,
    efi_dev: str,
    home_dev: str,
    uefi: bool,
    swap_dev: str = "",
) -> list[str]:
    errors: list[str] = []
    if not root_dev:
        errors.append("Debés seleccionar una partición para la raíz (/).")
    if uefi and not efi_dev:
        errors.append("El sistema arrancó en modo UEFI: seleccioná una partición EFI para /boot/efi.")
    chosen = [d for d in (root_dev, efi_dev, home_dev, swap_dev) if d]
    if len(chosen) != len(set(chosen)):
        errors.append("No podés asignar la misma partición a más de un punto de montaje.")
    return errors


def validate_auto_assignment(
    target_disk: str,
    disk_size_bytes: int,
    auto_swap: bool,
    auto_swap_gib: int,
    auto_separate_home: bool,
) -> list[str]:
    errors: list[str] = []
    if not target_disk:
        errors.append("Seleccioná un disco físico para el particionado automático.")
        return errors
    if target_disk in _protected_root_disks():
        errors.append(f"El disco {target_disk} está protegido porque contiene el medio de arranque actual.")
        return errors

    swap_bytes = (auto_swap_gib * 1024**3) if auto_swap else 0
    boot_bytes = EFI_MIB * 1024**2
    min_root_bytes = MIN_ROOT_GIB * 1024**3

    if auto_separate_home and disk_size_bytes < MIN_SEPARATE_HOME_DISK_BYTES:
        errors.append("Para separar /home en otra partición se recomienda un disco de al menos 32 GiB.")
    elif auto_separate_home and swap_bytes + boot_bytes + (min_root_bytes * 2) > disk_size_bytes:
        errors.append("El tamaño de swap o el disco no dejan espacio suficiente para / y /home separada.")
    elif not auto_separate_home and swap_bytes + boot_bytes + min_root_bytes > disk_size_bytes:
        errors.append("El tamaño de swap elegido supera el espacio disponible en el disco seleccionado.")
    return errors
