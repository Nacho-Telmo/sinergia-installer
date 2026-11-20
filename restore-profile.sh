#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAPSHOT_DIR="${REPO_DIR}/iso-profile-snapshot"
BASE_PROFILE="/usr/share/archiso/configs/releng"
TARGET_DIR="${1:-${TARGET_DIR:-/var/tmp/sinergia-iso/profile}}"
AIROOTFS_DIR="${TARGET_DIR}/airootfs"

log() {
    printf '[restore-profile] %s\n' "$*"
}

die() {
    printf '[restore-profile][ERROR] %s\n' "$*" >&2
    exit 1
}

[[ -d "${SNAPSHOT_DIR}" ]] || die "No se encontró el directorio snapshot: ${SNAPSHOT_DIR}"
[[ -d "${BASE_PROFILE}" ]] || die "No se encontró el perfil base archiso: ${BASE_PROFILE}"
command -v rsync >/dev/null 2>&1 || die "Se requiere 'rsync' instalado en el sistema."

if [[ "${EUID}" -ne 0 ]]; then
    die "Ejecutá este script con privilegios de root (ejemplo: sudo ${0} ${TARGET_DIR})."
fi

log "Preparando directorio de perfil en: ${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
rsync -a --delete "${BASE_PROFILE}/" "${TARGET_DIR}/"

log "Aplicando snapshot del perfil de Sinergia Linux..."
[[ -f "${SNAPSHOT_DIR}/packages.x86_64" ]] && install -m 0644 "${SNAPSHOT_DIR}/packages.x86_64" "${TARGET_DIR}/packages.x86_64"
[[ -f "${SNAPSHOT_DIR}/pacman.conf" ]] && install -m 0644 "${SNAPSHOT_DIR}/pacman.conf" "${TARGET_DIR}/pacman.conf"
[[ -f "${SNAPSHOT_DIR}/profiledef.sh" ]] && install -m 0644 "${SNAPSHOT_DIR}/profiledef.sh" "${TARGET_DIR}/profiledef.sh"
[[ -f "${SNAPSHOT_DIR}/chaotic-mirrorlist" ]] && install -m 0644 "${SNAPSHOT_DIR}/chaotic-mirrorlist" "${AIROOTFS_DIR}/etc/pacman.d/chaotic-mirrorlist"

if [[ -f "${SNAPSHOT_DIR}/sinergia-post-install.sh" ]]; then
    install -d -m 0755 "${AIROOTFS_DIR}/usr/local/bin"
    install -m 0755 "${SNAPSHOT_DIR}/sinergia-post-install.sh" "${AIROOTFS_DIR}/usr/local/bin/sinergia-post-install.sh"
fi

if [[ -f "${SNAPSHOT_DIR}/sinergia-repo.asc" ]]; then
    install -d -m 0755 "${AIROOTFS_DIR}/etc/pacman.d/gnupg"
    install -m 0644 "${SNAPSHOT_DIR}/sinergia-repo.asc" "${AIROOTFS_DIR}/etc/pacman.d/sinergia-repo.asc"
fi

if [[ -d "${SNAPSHOT_DIR}/boot-configs" ]]; then
    if [[ -d "${SNAPSHOT_DIR}/boot-configs/efiboot" ]]; then
        rsync -a "${SNAPSHOT_DIR}/boot-configs/efiboot/" "${TARGET_DIR}/efiboot/"
    fi
    if [[ -d "${SNAPSHOT_DIR}/boot-configs/grub" ]]; then
        rsync -a "${SNAPSHOT_DIR}/boot-configs/grub/" "${TARGET_DIR}/grub/"
    fi
    if [[ -d "${SNAPSHOT_DIR}/boot-configs/syslinux" ]]; then
        rsync -a "${SNAPSHOT_DIR}/boot-configs/syslinux/" "${TARGET_DIR}/syslinux/"
    fi
fi

if [[ -d "${SNAPSHOT_DIR}/etc-live" ]]; then
    install -d -m 0755 "${AIROOTFS_DIR}/etc"
    for cfg in passwd group hostname motd; do
        [[ -f "${SNAPSHOT_DIR}/etc-live/${cfg}" ]] && install -m 0644 "${SNAPSHOT_DIR}/etc-live/${cfg}" "${AIROOTFS_DIR}/etc/${cfg}"
    done
    if [[ -f "${SNAPSHOT_DIR}/etc-live/live-nopasswd" ]]; then
        install -d -m 0750 "${AIROOTFS_DIR}/etc/sudoers.d"
        install -m 0440 "${SNAPSHOT_DIR}/etc-live/live-nopasswd" "${AIROOTFS_DIR}/etc/sudoers.d/live-nopasswd"
    fi
fi

[[ -f "${SNAPSHOT_DIR}/locale.conf" ]] && install -m 0644 "${SNAPSHOT_DIR}/locale.conf" "${AIROOTFS_DIR}/etc/locale.conf"

if [[ -f "${SNAPSHOT_DIR}/autologin.conf" ]]; then
    install -d -m 0755 "${AIROOTFS_DIR}/etc/systemd/system/getty@tty1.service.d"
    install -m 0644 "${SNAPSHOT_DIR}/autologin.conf" "${AIROOTFS_DIR}/etc/systemd/system/getty@tty1.service.d/autologin.conf"
fi

log "Copiando sinergia-installer a ${AIROOTFS_DIR}/opt/sinergia-installer..."
INSTALLER_DEST="${AIROOTFS_DIR}/opt/sinergia-installer"
rm -rf "${INSTALLER_DEST}"
mkdir -p "${INSTALLER_DEST}"
rsync -a \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='iso-profile-snapshot/' \
    --exclude='restore-profile.sh' \
    "${REPO_DIR}/main.py" \
    "${REPO_DIR}/pyproject.toml" \
    "${REPO_DIR}/README.md" \
    "${REPO_DIR}/LICENSE" \
    "${REPO_DIR}/sinergia_installer" \
    "${INSTALLER_DEST}/"

log "Listo. Perfil restaurado en ${TARGET_DIR}."
