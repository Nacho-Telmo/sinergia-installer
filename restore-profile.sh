#!/usr/bin/env bash
set -uo pipefail

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
    if [[ -f "${SNAPSHOT_DIR}/etc-live/shadow" ]]; then
        install -m 0400 "${SNAPSHOT_DIR}/etc-live/shadow" "${AIROOTFS_DIR}/etc/shadow"
    fi
    if [[ -f "${SNAPSHOT_DIR}/etc-live/live-nopasswd" ]]; then
        install -d -m 0750 "${AIROOTFS_DIR}/etc/sudoers.d"
        install -m 0440 "${SNAPSHOT_DIR}/etc-live/live-nopasswd" "${AIROOTFS_DIR}/etc/sudoers.d/live-nopasswd"
    fi
fi

install -d -m 0700 -o 1000 -g 1000 "${AIROOTFS_DIR}/home/live"

[[ -f "${SNAPSHOT_DIR}/locale.conf" ]] && install -m 0644 "${SNAPSHOT_DIR}/locale.conf" "${AIROOTFS_DIR}/etc/locale.conf"

if [[ -f "${SNAPSHOT_DIR}/autologin.conf" ]]; then
    install -d -m 0755 "${AIROOTFS_DIR}/etc/sddm.conf.d"
    install -m 0644 "${SNAPSHOT_DIR}/autologin.conf" "${AIROOTFS_DIR}/etc/sddm.conf.d/autologin.conf"
    rm -rf "${AIROOTFS_DIR}/etc/systemd/system/getty@tty1.service.d"
fi

log "Habilitando servicios gráficos y de red en airootfs (solo NetworkManager)..."
rm -f "${AIROOTFS_DIR}/etc/systemd/system/multi-user.target.wants/systemd-networkd.service" \
      "${AIROOTFS_DIR}/etc/systemd/system/network-online.target.wants/systemd-networkd-wait-online.service" \
      "${AIROOTFS_DIR}/etc/systemd/system/sockets.target.wants/systemd-networkd.socket" \
      "${AIROOTFS_DIR}/etc/systemd/system/dbus-org.freedesktop.network1.service"
rm -rf "${AIROOTFS_DIR}/etc/systemd/network"
install -d -m 0755 "${AIROOTFS_DIR}/etc/systemd/system/multi-user.target.wants"
ln -sf /usr/lib/systemd/system/sddm.service "${AIROOTFS_DIR}/etc/systemd/system/display-manager.service"
ln -sf /usr/lib/systemd/system/NetworkManager.service "${AIROOTFS_DIR}/etc/systemd/system/multi-user.target.wants/NetworkManager.service"
rm -f "${AIROOTFS_DIR}/etc/systemd/system/multi-user.target.wants/systemd-networkd.service" \
  "${AIROOTFS_DIR}/etc/systemd/system/network-online.target.wants/systemd-networkd-wait-online.service" \
  "${AIROOTFS_DIR}/etc/systemd/system/sockets.target.wants/systemd-networkd.socket" \
  "${AIROOTFS_DIR}/etc/systemd/system/dbus-org.freedesktop.network1.service"
rm -rf "${AIROOTFS_DIR}/etc/systemd/network" "${AIROOTFS_DIR}/etc/systemd/system/systemd-networkd-wait-online.service.d"
install -d -m 0755 "${AIROOTFS_DIR}/etc/systemd/system"
for u in systemd-networkd.service systemd-networkd.socket systemd-networkd-wait-online.service; do
ln -sf /dev/null "${AIROOTFS_DIR}/etc/systemd/system/${u}"
done

log "Copiando sinergia-installer a ${AIROOTFS_DIR}/opt/sinergia-installer..."
INSTALLER_DEST="${AIROOTFS_DIR}/opt/sinergia-installer"
rm -rf "${INSTALLER_DEST}"
mkdir -p "${INSTALLER_DEST}"
rsync -a --chown=root:root \
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


