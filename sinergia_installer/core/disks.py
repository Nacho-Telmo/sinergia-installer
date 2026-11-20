import json
import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class PartitionInfo:
    name: str
    path: str
    size: str
    fstype: str
    mountpoint: str | None


def is_uefi_boot() -> bool:
    return os.path.exists("/sys/firmware/efi")


def has_partition_manager() -> bool:
    return shutil.which("partitionmanager") is not None


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
