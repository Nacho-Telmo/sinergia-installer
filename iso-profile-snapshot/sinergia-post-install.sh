#!/usr/bin/env bash
set -euo pipefail

LOCALE="${LOCALE:-es_AR.UTF-8}"
KEYMAP="${KEYMAP:-es}"
TIMEZONE="${TIMEZONE:-America/Argentina/Buenos_Aires}"
HOSTNAME="${HOSTNAME:-sinergia-linux}"
USERNAME="${USERNAME:-usuario}"
FULL_NAME="${FULL_NAME:-$USERNAME}"
PASSWORD="${PASSWORD:-}"
ROOT_PASSWORD="${ROOT_PASSWORD:-$PASSWORD}"
SUDO_NOPASSWD="${SUDO_NOPASSWD:-0}"
IS_UEFI="${IS_UEFI:-1}"

echo "==> [1/7] Limpiando artefactos del entorno Live..."
if id "live" &>/dev/null; then
    userdel -r live 2>/dev/null || rm -rf /home/live
fi
rm -f /etc/sudoers.d/live-nopasswd
rm -f /etc/sddm.conf.d/autologin.conf

systemctl disable choose-mirror.service livecd-alsa-unmuter.service livecd-talk.service pacman-init.service 2>/dev/null || true
rm -f /etc/systemd/system/choose-mirror.service \
      /etc/systemd/system/livecd-alsa-unmuter.service \
      /etc/systemd/system/livecd-talk.service \
      /etc/systemd/system/pacman-init.service \
      /etc/systemd/system/etc-pacman.d-gnupg.mount
rm -f /usr/local/bin/choose-mirror /usr/local/bin/Installation_guide /usr/local/bin/livecd-sound
rm -rf /usr/local/share/livecd-sound
rm -f /root/.automated_script.sh /root/.zlogin

rm -rf /opt/sinergia-installer
rm -f /usr/share/applications/sinergia-installer.desktop
rm -f /usr/local/bin/sinergia-installer

echo "==> [2/7] Configurando zona horaria (${TIMEZONE}) y reloj..."
ln -sf "/usr/share/zoneinfo/${TIMEZONE}" /etc/localtime
hwclock --systohc || true

echo "==> [3/7] Configurando locale (${LOCALE}) y teclado (${KEYMAP})..."
sed -i "s/^#${LOCALE}/${LOCALE}/" /etc/locale.gen
grep -q "^${LOCALE}" /etc/locale.gen || echo "${LOCALE} UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=${LOCALE}" >| /etc/locale.conf
echo "KEYMAP=${KEYMAP}" >| /etc/vconsole.conf

echo "==> [4/7] Configurando hostname (${HOSTNAME})..."
echo "${HOSTNAME}" >| /etc/hostname
cat >| /etc/hosts <<HOSTS
127.0.0.1   localhost
::1         localhost
127.0.1.1   ${HOSTNAME}.localdomain ${HOSTNAME}
HOSTS

echo "==> [5/7] Creando usuario (${USERNAME}) y configurando contraseñas..."
if [[ -n "${ROOT_PASSWORD}" ]]; then
    echo "root:${ROOT_PASSWORD}" | chpasswd
fi

if ! id "${USERNAME}" &>/dev/null; then
    useradd -m -G wheel,audio,video,storage,optical,network -s /bin/bash -c "${FULL_NAME}" "${USERNAME}"
fi

if [[ -n "${PASSWORD}" ]]; then
    echo "${USERNAME}:${PASSWORD}" | chpasswd
fi

mkdir -p /etc/sudoers.d
chmod 0750 /etc/sudoers.d
if [[ "${SUDO_NOPASSWD}" == "1" ]]; then
    echo "%wheel ALL=(ALL:ALL) NOPASSWD: ALL" >| /etc/sudoers.d/10-wheel
else
    echo "%wheel ALL=(ALL:ALL) ALL" >| /etc/sudoers.d/10-wheel
fi
chmod 0440 /etc/sudoers.d/10-wheel

echo "==> [6/7] Habilitando servicios del sistema (NetworkManager y SDDM)..."
systemctl enable NetworkManager.service
systemctl enable sddm.service