log "Creando ejecutable y lanzadores .desktop de sinergia-installer..."
install -d -m 0755 "${AIROOTFS_DIR}/usr/local/bin" "${AIROOTFS_DIR}/usr/share/pixmaps"
if [[ -f "${AIROOTFS_DIR}/opt/sinergia-installer/sinergia_installer/assets/logo_puntillismo.png" ]]; then
    install -m 0644 \
        "${AIROOTFS_DIR}/opt/sinergia-installer/sinergia_installer/assets/logo_puntillismo.png" \
        "${AIROOTFS_DIR}/usr/share/pixmaps/sinergia-installer.png"
fi
if [[ -f "${SNAPSHOT_DIR}/airootfs-assets/sinergia-linux.png" ]]; then
    install -m 0644 "${SNAPSHOT_DIR}/airootfs-assets/sinergia-linux.png" "${AIROOTFS_DIR}/usr/share/pixmaps/sinergia-linux.png"
    install -d -m 0755 "${AIROOTFS_DIR}/usr/share/icons/hicolor/256x256/apps"
    install -m 0644 "${SNAPSHOT_DIR}/airootfs-assets/sinergia-linux.png" "${AIROOTFS_DIR}/usr/share/icons/hicolor/256x256/apps/sinergia-linux.png"
fi
if compgen -G "${SNAPSHOT_DIR}/airootfs-assets/sinergia*_fhd.jpg" >/dev/null; then
    install -d -m 0755 "${AIROOTFS_DIR}/usr/share/backgrounds/sinergia"
    install -m 0644 "${SNAPSHOT_DIR}/airootfs-assets/"sinergia*_fhd.jpg "${AIROOTFS_DIR}/usr/share/backgrounds/sinergia/"
fi

# Configurar sinergia2_fhd.jpg como fondo por defecto en Plasma 6 (Live y sistema instalado)
if [[ -f "${AIROOTFS_DIR}/usr/share/backgrounds/sinergia/sinergia2_fhd.jpg" ]]; then
    install -d -m 0755         "${AIROOTFS_DIR}/usr/share/wallpapers/Sinergia/contents/images"         "${AIROOTFS_DIR}/usr/share/plasma/look-and-feel/org.sinergia.desktop/contents"         "${AIROOTFS_DIR}/etc/xdg"         "${AIROOTFS_DIR}/etc/pacman.d/hooks"

    ln -sf /usr/share/backgrounds/sinergia/sinergia2_fhd.jpg         "${AIROOTFS_DIR}/usr/share/wallpapers/Sinergia/contents/images/1920x1080.jpg"

    cat >| "${AIROOTFS_DIR}/usr/share/wallpapers/Sinergia/metadata.json" <<'EOF_WP_META'
{
    "KPlugin": {
        "Authors": [
            {
                "Name": "Sinergia Comunidad Linuxera"
            }
        ],
        "Id": "Sinergia",
        "License": "GPL-3.0-or-later",
        "Name": "Sinergia"
    }
}
EOF_WP_META

    cat >| "${AIROOTFS_DIR}/usr/share/plasma/look-and-feel/org.sinergia.desktop/metadata.json" <<'EOF_LAF_META'
{
    "KPlugin": {
        "Authors": [
            {
                "Name": "Sinergia Comunidad Linuxera"
            }
        ],
        "Description": "Identidad visual por defecto de Sinergia Linux",
        "Id": "org.sinergia.desktop",
        "License": "GPL-3.0-or-later",
        "Name": "Sinergia Linux"
    },
    "KPackageStructure": "Plasma/LookAndFeel"
}
EOF_LAF_META

    cat >| "${AIROOTFS_DIR}/usr/share/plasma/look-and-feel/org.sinergia.desktop/contents/defaults" <<'EOF_LAF_DEF'
[General]
iconTheme=Vortex-Dark
colorScheme=BreezeDark

[Wallpaper]
defaultWallpaperTheme=Sinergia
defaultFileSuffix=.jpg
defaultWidth=1920
defaultHeight=1080
EOF_LAF_DEF

    install -d -m 0755         "${AIROOTFS_DIR}/etc/xdg/gtk-3.0"         "${AIROOTFS_DIR}/etc/xdg/gtk-4.0"

    cat >| "${AIROOTFS_DIR}/etc/xdg/kdeglobals" <<'EOF_KDEGLOBALS'
[General]
ColorScheme=BreezeDark
Name=Breeze Dark
shadeSortColumn=true

