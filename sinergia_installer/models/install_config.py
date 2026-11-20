from dataclasses import dataclass, field


@dataclass
class PartitionAssignment:
    root_device: str = ""
    format_root: bool = True
    root_fs: str = "ext4"
    efi_device: str = ""
    format_efi: bool = False
    home_device: str = ""
    format_home: bool = False
    is_uefi: bool = True


@dataclass
class InstallConfig:
    locale: str = "es_AR.UTF-8"
    keymap: str = "us"
    timezone: str = "America/Argentina/Buenos_Aires"
    hostname: str = "sinergia-arch"
    full_name: str = ""
    username: str = ""
    password: str = ""
    same_password_for_root: bool = True
    root_password: str = ""
    sudo_nopasswd: bool = False
    partitions: PartitionAssignment = field(default_factory=PartitionAssignment)
    dry_run: bool = False