echo "==> [7/7] Regenerando initramfs e instalando GRUB..."
echo "==> Inicializando keyring de pacman y claves de repositorios..."
rm -rf /etc/pacman.d/gnupg
pacman-key --init
pacman-key --populate archlinux

# Clave y keyring de sinergia-repo (con fallback a keyservers y descarga directa)
SINERGIA_KEY="33986859CBA9A0329EE9321E1AA165CC95EBE1F1"
if [[ -s /etc/pacman.d/sinergia-repo.asc ]]; then
    pacman-key --add /etc/pacman.d/sinergia-repo.asc || true
fi
SINERGIA_KEY_TMP="/tmp/sinergia-repo.asc"
rm -f "${SINERGIA_KEY_TMP}"

for ks in "hkps://keyserver.ubuntu.com" "hkps://keys.openpgp.org" "hkps://pgp.mit.edu"; do
    if pacman-key --keyserver "${ks}" --recv-keys "${SINERGIA_KEY}" >/dev/null 2>&1; then
        break
    fi
done

if ! pacman-key --list-keys "${SINERGIA_KEY}" >/dev/null 2>&1; then
    for url in \
        "https://nacho-telmo.github.io/sinergia-repo/x86_64/sinergia-repo.asc" \
        "https://nacho-telmo.github.io/sinergia-repo/sinergia-repo.asc" \
        "https://nacho-telmo.github.io/sinergia-repo/x86_64/sinergia.gpg"; do
        if curl -fsSL "${url}" -o "${SINERGIA_KEY_TMP}" 2>/dev/null && [[ -s "${SINERGIA_KEY_TMP}" ]]; then
            pacman-key --add "${SINERGIA_KEY_TMP}" || true
            break
        fi
    done
    rm -f "${SINERGIA_KEY_TMP}"
fi

pacman-key --lsign-key "${SINERGIA_KEY}" || true

# Clave, mirrorlist y keyring de chaotic-aur
if [[ ! -f /etc/pacman.d/chaotic-mirrorlist ]]; then
    cat >| /etc/pacman.d/chaotic-mirrorlist <<'EOF_CHAOTIC_MIRROR'
Server = https://geo-mirror.chaotic.cx/$repo/$arch
Server = https://cdn-mirror.chaotic.cx/$repo/$arch
EOF_CHAOTIC_MIRROR
fi
pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com || \
    pacman-key --recv-key 3056513887B78AEB || true
pacman-key --lsign-key 3056513887B78AEB || true

pacman -Sy --noconfirm || true
pacman -U --noconfirm https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst || true
pacman-key --populate chaotic || true
# Asegurar repositorios [chaotic-aur] y [sinergia-repo] en /etc/pacman.conf
if ! grep -q '^\[chaotic-aur\]' /etc/pacman.conf; then
    cat >> /etc/pacman.conf <<'EOF_CHAOTIC_CONF'

[chaotic-aur]
Include = /etc/pacman.d/chaotic-mirrorlist
EOF_CHAOTIC_CONF
fi

if ! grep -q '^\[sinergia-repo\]' /etc/pacman.conf; then
    cat >> /etc/pacman.conf <<'EOF_SINERGIA_CONF'

[sinergia-repo]
SigLevel = Required DatabaseOptional
Server = https://nacho-telmo.github.io/sinergia-repo/$arch
EOF_SINERGIA_CONF
fi

pacman -Sy --noconfirm sinergia-keyring || true

# Configurar mapa de teclado en español para consola, X11 y Wayland/KDE
KEYMAP="${KEYMAP:-es}"
printf 'KEYMAP=%s\n' "${KEYMAP}" >| /etc/vconsole.conf
if command -v localectl >/dev/null 2>&1; then
    localectl set-x11-keymap "${KEYMAP}" || true
fi
if [[ ! -f /etc/X11/xorg.conf.d/00-keyboard.conf ]]; then
    mkdir -p /etc/X11/xorg.conf.d
    cat >| /etc/X11/xorg.conf.d/00-keyboard.conf <<EOF_X11_KB
Section "InputClass"
        Identifier "system-keyboard"
        MatchIsKeyboard "on"
        Option "XkbLayout" "${KEYMAP}"
EndSection
EOF_X11_KB
fi