[KDE]
LookAndFeelPackage=org.sinergia.desktop
widgetStyle=Breeze

[Icons]
Theme=Vortex-Dark
EOF_KDEGLOBALS

    cat >| "${AIROOTFS_DIR}/etc/xdg/gtk-3.0/settings.ini" <<'EOF_GTK3'
[Settings]
gtk-icon-theme-name=Vortex-Dark
gtk-application-prefer-dark-theme=true
EOF_GTK3

    cat >| "${AIROOTFS_DIR}/etc/xdg/gtk-4.0/settings.ini" <<'EOF_GTK4'
[Settings]
gtk-icon-theme-name=Vortex-Dark
gtk-application-prefer-dark-theme=true
EOF_GTK4

    cat >| "${AIROOTFS_DIR}/etc/pacman.d/hooks/99-sinergia-wallpaper.hook" <<'EOF_WP_HOOK'
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = plasma-workspace

[Action]
Description = Aplicando fondo por defecto de Sinergia Linux en Plasma 6...
When = PostTransaction
Exec = /usr/bin/sed -i 's|<default></default>|<default>file:///usr/share/backgrounds/sinergia/sinergia2_fhd.jpg</default>|' /usr/share/plasma/wallpapers/org.kde.image/contents/config/main.xml
EOF_WP_HOOK
fi

# Quitar Discover y fijar Preferencias, Dolphin y Konsole en Plasma 6
install -d -m 0755 "${AIROOTFS_DIR}/usr/local/bin" "${AIROOTFS_DIR}/etc/pacman.d/hooks" "${AIROOTFS_DIR}/etc/xdg" "${AIROOTFS_DIR}/etc/skel/.config"

cat >| "${AIROOTFS_DIR}/usr/local/bin/sinergia-patch-panel" <<'EOF_PATCH_PANEL'
#!/usr/bin/env python3
import pathlib
import re

LAUNCHERS_VALUE = (
    "applications:systemsettings.desktop,"
    "applications:org.kde.dolphin.desktop,"
    "applications:org.kde.konsole.desktop"
)


KICKOFF_ICON = "/usr/share/pixmaps/sinergia-linux.png"

def patch_kickoff_icon(content: str) -> str:
    lines = content.splitlines(keepends=True)
    target_groups = set()
    current_section = None
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            current_section = s[1:-1]
        elif s == "plugin=org.kde.plasma.kickoff" and current_section:
            if "[Applets][" in current_section:
                target_groups.add(f"[{current_section}][Configuration][General]")

    if not target_groups:
        return content

    out = []
    active_group = None
    written_groups = set()

    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            if active_group in target_groups and active_group not in written_groups:
                out.append(f"icon={KICKOFF_ICON}\n")
                written_groups.add(active_group)
            active_group = s
            out.append(line)
            continue

        if active_group in target_groups and s.startswith("icon="):
            nl = "\n" if line.endswith("\n") else ""
            out.append(f"icon={KICKOFF_ICON}{nl}")
            written_groups.add(active_group)
            continue

        out.append(line)

    if active_group in target_groups and active_group not in written_groups:
        out.append(f"icon={KICKOFF_ICON}\n")
        written_groups.add(active_group)

    for grp in sorted(target_groups - written_groups):
        out.append(f"\n{grp}\nicon={KICKOFF_ICON}\n")

    return "".join(out)

js_path = pathlib.Path("/usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js")
if js_path.exists():
    jtxt = js_path.read_text(encoding="utf-8", errors="replace")
    kickoff_snippet = (
        'var sinergiaKickoff = panel.addWidget("org.kde.plasma.kickoff");\n'
        'sinergiaKickoff.currentConfigGroup = ["General"];\n'
        'sinergiaKickoff.writeConfig("icon", "/usr/share/pixmaps/sinergia-linux.png");'
    )
    if 'writeConfig("icon", "/usr/share/pixmaps/sinergia-linux.png")' not in jtxt:
        if 'panel.addWidget("org.kde.plasma.kickoff");' in jtxt:
            jtxt = jtxt.replace('panel.addWidget("org.kde.plasma.kickoff");', kickoff_snippet, 1)
        elif 'panel.addWidget("org.kde.plasma.kickoff")' in jtxt:
            jtxt = jtxt.replace('panel.addWidget("org.kde.plasma.kickoff")', kickoff_snippet, 1)
        else:
            jtxt += "\n" + kickoff_snippet + "\n"
        js_path.write_text(jtxt, encoding="utf-8")

