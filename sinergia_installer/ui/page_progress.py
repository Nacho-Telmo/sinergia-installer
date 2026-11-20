from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sinergia_installer.core.installer_engine import InstallerEngine
from sinergia_installer.models.install_config import InstallConfig

SLIDES_METADATA: list[tuple[str, str, str]] = [
    (
        "01_sinergia_linux.png",
        "Sinergia Linux + KDE Plasma",
        "Un entorno construido sobre Arch Linux con enfoque comunitario, fluidez y herramientas propias.",
    ),
    (
        "02_union_futurista.png",
        "Software libre y control del sistema",
        "Configuración limpia, paquetes actualizados y repositorios sinergia-repo y chaotic-aur listos.",
    ),
    (
        "03_cooperacion.png",
        "Hecho en comunidad",
        "Compartiendo conocimiento, tutoriales y utilidades abiertas para quienes aprenden y usan Linux.",
    ),
    (
        "04_comunidad_neon.png",
        "Sinergia Comunidad Linuxera",
        "Un espacio colaborativo para resolver dudas, probar herramientas y crecer juntos en GNU/Linux.",
    ),
    (
        "05_emblema.png",
        "Preparando tu nuevo sistema",
        "Particionando, copiando el sistema base, configurando el usuario y preparando el gestor de arranque.",
    ),
]


class ProgressPage(QWidget):
    install_finished = pyqtSignal(bool, str)

    def __init__(self, config: InstallConfig, engine: InstallerEngine) -> None:
        super().__init__()
        self.config = config
        self.engine = engine
        self._running = False
        self._slides: list[tuple[QPixmap, str, str]] = []
        self._slide_idx = 0
        self._load_slides()
        self._build_ui()
        self._connect_signals()
        self._slide_timer = QTimer(self)
        self._slide_timer.setInterval(5000)
        self._slide_timer.timeout.connect(self._next_slide)

    def _load_slides(self) -> None:
        assets_dir = Path(__file__).resolve().parent.parent / "assets" / "slides"
        for filename, title, caption in SLIDES_METADATA:
            p = assets_dir / filename
            if p.is_file():
                pm = QPixmap(str(p))
                if not pm.isNull():
                    self._slides.append((pm, title, caption))

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self.lbl_status = QLabel("Preparando instalación...")
        self.lbl_status.setStyleSheet("font-weight: bold; font-size: 11pt;")
        layout.addWidget(self.lbl_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.showcase_frame = QFrame()
        self.showcase_frame.setStyleSheet(
            "QFrame { background-color: #171d2a; border: 1px solid #2b354a; border-radius: 10px; }"
        )
        s_lay = QVBoxLayout(self.showcase_frame)
        s_lay.setContentsMargins(14, 12, 14, 12)
        s_lay.setSpacing(8)

        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumHeight(200)
        self.lbl_image.setStyleSheet("border: none; background: transparent;")
        s_lay.addWidget(self.lbl_image, stretch=1)

        self.lbl_slide_title = QLabel()
        self.lbl_slide_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_slide_title.setStyleSheet(
            "font-weight: bold; font-size: 11pt; color: #38bdf8; border: none; background: transparent;"
        )
        s_lay.addWidget(self.lbl_slide_title)

        self.lbl_slide_caption = QLabel()
        self.lbl_slide_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_slide_caption.setWordWrap(True)
        self.lbl_slide_caption.setStyleSheet("color: #cbd5e1; border: none; background: transparent;")
        s_lay.addWidget(self.lbl_slide_caption)

        nav = QHBoxLayout()
        self.btn_prev_slide = QPushButton("◀ Anterior")
        self.btn_prev_slide.clicked.connect(self._prev_slide)
        self.lbl_slide_counter = QLabel()
        self.lbl_slide_counter.setStyleSheet("color: #94a3b8; border: none; background: transparent;")
        self.btn_next_slide = QPushButton("Siguiente ▶")
        self.btn_next_slide.clicked.connect(self._next_slide)
        nav.addWidget(self.btn_prev_slide)
        nav.addStretch()
        nav.addWidget(self.lbl_slide_counter)
        nav.addStretch()
        nav.addWidget(self.btn_next_slide)
        s_lay.addLayout(nav)
        layout.addWidget(self.showcase_frame, stretch=1)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMinimumHeight(140)
        self.txt_log.setVisible(False)
        layout.addWidget(self.txt_log)

        actions = QHBoxLayout()
        self.btn_toggle_log = QPushButton("Ver pasos")
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.toggled.connect(self._on_toggle_log)
        actions.addWidget(self.btn_toggle_log)
        actions.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._on_cancel)
        actions.addWidget(self.btn_cancel)
        layout.addLayout(actions)
        self._render_slide()

    def _connect_signals(self) -> None:
        self.engine.step_changed.connect(self._on_step_changed)
        self.engine.log_line.connect(self._on_log_line)
        self.engine.finished_install.connect(self._on_finished)

    def _on_toggle_log(self, checked: bool) -> None:
        self.txt_log.setVisible(checked)
        self.btn_toggle_log.setText("Ocultar pasos" if checked else "Ver pasos")
        if checked:
            sb = self.txt_log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _render_slide(self) -> None:
        if not self._slides:
            self.lbl_slide_title.setText("Sinergia Linux")
            self.lbl_slide_caption.setText("Instalando el sistema en el disco seleccionado...")
            self.lbl_slide_counter.setText("")
            self.btn_prev_slide.setEnabled(False)
            self.btn_next_slide.setEnabled(False)
            return
        pm, title, caption = self._slides[self._slide_idx]
        w = max(320, self.lbl_image.width() if self.lbl_image.width() > 50 else 680)
        h = max(160, self.lbl_image.height() if self.lbl_image.height() > 50 else 200)
        self.lbl_image.setPixmap(
            pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )
        self.lbl_slide_title.setText(title)
        self.lbl_slide_caption.setText(caption)
        self.lbl_slide_counter.setText(f"{self._slide_idx + 1} / {len(self._slides)}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_slide()

    def _next_slide(self) -> None:
        if self._slides:
            self._slide_idx = (self._slide_idx + 1) % len(self._slides)
            self._render_slide()

    def _prev_slide(self) -> None:
        if self._slides:
            self._slide_idx = (self._slide_idx - 1) % len(self._slides)
            self._render_slide()

    def start_installation(self) -> None:
        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Iniciando...")
        self._running = True
        self.btn_cancel.setEnabled(True)
        self._slide_idx = 0
        self._render_slide()
        if self._slides:
            self._slide_timer.start()
        self.engine.start(self.config)

    def _on_cancel(self) -> None:
        if self._running:
            self.lbl_status.setText("Cancelando...")
            self.btn_cancel.setEnabled(False)
            self.engine.cancel()

    def _on_step_changed(self, current: int, total: int, label: str) -> None:
        self.lbl_status.setText(f"Paso {current} de {total}: {label}")
        if total > 0:
            self.progress_bar.setValue(int(((current - 1) / total) * 100))

    def _on_log_line(self, line: str) -> None:
        self.txt_log.appendPlainText(line)
        if self.txt_log.isVisible():
            sb = self.txt_log.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _on_finished(self, ok: bool, message: str) -> None:
        self._running = False
        self._slide_timer.stop()
        self.btn_cancel.setEnabled(False)
        if ok:
            self.progress_bar.setValue(100)
            self.lbl_status.setText(f"Listo: {message}")
        else:
            self.lbl_status.setText(f"Detenido: {message}")
        self.install_finished.emit(ok, message)