rm -f /etc/mkinitcpio.conf.d/archiso.conf
if pacman -Qi mkinitcpio-archiso >/dev/null 2>&1; then
    pacman -Rdd --noconfirm mkinitcpio-archiso
fi
mkinitcpio -P

if [[ -f /etc/default/grub ]]; then
    sed -i 's/^GRUB_DISTRIBUTOR=.*/GRUB_DISTRIBUTOR="SinergiaLinux"/' /etc/default/grub
    sed -i 's/^GRUB_DISABLE_LINUX_UUID=true/#GRUB_DISABLE_LINUX_UUID=true/' /etc/default/grub
fi

if ! grep -qE '[[:space:]]/[[:space:]]' /etc/fstab; then
    ROOT_SRC=$(findmnt -n -o SOURCE / || true)
    if [[ -n "${ROOT_SRC}" ]]; then
        genfstab -U / >> /etc/fstab
    fi
fi

if [[ "${IS_UEFI}" == "1" ]]; then
    grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=SinergiaLinux --removable --recheck
else
    ROOT_PART=$(findmnt -n -o SOURCE /)
    ROOT_DISK=$(lsblk -no PKNAME "${ROOT_PART}" | head -n1)
    grub-install --target=i386-pc "/dev/${ROOT_DISK}" --recheck
fi

grub-mkconfig -o /boot/grub/grub.cfg

ROOT_UUID=""
if [[ -f /etc/fstab ]]; then
    ROOT_UUID=$(awk '$2 == "/" {print $1}' /etc/fstab | sed -n 's/^UUID=//p' | head -n1)
fi
if [[ -z "${ROOT_UUID}" ]]; then
    ROOT_UUID=$(findmnt -n -o UUID / 2>/dev/null || true)
fi
ROOT_DEV=$(findmnt -n -o SOURCE / 2>/dev/null || true)
if [[ -z "${ROOT_UUID}" && -n "${ROOT_DEV}" && -b "${ROOT_DEV}" ]]; then
    ROOT_UUID=$(blkid -s UUID -o value "${ROOT_DEV}" 2>/dev/null || true)
fi

if [[ -n "${ROOT_UUID}" ]]; then
    TARGET_ROOT="UUID=${ROOT_UUID}"
elif [[ -n "${ROOT_DEV}" && -b "${ROOT_DEV}" ]]; then
    TARGET_ROOT="${ROOT_DEV}"
else
    TARGET_ROOT=""
fi

if [[ -n "${TARGET_ROOT}" && -f /boot/grub/grub.cfg ]]; then
    python3 - "${TARGET_ROOT}" <<'FIX_GRUB'
import re
import sys
from pathlib import Path

target_root = sys.argv[1]
cfg_path = Path("/boot/grub/grub.cfg")
lines = cfg_path.read_text(encoding="utf-8").splitlines(keepends=True)

updated = []
for line in lines:
    if re.match(r"^[ 	]*(linux|linuxefi)[ 	]+", line):
        line = re.sub(r"\broot=[^ \t]*", f"root={target_root}", line)
    updated.append(line)

cfg_path.write_text("".join(updated), encoding="utf-8")
FIX_GRUB
fi
# Identidad de Sinergia Linux en /etc/os-release y logo global de fastfetch
echo "==> Configurando identidad de Sinergia Linux y logo de fastfetch..."
install -d -m 0755 /usr/local/share/sinergia /usr/share/sinergia /etc/pacman.d/hooks /etc/xdg/fastfetch

rm -f /etc/os-release
cat <<'EOS' > /usr/local/share/sinergia/os-release
NAME="Sinergia Linux"
PRETTY_NAME="Sinergia Linux"
ID=sinergia
ID_LIKE=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;0;229;255"
HOME_URL="https://github.com/Nacho-Telmo"
DOCUMENTATION_URL="https://github.com/Nacho-Telmo"
SUPPORT_URL="https://github.com/Nacho-Telmo"
BUG_REPORT_URL="https://github.com/Nacho-Telmo"
LOGO=sinergia-installer
EOS
install -m 0644 /usr/local/share/sinergia/os-release /etc/os-release

cat <<'EOS' > /etc/pacman.d/hooks/99-sinergia-os-release.hook
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = filesystem