def sanitize_appletsrc(content: str) -> str:
    cleaned = re.sub(r'applications:org\.kde\.discover\.desktop,?', '', content)
    cleaned = re.sub(r'applications:zen(?:-browser)?\.desktop,?', '', cleaned)
    if "launchers=" in cleaned:
        out_lines = []
        for line in cleaned.splitlines(keepends=True):
            if line.startswith("launchers="):
                nl = "\n" if line.endswith("\n") else ""
                out_lines.append(f"launchers={LAUNCHERS_VALUE}{nl}")
            else:
                out_lines.append(line)
        return "".join(out_lines)
    if "[Containments][" in cleaned or "plugin=org.kde.plasma.icontasks" in cleaned:
        cleaned += f"\n[General]\nlaunchers={LAUNCHERS_VALUE}\n"
    return patch_kickoff_icon(cleaned)

js_path = pathlib.Path("/usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js")
if js_path.exists():
    txt = js_path.read_text(encoding="utf-8")
    snippet = (
        'var sinergiaTasks = panel.addWidget("org.kde.plasma.icontasks");\n'
        'sinergiaTasks.currentConfigGroup = ["General"];\n'
        'sinergiaTasks.writeConfig("launchers", [\n'
        '    "applications:systemsettings.desktop",\n'
        '    "applications:org.kde.dolphin.desktop",\n'
        '    "applications:org.kde.konsole.desktop"\n'
        ']);'
    )
    existing_block = re.compile(
        r'var sinergiaTasks = panel\.addWidget\("org\.kde\.plasma\.icontasks"\);.*?sinergiaTasks\.writeConfig\("launchers",\s*\[.*?\]\);',
        re.DOTALL,
    )
    if existing_block.search(txt):
        txt = existing_block.sub(lambda _: snippet, txt, count=1)
    elif 'panel.addWidget("org.kde.plasma.icontasks");' in txt:
        txt = txt.replace('panel.addWidget("org.kde.plasma.icontasks");', snippet, 1)
    elif 'panel.addWidget("org.kde.plasma.icontasks")' in txt:
        txt = txt.replace('panel.addWidget("org.kde.plasma.icontasks")', snippet, 1)
    else:
        txt += "\n" + snippet + "\n"
    js_path.write_text(txt, encoding="utf-8")

targets = []
for base in [pathlib.Path("/etc/xdg"), pathlib.Path("/etc/skel"), pathlib.Path("/home")]:
    if base.exists():
        targets.extend(base.rglob("plasma-org.kde.plasma.desktop-appletsrc"))

for rc in targets:
    try:
        orig = rc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    updated = sanitize_appletsrc(orig)
    if updated != orig:
        rc.write_text(updated, encoding="utf-8")

# Asegurar archivo base en /etc/xdg si no existiera
xdg_rc = pathlib.Path("/etc/xdg/plasma-org.kde.plasma.desktop-appletsrc")
if not xdg_rc.exists():
    xdg_rc.write_text(f"[General]\nlaunchers={LAUNCHERS_VALUE}\n", encoding="utf-8")
EOF_PATCH_PANEL
chmod 0755 "${AIROOTFS_DIR}/usr/local/bin/sinergia-patch-panel"

cat >| "${AIROOTFS_DIR}/etc/xdg/plasma-org.kde.plasma.desktop-appletsrc" <<'EOF_XDG_APPLETSRC'
[General]
launchers=applications:systemsettings.desktop,applications:org.kde.dolphin.desktop,applications:org.kde.konsole.desktop
EOF_XDG_APPLETSRC

cat >| "${AIROOTFS_DIR}/etc/pacman.d/hooks/98-sinergia-panel-launchers.hook" <<'EOF_PANEL_HOOK'
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = plasma-desktop

