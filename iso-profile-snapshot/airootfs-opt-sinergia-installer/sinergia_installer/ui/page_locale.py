import os
import subprocess
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.models.install_config import InstallConfig

FALLBACK_LOCALES = [
    "es_AR.UTF-8",
    "es_ES.UTF-8",
    "es_MX.UTF-8",
    "en_US.UTF-8",
]

FALLBACK_KEYMAPS = [
    "us",
    "la-latin1",
    "es",
]

FALLBACK_TIMEZONES = [
    "America/Argentina/Buenos_Aires",
    "America/Argentina/Cordoba",
    "America/Argentina/Mendoza",
    "America/Montevideo",
    "America/Santiago",
    "America/Mexico_City",
    "America/Bogota",
    "Europe/Madrid",
    "UTC",
]


def load_system_locales() -> list[str]:
    locales: set[str] = set()
    locale_gen = "/etc/locale.gen"
    if os.path.isfile(locale_gen):
        with open(locale_gen, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.strip().lstrip("#").strip()
                if not line:
                    continue
                parts = line.split()
                code = parts[0]
                if ".UTF-8" in code or "UTF-8" in line:
                    # Normaliza "es_AR.UTF-8" aunque en locale.gen figure "es_AR.UTF-8 UTF-8"
                    locales.add(code)

    if not locales:
        return FALLBACK_LOCALES
    return sorted(locales)


def load_system_keymaps() -> list[str]:
    try:
        proc = subprocess.run(
            ["localectl", "list-keymaps"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        keymaps = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if keymaps:
            return sorted(set(keymaps))
    except Exception:
        pass

    base_dir = "/usr/share/kbd/keymaps"
    found: set[str] = set()
    if os.path.isdir(base_dir):
        for root, _, files in os.walk(base_dir):
            for fname in files:
                if fname.endswith(".map.gz"):
                    found.add(fname[:-7])
                elif fname.endswith(".map"):
                    found.add(fname[:-4])

    return sorted(found) if found else FALLBACK_KEYMAPS


def load_system_timezones() -> list[str]:
    zone_tab = "/usr/share/zoneinfo/zone.tab"
    zones: set[str] = set()

    if os.path.isfile(zone_tab):
        with open(zone_tab, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                cols = line.split("\t")
                if len(cols) >= 3 and cols[2].strip():
                    zones.add(cols[2].strip())

    if not zones:
        base_dir = "/usr/share/zoneinfo"
        skip = {"posix", "right", "Etc", "SystemV", "Factory"}
        if os.path.isdir(base_dir):
            for root, _, files in os.walk(base_dir):
                for fname in files:
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, base_dir)
                    top = rel.split("/")[0]
                    if top in skip or "." in fname:
                        continue
                    if os.path.isfile(full) and not os.path.islink(full):
                        zones.add(rel)

    if not zones:
        return FALLBACK_TIMEZONES

    zones.add("UTC")
    return sorted(zones)


def _make_searchable_combo(items: list[str]) -> QComboBox:
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    for item in items:
        combo.addItem(item, item)

    completer = QCompleter(items, combo)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    combo.setCompleter(completer)
    return combo


class LocalePage(QWidget):
    def __init__(self, config: InstallConfig) -> None:
        super().__init__()
        self.config = config
        self._build_ui()
        self._load_defaults()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        grp = QGroupBox("Idioma, teclado y zona horaria")
        form = QFormLayout(grp)

        locales = load_system_locales()
        keymaps = load_system_keymaps()
        timezones = load_system_timezones()

        self.combo_locale = _make_searchable_combo(locales)
        self.combo_keymap = _make_searchable_combo(keymaps)
        self.combo_timezone = _make_searchable_combo(timezones)

        form.addRow("Idioma del sistema:", self.combo_locale)
        form.addRow("Mapa de teclado:", self.combo_keymap)
        form.addRow("Zona horaria:", self.combo_timezone)
        layout.addWidget(grp)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #c62828;")
        layout.addWidget(self.lbl_error)
        layout.addStretch()

    def _load_defaults(self) -> None:
        self.combo_locale.setCurrentText(self.config.locale)
        self.combo_keymap.setCurrentText(self.config.keymap)
        self.combo_timezone.setCurrentText(self.config.timezone)

    def save_and_validate(self) -> bool:
        locale = self.combo_locale.currentText().strip()
        keymap = self.combo_keymap.currentText().strip()
        timezone = self.combo_timezone.currentText().strip()

        errors: list[str] = []
        if not locale:
            errors.append("Seleccioná o ingresá un idioma del sistema.")
        if not keymap:
            errors.append("Seleccioná o ingresá un mapa de teclado.")
        if not timezone:
            errors.append("Seleccioná o ingresá una zona horaria.")

        if errors:
            msg = "\n".join(errors)
            self.lbl_error.setText(msg)
            QMessageBox.warning(self, "Configuración regional", msg)
            return False

        self.lbl_error.setText("")
        self.config.locale = locale
        self.config.keymap = keymap
        self.config.timezone = timezone
        return True
