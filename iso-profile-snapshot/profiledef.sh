#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="SinergiaLinux"
iso_label="SINERGIA_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Sinergia Comunidad Linuxera <https://github.com/Nacho-Telmo>"
iso_application="Sinergia Linux Live/Install DVD"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="arch"
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-b' '1M' '-processors' '12')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
kernel_params_aarch64="clk_ignore_unused pd_ignore_unused arm64.nopauth"
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/local/bin/sinergia-post-install.sh"]="0:0:0755"
  ["/usr/local/bin/sinergia-installer"]="0:0:0755"
  ["/home/live/Desktop"]="1000:1000:0755"
  ["/home/live/Desktop/sinergia-installer.desktop"]="1000:1000:0755"
)