[Action]
Description = Restaurando identidad de Sinergia Linux en /etc/os-release...
When = PostTransaction
Exec = /usr/bin/install -m 0644 /usr/local/share/sinergia/os-release /etc/os-release
EOS

cat <<'EOS' > /usr/share/sinergia/fastfetch-logo.txt
⠀⠀⡀⠀⢀⡄⠀⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⢰⢺⡄⢠⡇⢀⡾⣇⢀⡿⣆⣠⡞⠀⢀⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣀⡀⠸⡆⢸⠀⢿⣟⢀⣾⢃⢹⣾⠀⢻⣏⣤⠾⢻⣠⢞⣤⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⢺⣬⠙⡟⠷⣾⣦⣌⣿⣾⠷⣼⡄⢿⣤⣶⢿⡅⣠⡞⢡⡾⠁⣠⠇⠀⠀⠀⠀⠀
⠀⠀⠰⣄⠀⣙⢷⣿⡀⣿⡏⠙⣿⣿⡄⠙⣧⣾⡟⣡⡼⣿⡉⣰⣿⠷⣶⠿⠶⠶⢆⡀⠀⠀
⠀⠰⠶⠾⢷⣍⠉⠻⣷⣽⡇⣸⡿⢿⣧⢀⣨⣿⠟⠋⠀⢿⣿⡿⠴⣰⠿⠒⣠⠞⢉⣡⠀⠀
⣠⠶⠶⠶⠶⣿⡿⠿⠿⠿⣿⣿⡃⢸⣿⣿⠟⣿⡀⠀⣠⣿⣏⣀⣼⣯⣤⣼⣷⣞⢋⡥⠀⠀
⠈⠛⠦⣄⣾⠋⠠⠤⢤⣤⣾⣿⣿⣾⣿⣧⡀⣿⣇⣴⣿⠟⢛⣿⠟⠻⣍⠀⠈⣉⣉⣭⠽⠆
⠀⢀⡴⠛⢙⣻⠷⣶⡾⠛⠁⠀⠻⣿⣿⣿⣷⣝⢿⡿⠃⣠⣾⣯⣤⣶⠶⠿⢿⣍⣁⣀⣀⠀
⠈⠉⠀⠈⠉⠡⠞⠋⠀⠀⠀⠀⠀⠈⠻⣿⣿⣿⣷⣭⡻⠟⠛⠉⠙⢧⠀⠀⠀⠙⢦⡀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠻⣿⣿⣿⣿⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣿⣿⣿⣿⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⢿⣿⣿⣿⡆⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⢸⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⣤⣤⣤⣤⣄⣀⣤⣴⣾⣟⣼⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠘⠒⠒⠒⣿⠟⠉⣡⡾⠛⠉⠛⠛⣛⣻⣵⣿⣿⣿⣿⢻⣿⣿⡻⠶⠶⠋⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠉⠁⠔⠚⢩⠇⣠⣶⣿⡿⠿⠿⣻⣿⡿⠋⣹⣧⠈⢹⡿⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠠⢴⣾⡿⠋⢀⣤⠶⢾⡿⠃⠀⢸⠃⠸⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠊⠀⠀⠘⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
EOS

cat <<'EOS' > /etc/xdg/fastfetch/config.jsonc
{
  "$schema": "https://github.com/fastfetch-cli/fastfetch/raw/dev/doc/json_schema.json",
  "logo": {
    "type": "file",
    "source": "/usr/share/sinergia/fastfetch-logo.txt",
    "color": {
      "1": "cyan",
      "2": "blue"
    }
  },
  "modules": [
    "title",
    "separator",
    "os",
    "host",
    "kernel",
    "uptime",
    "packages",
    "shell",
    "display",
    "de",
    "wm",
    "wmtheme",
    "theme",
    "icons",
    "font",
    "cursor",
    "terminal",
    "terminalfont",
    "cpu",
    "gpu",
    "memory",
    "swap",
    "disk",
    "localip",
    "battery",
    "poweradapter",
    "locale",
    "break",
    "colors"
  ]
}
EOS

rm -f /usr/local/bin/sinergia-post-install.sh
echo "==> Post-instalación de SinergiaLinux completada correctamente."
