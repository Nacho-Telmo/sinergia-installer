# Sinergia Installer

Instalador gráfico desarrollado en **Python** y **PyQt6** para **Sinergia Linux** (distribución basada en Arch Linux creada por **Sinergia Comunidad Linuxera**).

Diseñado bajo software libre (**GPL-3.0**) para ofrecer una instalación limpia, directa y sin dependencias pesadas, desacoplada de rutas rígidas del entorno Live.

---

## Características principales

- **Interfaz gráfica en PyQt6:** Asistente paso a paso con selección de idioma/zona horaria, particionado de discos, creación de usuario, resumen previo y progreso en tiempo real.
- **Detección dinámica del medio de origen (`rootfs`):** Localiza automáticamente `airootfs.sfs` y `vmlinuz-linux` en cualquier punto de montaje del medio de arranque sin depender exclusivamente de `/run/archiso/bootmnt`.
- **Despliegue robusto del sistema:** Extracción directa con `unsquashfs` y mecanismo de respaldo (*fallback*) mediante `rsync` a `/mnt` en caso de entornos desmontados o estructuras alternativas.
- **Preconfiguración de Sinergia Linux:** Preparado para dejar operativos `sinergia-repo`, `sinergia-keyring`, repositorios adicionales y scripts de post-instalación (`sinergia-post-install.sh`).
- **Snapshot reproducible del perfil ISO:** Incluye en `iso-profile-snapshot/` la definición del perfil `archiso` (`packages.x86_64`, `pacman.conf`, `profiledef.sh`, configuraciones de arranque GRUB/systemd-boot/Syslinux y entorno Live).

---

## Estructura del proyecto

```text
sinergia-installer/
├── main.py                        # Punto de entrada de la aplicación PyQt6
├── pyproject.toml                 # Metadatos y configuración del paquete Python
├── sinergia_installer/
│   ├── core/
│   │   ├── disks.py               # Detección y gestión de discos y particiones
│   │   └── installer_engine.py    # Motor de instalación (rootfs, chroot, bootloader, post-install)
│   ├── models/
│   │   └── install_config.py      # Modelo de datos con los parámetros de instalación
│   └── ui/
│       ├── main_window.py         # Ventana principal y navegación del asistente
│       ├── page_welcome.py        # Pantalla de bienvenida
│       ├── page_locale.py         # Configuración regional, teclado y zona horaria
│       ├── page_partitions.py     # Selección y particionado de disco destino
│       ├── page_user.py           # Creación de usuario, contraseña y hostname
│       ├── page_summary.py        # Resumen de cambios antes de aplicar
│       └── page_progress.py       # Barra de progreso y registro de ejecución
└── iso-profile-snapshot/          # Respaldo del perfil archiso de Sinergia Linux
    ├── packages.x86_64            # Lista de paquetes incluidos en la ISO
    ├── pacman.conf                # Configuración de repositorios (Arch, Sinergia, Chaotic-AUR)
    ├── profiledef.sh              # Definición de imagen y permisos archiso
    ├── sinergia-post-install.sh   # Script de ajustes posteriores a la instalación
    ├── sinergia-repo.asc          # Clave pública GPG del repositorio Sinergia
    ├── boot-configs/              # Configuraciones de GRUB, systemd-boot (efiboot) y Syslinux
    └── etc-live/                  # Configuraciones del sistema en vivo (autologin, sudoers, motd)
