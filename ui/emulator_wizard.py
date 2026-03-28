"""
ui/emulator_wizard.py
=====================
Wizard de configuración de emulador que se muestra antes de la ventana principal.
Permite seleccionar un dispositivo ADB detectado, un perfil guardado, o ingresar
los datos de conexión manualmente.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from core.adb_controller import ADBController
from core.script_manager import ScriptManager

_PAGE_SELECTION = 0
_PAGE_MANUAL = 1


# ---------------------------------------------------------------------------
# Página 1: Selección de dispositivo o perfil
# ---------------------------------------------------------------------------

class _SelectionPage(QWizardPage):
    def __init__(self, script_manager: ScriptManager, parent: QWizard | None = None) -> None:
        super().__init__(parent)
        self._sm = script_manager
        self._use_manual = False
        self.setTitle("Seleccionar emulador")
        self.setSubTitle("Elige un dispositivo detectado, un perfil guardado, o ingresa los datos manualmente.")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- Dispositivos detectados ---
        layout.addWidget(QLabel("Dispositivos detectados:"))
        self._device_list = QListWidget()
        self._device_list.setMaximumHeight(120)
        layout.addWidget(self._device_list)

        btn_detect = QPushButton("Detectar / Actualizar")
        btn_detect.clicked.connect(self._refresh_devices)
        layout.addWidget(btn_detect)

        # --- Separador ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # --- Perfiles guardados ---
        layout.addWidget(QLabel("Perfiles guardados:"))
        self._profile_list = QListWidget()
        self._profile_list.setMaximumHeight(120)
        layout.addWidget(self._profile_list)

        btn_row = QHBoxLayout()
        self._btn_delete = QPushButton("Eliminar perfil")
        self._btn_delete.clicked.connect(self._delete_selected_profile)
        btn_row.addWidget(self._btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # --- Separador ---
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        # --- Botón conexión manual ---
        btn_manual = QPushButton("Nueva conexión manual →")
        btn_manual.clicked.connect(self._on_manual_clicked)
        layout.addWidget(btn_manual)

        # Conexiones de selección mutua excluyente
        self._device_list.currentItemChanged.connect(self._on_device_selected)
        self._profile_list.currentItemChanged.connect(self._on_profile_selected)

    def initializePage(self) -> None:
        self._use_manual = False
        self._refresh_devices()
        self._load_profiles()

    def isComplete(self) -> bool:
        return True

    def nextId(self) -> int:
        if self._use_manual:
            return _PAGE_MANUAL
        return -1

    # ------------------------------------------------------------------
    # Slots privados
    # ------------------------------------------------------------------

    def _refresh_devices(self) -> None:
        self._device_list.clear()
        devices = ADBController.list_devices()
        if not devices:
            item = QListWidgetItem("(ninguno detectado)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._device_list.addItem(item)
            return
        for dev in devices:
            label = f"{dev['serial']}  ({dev['host']}:{dev['port']})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, dev)
            self._device_list.addItem(item)

    def _load_profiles(self) -> None:
        self._profile_list.clear()
        profiles = self._sm.load_profiles()
        if not profiles:
            item = QListWidgetItem("(sin perfiles guardados)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._profile_list.addItem(item)
            return
        for prof in profiles:
            label = f"{prof['name']}  ({prof['host']}:{prof['port']})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, prof)
            self._profile_list.addItem(item)

    def _on_device_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        self._profile_list.clearSelection()
        self._profile_list.setCurrentItem(None)
        wizard = self.wizard()
        if wizard is not None:
            wizard._pending_result = {
                "host": data["host"],
                "port": data["port"],
            }

    def _on_profile_selected(self, current: QListWidgetItem | None, _prev) -> None:
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        self._device_list.clearSelection()
        self._device_list.setCurrentItem(None)
        wizard = self.wizard()
        if wizard is not None:
            wizard._pending_result = {
                "host": data.get("host", "127.0.0.1"),
                "port": data.get("port", 5555),
            }

    def _delete_selected_profile(self) -> None:
        item = self._profile_list.currentItem()
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if data is None:
            return
        self._sm.delete_profile(data["name"])
        wizard = self.wizard()
        if wizard is not None and wizard._pending_result == {
            "host": data.get("host"),
            "port": data.get("port"),
        }:
            wizard._pending_result = None
        self._load_profiles()

    def _on_manual_clicked(self) -> None:
        self._use_manual = True
        self.wizard().next()


# ---------------------------------------------------------------------------
# Página 2: Entrada manual de host/puerto/título
# ---------------------------------------------------------------------------

class _ManualPage(QWizardPage):
    def __init__(self, script_manager: ScriptManager, parent: QWizard | None = None) -> None:
        super().__init__(parent)
        self._sm = script_manager
        self.setTitle("Configurar conexión manualmente")
        self.setSubTitle("Ingresa los datos de conexión al emulador.")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._host = QLineEdit("127.0.0.1")
        self._host.setPlaceholderText("127.0.0.1")
        form.addRow("Host:", self._host)

        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(5555)
        form.addRow("Puerto:", self._port)

        layout.addLayout(form)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        self._save_cb = QCheckBox("Guardar como perfil")
        layout.addWidget(self._save_cb)

        self._profile_name = QLineEdit()
        self._profile_name.setPlaceholderText("Nombre del perfil")
        self._profile_name.setVisible(False)
        layout.addWidget(self._profile_name)

        layout.addStretch()

        # Conectar cambios para actualizar isComplete
        self._host.textChanged.connect(self.completeChanged)
        self._save_cb.stateChanged.connect(self._on_save_toggled)
        self._profile_name.textChanged.connect(self.completeChanged)

    def initializePage(self) -> None:
        wizard = self.wizard()
        if wizard is not None and wizard._pending_result:
            result = wizard._pending_result
            self._host.setText(result.get("host", "127.0.0.1"))
            self._port.setValue(result.get("port", 5555))

    def isComplete(self) -> bool:
        host_ok = bool(self._host.text().strip())
        name_ok = (not self._save_cb.isChecked()) or bool(self._profile_name.text().strip())
        return host_ok and name_ok

    def validatePage(self) -> bool:
        result = {
            "host": self._host.text().strip(),
            "port": self._port.value(),
        }
        wizard = self.wizard()
        if wizard is not None:
            wizard._pending_result = result
        if self._save_cb.isChecked():
            profile = {
                "name": self._profile_name.text().strip(),
                "host": result["host"],
                "port": result["port"],
            }
            self._sm.save_profile(profile)
        return True

    def nextId(self) -> int:
        return -1

    def _on_save_toggled(self, state: int) -> None:
        self._profile_name.setVisible(bool(state))
        self.completeChanged.emit()


# ---------------------------------------------------------------------------
# Wizard principal
# ---------------------------------------------------------------------------

class EmulatorWizard(QWizard):
    """Wizard de configuración de emulador.

    Muestra páginas para seleccionar un dispositivo ADB detectado, un perfil
    guardado, o ingresar datos manualmente. El resultado se obtiene mediante
    ``get_result()`` tras llamar a ``exec()``.

    Args:
        script_manager: Instancia de ScriptManager para cargar/guardar perfiles.
        parent: Widget padre opcional.
    """

    def __init__(self, script_manager: ScriptManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurar emulador")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(500, 480)
        self._pending_result: dict | None = None

        self._sel_page = _SelectionPage(script_manager, self)
        self._man_page = _ManualPage(script_manager, self)

        self.setPage(_PAGE_SELECTION, self._sel_page)
        self.setPage(_PAGE_MANUAL, self._man_page)
        self.setStartId(_PAGE_SELECTION)

    def get_result(self) -> dict | None:
        """Retorna los datos de conexión elegidos por el usuario.

        Returns:
            Dict con claves ``host`` (str), ``port`` (int),
            o ``None`` si el wizard fue cancelado.
        """
        if self.result() == QDialog.DialogCode.Rejected:
            return None
        return self._pending_result

    def reject(self) -> None:
        self._pending_result = None
        super().reject()
