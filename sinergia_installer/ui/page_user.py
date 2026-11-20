import re
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.models.install_config import InstallConfig

USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")


class UserPage(QWidget):
    def __init__(self, config: InstallConfig) -> None:
        super().__init__()
        self.config = config
        self._build_ui()
        self._load_defaults()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        grp = QGroupBox("Usuario y nombre del equipo")
        self.form = QFormLayout(grp)

        self.txt_full_name = QLineEdit()
        self.txt_full_name.setPlaceholderText("Ej. Nacho Telmo")

        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Ej. nacho (minúsculas, sin espacios)")

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Contraseña del usuario")

        self.txt_password_confirm = QLineEdit()
        self.txt_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password_confirm.setPlaceholderText("Repetir contraseña")

        self.lbl_pw_match = QLabel("")

        self.chk_same_root_pw = QCheckBox("Usar la misma contraseña para el superusuario (root)")
        self.chk_same_root_pw.setChecked(True)
        self.chk_same_root_pw.toggled.connect(self._on_same_root_pw_toggled)

        self.lbl_root_password = QLabel("Contraseña de root:")
        self.txt_root_password = QLineEdit()
        self.txt_root_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_root_password.setPlaceholderText("Contraseña del superusuario (root)")

        self.lbl_root_password_confirm = QLabel("Confirmar root:")
        self.txt_root_password_confirm = QLineEdit()
        self.txt_root_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_root_password_confirm.setPlaceholderText("Repetir contraseña de root")

        self.lbl_root_pw_match = QLabel("")

        self.txt_hostname = QLineEdit()
        self.txt_hostname.setPlaceholderText("Ej. sinergia-plasma")

        self.chk_use_sudo = QCheckBox("El usuario usará sudo (grupo wheel), pidiendo contraseña")
        self.chk_use_sudo.setChecked(True)

        self.form.addRow("Nombre completo:", self.txt_full_name)
        self.form.addRow("Nombre de usuario:", self.txt_username)
        self.form.addRow("Contraseña:", self.txt_password)
        self.form.addRow("Confirmar contraseña:", self.txt_password_confirm)
        self.form.addRow("", self.lbl_pw_match)
        self.form.addRow("", self.chk_same_root_pw)
        self.form.addRow(self.lbl_root_password, self.txt_root_password)
        self.form.addRow(self.lbl_root_password_confirm, self.txt_root_password_confirm)
        self.form.addRow("", self.lbl_root_pw_match)
        self.form.addRow("Nombre del equipo (hostname):", self.txt_hostname)
        self.form.addRow("", self.chk_use_sudo)

        layout.addWidget(grp)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #c62828;")
        layout.addWidget(self.lbl_error)
        layout.addStretch()

        self.txt_password.textChanged.connect(self._update_password_match_status)
        self.txt_password_confirm.textChanged.connect(self._update_password_match_status)
        self.txt_root_password.textChanged.connect(self._update_password_match_status)
        self.txt_root_password_confirm.textChanged.connect(self._update_password_match_status)

        self._on_same_root_pw_toggled(self.chk_same_root_pw.isChecked())
        self._update_password_match_status()

    def _set_match_label(self, label: QLabel, pw1: str, pw2: str) -> None:
        if not pw1 and not pw2:
            label.setText("")
            label.setStyleSheet("")
            return
        if not pw2:
            label.setText("Repetí la contraseña para confirmar")
            label.setStyleSheet("color: #9e9e9e;")
            return
        if pw1 == pw2:
            label.setText("✓ Las contraseñas coinciden")
            label.setStyleSheet("color: #2e7d32; font-weight: bold;")
        else:
            label.setText("✗ Las contraseñas no coinciden")
            label.setStyleSheet("color: #c62828; font-weight: bold;")

    def _update_password_match_status(self) -> None:
        self._set_match_label(
            self.lbl_pw_match,
            self.txt_password.text(),
            self.txt_password_confirm.text(),
        )
        if not self.chk_same_root_pw.isChecked():
            self._set_match_label(
                self.lbl_root_pw_match,
                self.txt_root_password.text(),
                self.txt_root_password_confirm.text(),
            )
        else:
            self.lbl_root_pw_match.setText("")
            self.lbl_root_pw_match.setStyleSheet("")

    def _on_same_root_pw_toggled(self, checked: bool) -> None:
        show_root_fields = not checked
        self.lbl_root_password.setVisible(show_root_fields)
        self.txt_root_password.setVisible(show_root_fields)
        self.lbl_root_password_confirm.setVisible(show_root_fields)
        self.txt_root_password_confirm.setVisible(show_root_fields)
        self.lbl_root_pw_match.setVisible(show_root_fields)
        self._update_password_match_status()

    def _load_defaults(self) -> None:
        self.txt_full_name.setText(self.config.full_name)
        self.txt_username.setText(self.config.username)
        self.txt_password.setText(self.config.password)
        self.txt_password_confirm.setText(self.config.password)
        self.chk_same_root_pw.setChecked(self.config.same_password_for_root)
        self.txt_root_password.setText(self.config.root_password)
        self.txt_root_password_confirm.setText(self.config.root_password)
        self.txt_hostname.setText(self.config.hostname)
        # Si sudo_nopasswd era True, igual mantenemos sudo activo pidiendo contraseña por defecto
        self.chk_use_sudo.setChecked(True)
        self._on_same_root_pw_toggled(self.chk_same_root_pw.isChecked())
        self._update_password_match_status()

    def save_and_validate(self) -> bool:
        errors: list[str] = []

        full_name = self.txt_full_name.text().strip()
        username = self.txt_username.text().strip()
        password = self.txt_password.text()
        password_confirm = self.txt_password_confirm.text()
        same_root_pw = self.chk_same_root_pw.isChecked()
        root_password = self.txt_root_password.text()
        root_password_confirm = self.txt_root_password_confirm.text()
        hostname = self.txt_hostname.text().strip()

        if not username:
            errors.append("Ingresá un nombre de usuario.")
        elif not USERNAME_RE.match(username):
            errors.append(
                "El nombre de usuario debe empezar con letra minúscula o '_' y contener solo minúsculas, números, '_' o '-'."
            )

        if not password:
            errors.append("Ingresá una contraseña para el usuario.")
        elif password != password_confirm:
            errors.append("Las contraseñas del usuario no coinciden.")

        if not same_root_pw:
            if not root_password:
                errors.append("Ingresá una contraseña para el superusuario (root).")
            elif root_password != root_password_confirm:
                errors.append("Las contraseñas de root no coinciden.")

        if not hostname:
            errors.append("Ingresá un nombre de equipo (hostname).")
        elif not HOSTNAME_RE.match(hostname):
            errors.append("El hostname solo puede contener letras, números y guiones (sin espacios).")

        if errors:
            msg = "\n".join(errors)
            self.lbl_error.setText(msg)
            QMessageBox.warning(self, "Datos de usuario", msg)
            return False

        self.lbl_error.setText("")
        self.config.full_name = full_name or username
        self.config.username = username
        self.config.password = password
        self.config.same_password_for_root = same_root_pw
        self.config.root_password = password if same_root_pw else root_password
        self.config.hostname = hostname
        # Siempre pide contraseña al usar sudo cuando está habilitado
        self.config.sudo_nopasswd = False
        return True