[Action]
Description = Fijando Preferencias, Dolphin y Konsole en el gestor de tareas de Plasma 6...
When = PostTransaction
Exec = /usr/local/bin/sinergia-patch-panel
EOF_PANEL_HOOK

# Instalar y activar el tema oscuro de SDDM (sinergia-sddm)
if [[ -d "${SNAPSHOT_DIR}/airootfs-assets/sddm-theme-sinergia" ]]; then
    install -d -m 0755 \
        "${AIROOTFS_DIR}/usr/share/sddm/themes/sinergia-sddm" \
        "${AIROOTFS_DIR}/etc/sddm.conf.d"

    cp -a "${SNAPSHOT_DIR}/airootfs-assets/sddm-theme-sinergia/." \
        "${AIROOTFS_DIR}/usr/share/sddm/themes/sinergia-sddm/"
    chmod -R u=rwX,go=rX "${AIROOTFS_DIR}/usr/share/sddm/themes/sinergia-sddm"

    if [[ -f "${AIROOTFS_DIR}/usr/share/backgrounds/sinergia/sinergia2_fhd.jpg" ]]; then
        ln -sf /usr/share/backgrounds/sinergia/sinergia2_fhd.jpg \
            "${AIROOTFS_DIR}/usr/share/sddm/themes/sinergia-sddm/preview.jpg"
    fi

    cat >| "${AIROOTFS_DIR}/etc/sddm.conf.d/10-sinergia-theme.conf" <<'EOF_SDDM_CONF'
[Theme]
Current=sinergia-sddm
CursorTheme=breeze_cursors
EOF_SDDM_CONF
fi

printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'if [[ "${EUID}" -eq 0 ]]; then exec python3 /opt/sinergia-installer/main.py "$@"; fi' \
    'exec pkexec env DISPLAY="${DISPLAY:-}" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-}" DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-}" XAUTHORITY="${XAUTHORITY:-}" QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-}" QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-}" python3 /opt/sinergia-installer/main.py "$@"' \
    >| "${AIROOTFS_DIR}/usr/local/bin/sinergia-installer"
chmod 0755 "${AIROOTFS_DIR}/usr/local/bin/sinergia-installer"

install -d -m 0755 "${AIROOTFS_DIR}/usr/share/applications"
printf '%s\n' \
    '[Desktop Entry]' \
    'Type=Application' \
    'Version=1.0' \
    'Name=Instalar Sinergia Linux (Arkea)' \
    'GenericName=Instalador del Sistema' \
    'Comment=Arkea — Asistente de instalación de Sinergia Linux' \
    'Exec=/usr/local/bin/sinergia-installer' \
    'Icon=/usr/share/pixmaps/sinergia-installer.png' \
    'StartupWMClass=sinergia-installer' \
    'Terminal=false' \
    'Categories=System;Settings;' \
    'StartupNotify=true' \
    >| "${AIROOTFS_DIR}/usr/share/applications/sinergia-installer.desktop"
chmod 0644 "${AIROOTFS_DIR}/usr/share/applications/sinergia-installer.desktop"

install -d -m 0755 -o 1000 -g 1000 "${AIROOTFS_DIR}/home/live/Desktop"
install -m 0755 -o 1000 -g 1000 \
    "${AIROOTFS_DIR}/usr/share/applications/sinergia-installer.desktop" \
    "${AIROOTFS_DIR}/home/live/Desktop/sinergia-installer.desktop"

log "Listo. Perfil restaurado en ${TARGET_DIR}."

# Autostart de sinergia-welcome en Plasma 6
install -d -m 0755 "${AIROOTFS_DIR}/etc/xdg/autostart"
cat >| "${AIROOTFS_DIR}/etc/xdg/autostart/sinergia-welcome.desktop" <<'EOF_WELCOME_AUTOSTART'
[Desktop Entry]
Type=Application
Name=Sinergia Welcome
Comment=Pantalla de bienvenida de Sinergia Linux
Exec=/usr/bin/sinergia-welcome
Terminal=false
OnlyShowIn=KDE;
X-KDE-autostart-phase=2
EOF_WELCOME_AUTOSTART
chmod 0644 "${AIROOTFS_DIR}/etc/xdg/autostart/sinergia-welcome.desktop"


