from dataclasses import dataclass, field


@dataclass
class PartitionAssignment:
    mode: str = "manual"  # "manual" | "auto"
    target_disk: str = ""
    auto_swap: bool = True
    auto_swap_gib: int = 4
    auto_separate_home: bool = False

    root_device: str = ""
    format_root: bool = True
    root_fs: str = "ext4"  # "ext4" | "btrfs"
    efi_device: str = ""
    format_efi: bool = False
    home_device: str = ""
    format_home: bool = False
    swap_device: str = ""
    format_swap: bool = True
    is_uefi: bool = True


@dataclass
class InstallConfig:
    locale: str = "es_AR.UTF-8"
    keymap: str = "us"
    timezone: str = "America/Argentina/Buenos_Aires"
    hostname: str = "sinergialinux"
    full_name: str = ""
    username: str = ""
    password: str = ""
    same_password_for_root: bool = True
    root_password: str = ""
    sudo_nopasswd: bool = False
    partitions: PartitionAssignment = field(default_factory=PartitionAssignment)
    dry_run: bool = False
