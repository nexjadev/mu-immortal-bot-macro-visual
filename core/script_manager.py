"""script_manager.py — Lectura, escritura y validacion de scripts JSON para mu-immortal-bot-macro-visual.

Unico modulo autorizado para leer/escribir archivos JSON de scripts y perfiles.
No usa print() ni logging — comunica errores exclusivamente via excepciones.
"""

import json
import os
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Excepciones personalizadas
# ---------------------------------------------------------------------------

class ScriptNotFoundError(Exception):
    """Raised when the script JSON file does not exist at the given path.

    Attributes:
        path: The file path that was not found.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Script not found: {path}")


class ScriptValidationError(Exception):
    """Raised when the script JSON is missing a required field or has an invalid value.

    Attributes:
        field: Dot-notation field identifier where validation failed.
        msg:   Human-readable description of the validation failure.
    """

    def __init__(self, field: str, msg: str) -> None:
        self.field = field
        self.msg = msg
        super().__init__(f"[{field}] {msg}")


# ---------------------------------------------------------------------------
# ScriptManager
# ---------------------------------------------------------------------------

class ScriptManager:
    """Manages loading, saving, and validating bot script JSON files.

    Also handles CRUD operations for emulator profiles stored in
    ``config/profiles.json``.

    Class Attributes:
        VALID_CLICK_TYPES: Set of accepted values for ``click_type`` in actions.
    """

    VALID_CLICK_TYPES: set[str] = {"single", "double", "long_press"}

    # ------------------------------------------------------------------
    # Script I/O
    # ------------------------------------------------------------------

    def load(self, path: str) -> dict:
        """Load and validate a script JSON file.

        Args:
            path: Filesystem path to the script ``.json`` file.

        Returns:
            Validated script dict.

        Raises:
            ScriptNotFoundError: If the file does not exist.
            ScriptValidationError: If the script fails schema validation.
            json.JSONDecodeError: If the file content is not valid JSON.
        """
        p = Path(path)
        if not p.is_file():
            raise ScriptNotFoundError(path)

        raw = p.read_text(encoding="utf-8")
        script: dict = json.loads(raw)
        self.validate(script)
        return script

    def save(self, script: dict, path: str) -> None:
        """Persist a script dict to disk as formatted JSON.

        Updates ``script["meta"]["created_at"]`` with the current local
        datetime before writing.

        Args:
            script: Script dict to persist. Must contain a ``"meta"`` key.
            path:   Destination filesystem path for the ``.json`` file.
        """
        script["meta"]["created_at"] = datetime.now().isoformat(
            sep=" ", timespec="seconds"
        )

        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps(script, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, script: dict) -> None:
        """Validate a script dict against the required schema.

        Checks are performed in a defined order; the first failure raises
        ``ScriptValidationError`` immediately.

        Args:
            script: Dict parsed from a script JSON file.

        Raises:
            ScriptValidationError: On the first schema violation found.
        """
        # 1. Top-level required keys
        for key in ("meta", "emulator", "actions", "cycle_delay"):
            if key not in script:
                raise ScriptValidationError(key, "campo requerido ausente")

        meta = script["meta"]
        emulator = script["emulator"]

        # 2. meta.name — str no vacio
        if not isinstance(meta.get("name"), str) or not meta["name"].strip():
            raise ScriptValidationError("meta.name", "campo requerido ausente")

        # 3. meta.resolution
        resolution = meta.get("resolution")
        if not isinstance(resolution, dict):
            raise ScriptValidationError("meta.resolution", "campo requerido ausente")
        for dim in ("width", "height"):
            val = resolution.get(dim)
            if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                raise ScriptValidationError(
                    f"meta.resolution.{dim}", "debe ser int > 0"
                )

        # 4. meta.version — str
        if not isinstance(meta.get("version"), str):
            raise ScriptValidationError("meta.version", "campo requerido ausente")

        # 5. emulator.host — str
        if not isinstance(emulator.get("host"), str):
            raise ScriptValidationError("emulator.host", "campo requerido ausente")

        # 6. emulator.port — int entre 1 y 65535
        port = emulator.get("port")
        if isinstance(port, bool) or not isinstance(port, int) or not (1 <= port <= 65535):
            raise ScriptValidationError("emulator.port", "debe ser int entre 1 y 65535")

        # 7. emulator.window_title — str
        if not isinstance(emulator.get("window_title"), str):
            raise ScriptValidationError(
                "emulator.window_title", "campo requerido ausente"
            )

        # 8. cycle_delay — int >= 0
        cycle_delay = script.get("cycle_delay")
        if isinstance(cycle_delay, bool) or not isinstance(cycle_delay, int) or cycle_delay < 0:
            raise ScriptValidationError("cycle_delay", "debe ser int >= 0")

        # 9. actions — lista no vacia
        actions = script["actions"]
        if not isinstance(actions, list) or len(actions) == 0:
            raise ScriptValidationError("actions", "debe ser una lista no vacia")

        # 10. Validacion por accion
        for i, action in enumerate(actions):
            prefix = f"actions[{i}]"

            # id — str no vacio
            if not isinstance(action.get("id"), str) or not action["id"].strip():
                raise ScriptValidationError(f"{prefix}.id", "campo requerido ausente")

            # name — str no vacio
            if not isinstance(action.get("name"), str) or not action["name"].strip():
                raise ScriptValidationError(f"{prefix}.name", "campo requerido ausente")

            # enabled — bool (verificar ANTES de int porque bool es subclase de int)
            if not isinstance(action.get("enabled"), bool):
                raise ScriptValidationError(
                    f"{prefix}.enabled", "debe ser bool"
                )

            # roi — dict existente
            roi = action.get("roi")
            if not isinstance(roi, dict):
                raise ScriptValidationError(f"{prefix}.roi", "campo requerido ausente")

            # roi.x — int >= 0
            roi_x = roi.get("x")
            if isinstance(roi_x, bool) or not isinstance(roi_x, int) or roi_x < 0:
                raise ScriptValidationError(f"{prefix}.roi.x", "debe ser int >= 0")

            # roi.y — int >= 0
            roi_y = roi.get("y")
            if isinstance(roi_y, bool) or not isinstance(roi_y, int) or roi_y < 0:
                raise ScriptValidationError(f"{prefix}.roi.y", "debe ser int >= 0")

            # roi.w — int > 0
            roi_w = roi.get("w")
            if isinstance(roi_w, bool) or not isinstance(roi_w, int) or roi_w <= 0:
                raise ScriptValidationError(f"{prefix}.roi.w", "debe ser int > 0")

            # roi.h — int > 0
            roi_h = roi.get("h")
            if isinstance(roi_h, bool) or not isinstance(roi_h, int) or roi_h <= 0:
                raise ScriptValidationError(f"{prefix}.roi.h", "debe ser int > 0")

            # click_type — valor en VALID_CLICK_TYPES
            if action.get("click_type") not in self.VALID_CLICK_TYPES:
                raise ScriptValidationError(
                    f"{prefix}.click_type",
                    "debe ser single|double|long_press",
                )

            # delay_before — int >= 0
            delay_before = action.get("delay_before")
            if (
                isinstance(delay_before, bool)
                or not isinstance(delay_before, int)
                or delay_before < 0
            ):
                raise ScriptValidationError(
                    f"{prefix}.delay_before", "debe ser int >= 0"
                )

            # delay_after — int >= 0
            delay_after = action.get("delay_after")
            if (
                isinstance(delay_after, bool)
                or not isinstance(delay_after, int)
                or delay_after < 0
            ):
                raise ScriptValidationError(
                    f"{prefix}.delay_after", "debe ser int >= 0"
                )

            # on_error — str no vacio
            on_error = action.get("on_error")
            if not isinstance(on_error, str) or not on_error.strip():
                raise ScriptValidationError(
                    f"{prefix}.on_error", "campo requerido ausente"
                )

    # ------------------------------------------------------------------
    # Profile I/O
    # ------------------------------------------------------------------

    def load_profiles(self) -> list:
        """Load emulator profiles from ``config/profiles.json``.

        Returns:
            List of profile dicts. Returns an empty list if the file does
            not exist or its content is not a JSON array.
        """
        profiles_path = Path("config/profiles.json")
        if not profiles_path.is_file():
            return []

        raw = profiles_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return data

    def save_profile(self, profile: dict) -> None:
        """Persist an emulator profile, creating or updating by name.

        If a profile with the same ``name`` already exists it is replaced
        in-place; otherwise the new profile is appended.

        Args:
            profile: Dict with keys ``name``, ``host``, ``port``, ``window_title``.
        """
        profiles = self.load_profiles()

        replaced = False
        for idx, existing in enumerate(profiles):
            if existing.get("name") == profile.get("name"):
                profiles[idx] = profile
                replaced = True
                break

        if not replaced:
            profiles.append(profile)

        Path("config").mkdir(exist_ok=True)
        Path("config/profiles.json").write_text(
            json.dumps(profiles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def delete_profile(self, name: str) -> None:
        """Remove an emulator profile by name.

        If no profile with the given name exists the operation is a no-op.

        Args:
            name: The ``name`` value of the profile to remove.
        """
        profiles = self.load_profiles()
        updated = [p for p in profiles if p.get("name") != name]
        Path("config/profiles.json").write_text(
            json.dumps(updated, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