# Crear sinergia-live-panel-fix y su autostart en el Live para fijar Kickoff y lanzadores con kwriteconfig6
install -d -m 0755 "${AIROOTFS_DIR}/usr/local/bin" "${AIROOTFS_DIR}/etc/xdg/autostart"
cat >| "${AIROOTFS_DIR}/usr/local/bin/sinergia-live-panel-fix" <<'EOF_LIVE_PANEL_FIX'
#!/usr/bin/env bash
set -uo pipefail

RC="${HOME}/.config/plasma-org.kde.plasma.desktop-appletsrc"
id "live" &>/dev/null || exit 0
MARKER="${HOME}/.config/.sinergia-panel-initialized"
ICON_PATH="/usr/share/pixmaps/sinergia-linux.png"
LAUNCHERS="applications:systemsettings.desktop,applications:org.kde.dolphin.desktop,applications:org.kde.konsole.desktop"

[ -f "${MARKER}" ] && exit 0

for _ in $(seq 1 40); do
  [ -f "${RC}" ] && grep -q "plugin=org.kde.plasma.icontasks" "${RC}" && break
  sleep 0.5
done

[ -f "${RC}" ] || exit 0
command -v kwriteconfig6 >/dev/null 2>&1 || exit 0

changed=0
while IFS=: read -r c_id a_id plugin; do
  [ -n "${c_id}" ] && [ -n "${a_id}" ] || continue
  if [ "${plugin}" = "org.kde.plasma.kickoff" ]; then
    kwriteconfig6 --file "${RC}"       --group Containments --group "${c_id}" --group Applets --group "${a_id}" --group Configuration --group General       --key icon "${ICON_PATH}"
    changed=1
  elif [ "${plugin}" = "org.kde.plasma.icontasks" ]; then
    kwriteconfig6 --file "${RC}"       --group Containments --group "${c_id}" --group Applets --group "${a_id}" --group Configuration --group General       --key launchers "${LAUNCHERS}"
    changed=1
  fi
done < <(python3 - "${RC}" <<'PY_PARSE'
import pathlib, re, sys

lines = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
cur_c = cur_a = None
for line in lines:
    s = line.strip()
    m = re.fullmatch(r"\[Containments\]\[(\d+)\]\[Applets\]\[(\d+)\]", s)
    if m:
        cur_c, cur_a = m.group(1), m.group(2)
    elif s.startswith("[Containments]["):
        cur_c = cur_a = None
    elif s.startswith("plugin=") and cur_c and cur_a:
        print(f"{cur_c}:{cur_a}:{s.split('=', 1)[1]}")
PY_PARSE
)

touch "${MARKER}"

if [ "${changed}" -eq 1 ]; then
  mkdir -p "${HOME}/.config"
  cat >| "${HOME}/.config/ksplashrc" <<'EOF_LIVE_KSPLASH'
[KSplash]
Theme=org.sinergia.desktop
Engine=KSplashQML
EOF_LIVE_KSPLASH
fi
EOF_LIVE_PANEL_FIX
chmod 0755 "${AIROOTFS_DIR}/usr/local/bin/sinergia-live-panel-fix"

cat >| "${AIROOTFS_DIR}/etc/xdg/autostart/sinergia-panel-fix.desktop" <<'EOF_PANEL_AUTOSTART'
[Desktop Entry]
Type=Application
Name=Sinergia Live Panel Fix
Exec=/usr/local/bin/sinergia-live-panel-fix
Terminal=false
OnlyShowIn=KDE;
X-KDE-autostart-phase=2
EOF_PANEL_AUTOSTART
chmod 0644 "${AIROOTFS_DIR}/etc/xdg/autostart/sinergia-panel-fix.desktop"


if [[ -f "${TARGET_DIR}/profiledef.sh" ]] && ! grep -q '"/usr/local/bin/sinergia-live-panel-fix"' "${TARGET_DIR}/profiledef.sh"; then
  python3 - "${TARGET_DIR}/profiledef.sh" <<'PY_PERM'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
txt = p.read_text(encoding="utf-8")
if "file_permissions=(" in txt:
    txt = txt.replace(
        "file_permissions=(",
        'file_permissions=(\n  ["/usr/local/bin/sinergia-live-panel-fix"]="0:0:755"',
        1,
    )
    p.write_text(txt, encoding="utf-8")
PY_PERM
fi


# Parchear layout.js del panel por defecto en customize_airootfs.sh (después de pacstrap)
CUSTOMIZE_SCRIPT="${AIROOTFS_DIR}/root/customize_airootfs.sh"
if [[ -f "${CUSTOMIZE_SCRIPT}" ]] && ! grep -q "sinergiaKickoff" "${CUSTOMIZE_SCRIPT}"; then
  cat >> "${CUSTOMIZE_SCRIPT}" <<'EOF_CUSTOMIZE_PANEL'

# Fijar icono de Kickoff y lanzadores iniciales en defaultPanel/contents/layout.js
if [ -f /usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js ]; then
  python3 - /usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js <<'PY_JS_CUST'
import pathlib, re, sys
p = pathlib.Path(sys.argv[1])
txt = p.read_text(encoding="utf-8")

kickoff_rep = (
    'var sinergiaKickoff = panel.addWidget("org.kde.plasma.kickoff");\n'
    'sinergiaKickoff.currentConfigGroup = ["General"];\n'
    'sinergiaKickoff.writeConfig("icon", "/usr/share/pixmaps/sinergia-linux.png");'
)
icontasks_rep = (
    'var sinergiaTasks = panel.addWidget("org.kde.plasma.icontasks");\n'
    'sinergiaTasks.currentConfigGroup = ["General"];\n'
    'sinergiaTasks.writeConfig("launchers", ['
    '"applications:systemsettings.desktop", '
    '"applications:org.kde.dolphin.desktop", '
    '"applications:org.kde.konsole.desktop"]);'
)

if "sinergiaKickoff" not in txt:
    txt = re.sub(r'panel\.addWidget\("org\.kde\.plasma\.kickoff"\);?', kickoff_rep, txt, count=1)
if "sinergiaTasks" not in txt:
    txt = re.sub(r'panel\.addWidget\("org\.kde\.plasma\.icontasks"\);?', icontasks_rep, txt, count=1)

p.write_text(txt, encoding="utf-8")
PY_JS_CUST
fi
EOF_CUSTOMIZE_PANEL
fi


# Crear tema KSplash "Sinergia" y fijarlo por defecto en Live y /etc/skel
KSPLASH_DIR="${AIROOTFS_DIR}/usr/share/plasma/look-and-feel/org.sinergia.desktop"
install -d -m 0755 "${KSPLASH_DIR}/contents/splash" "${KSPLASH_DIR}/contents/previews" "${AIROOTFS_DIR}/etc/skel/.config"

if [[ -f "${AIROOTFS_DIR}/usr/share/pixmaps/sinergia-linux.png" ]]; then
  cp -f "${AIROOTFS_DIR}/usr/share/pixmaps/sinergia-linux.png" "${KSPLASH_DIR}/contents/previews/splash.png"
  cp -f "${AIROOTFS_DIR}/usr/share/pixmaps/sinergia-linux.png" "${KSPLASH_DIR}/contents/previews/preview.png"
fi

cat >| "${KSPLASH_DIR}/metadata.json" <<'EOF_KSPLASH_META'
{
    "KPlugin": {
        "Authors": [
            {
                "Name": "Sinergia Comunidad Linuxera"
            }
        ],
        "Id": "org.sinergia.desktop",
        "Name": "Sinergia",
        "Description": "Pantalla de bienvenida de Sinergia Linux para KDE Plasma",
        "Version": "1.0",
        "Category": "Plasma Look And Feel",
        "License": "GPL-3.0-or-later"
    },
    "KPackageStructure": "Plasma/LookAndFeel"
}
EOF_KSPLASH_META
chmod 0644 "${KSPLASH_DIR}/metadata.json"

cat >| "${KSPLASH_DIR}/contents/splash/Splash.qml" <<'EOF_KSPLASH_QML'
import QtQuick

Rectangle {
    id: root
    color: "#0e1013"

    property int stage: 1
    property real progress: 0.20

    onStageChanged: {
        if (stage === 1) progress = 0.25
        else if (stage === 2) progress = 0.50
        else if (stage === 3) progress = 0.78
        else if (stage >= 4) progress = 1.0
    }

    // Fondo de pantalla de Sinergia a pantalla completa
    Image {
        id: wallpaper
        anchors.fill: parent
        source: "file:///usr/share/backgrounds/sinergia/sinergia2_fhd.jpg"
        fillMode: Image.PreserveAspectCrop
        smooth: true
    }

    // Ligero oscurecimiento para dar contraste al árbol y a la barra de carga
    Rectangle {
        anchors.fill: parent
        color: "#0b0d10"
        opacity: 0.35
    }

    // Gráfico central con el arbolito de Sinergia y etiqueta
    Column {
        anchors.centerIn: parent
        spacing: 16

        Item {
            width: 176
            height: 176
            anchors.horizontalCenter: parent.horizontalCenter

            // Halo suave detrás del arbolito
            Rectangle {
                anchors.centerIn: parent
                width: 164
                height: 164
                radius: 82
                color: "#3daee9"
                opacity: 0.14
            }

            Image {
                id: treeIcon
                anchors.centerIn: parent
                source: "file:///usr/share/pixmaps/sinergia-linux.png"
                width: 148
                height: 148
                fillMode: Image.PreserveAspectFit
                smooth: true

                SequentialAnimation on scale {
                    running: true
                    loops: Animation.Infinite
                    NumberAnimation { to: 1.05; duration: 900; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.00; duration: 900; easing.type: Easing.InOutSine }
                }
            }
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "SINERGIA LINUX"
            color: "#f4f6f9"
            font.pixelSize: 24
            font.bold: true
            font.letterSpacing: 3
        }
    }

    // Barra de progreso inferior
    Rectangle {
        id: progressTrack
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 68
        width: 340
        height: 6
        radius: 3
        color: "#88000000"
        border.color: "#44ffffff"
        border.width: 1

        Rectangle {
            height: parent.height
            radius: 3
            width: parent.width * root.progress
            color: "#3daee9"

            Behavior on width {
                NumberAnimation { duration: 350; easing.type: Easing.InOutQuad }
            }
        }
    }
}
EOF_KSPLASH_QML
chmod 0644 "${KSPLASH_DIR}/contents/splash/Splash.qml"

cat >| "${KSPLASH_DIR}/metadata.json" <<'EOF_KSPLASH_META'
{
    "KPackageStructure": "Plasma/LookAndFeel",
    "KPlugin": {
        "Authors": [
            {
                "Name": "Sinergia Comunidad Linuxera"
            }
        ],
        "Description": "Pantalla de bienvenida y tema Sinergia Linux",
        "EnabledByDefault": true,
        "Id": "org.sinergia.desktop",
        "License": "GPL-3.0-or-later",
        "Name": "Sinergia",
        "Version": "1.0"
    }
}
EOF_KSPLASH_META
chmod 0644 "${KSPLASH_DIR}/metadata.json"

cat >| "${AIROOTFS_DIR}/etc/skel/.config/ksplashrc" <<'EOF_KSPLASH_RC'
[KSplash]
Theme=org.sinergia.desktop
Engine=KSplashQML
EOF_KSPLASH_RC
chmod 0644 "${AIROOTFS_DIR}/etc/skel/.config/ksplashrc"

if [[ -d "${AIROOTFS_DIR}/home/live" ]]; then
  install -d -m 0755 "${AIROOTFS_DIR}/home/live/.config"
  cp -f "${AIROOTFS_DIR}/etc/skel/.config/ksplashrc" "${AIROOTFS_DIR}/home/live/.config/ksplashrc"
fi


# Fijar KSplash Sinergia a nivel global (/etc/xdg/ksplashrc) para el primer arranque
install -d -m 0755 "${AIROOTFS_DIR}/etc/xdg"
cat >| "${AIROOTFS_DIR}/etc/xdg/ksplashrc" <<'EOF_XDG_KSPLASH'
[KSplash]
Theme=org.sinergia.desktop
Engine=KSplashQML
EOF_XDG_KSPLASH
chmod 0644 "${AIROOTFS_DIR}/etc/xdg/ksplashrc"
