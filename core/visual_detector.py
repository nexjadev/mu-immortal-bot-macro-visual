"""
core/visual_detector.py
=======================
Captura de pantalla (v1) y detección visual (v2, pendiente).

v1 — disponible: get_frame()
v2 — estructura documentada, sin implementar: check_condition(),
     find_template(), detect_color_change()
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from core.adb_controller import ADBController


class VisualDetector:
    """
    Provee captura de fotogramas del emulador (v1) y una interfaz
    preparada para detección visual basada en condiciones (v2).

    Uso v1::

        detector = VisualDetector()
        frame = detector.get_frame(adb)   # PIL.Image

    Uso v2 (pendiente)::

        ok = detector.check_condition(frame, condition_dict)
    """

    # ------------------------------------------------------------------
    # v1 — Captura
    # ------------------------------------------------------------------

    def get_frame(self, adb: ADBController) -> Image.Image:
        """Captura el fotograma actual del emulador y lo retorna como imagen.

        Delega en ``ADBController.screenshot()``, que usa
        ``adb exec-out screencap -p`` para transferir los píxeles en binario
        sin escribir archivos intermedios en el dispositivo.

        Args:
            adb: Instancia de ``ADBController`` ya conectada al emulador.

        Returns:
            Objeto ``PIL.Image.Image`` en modo RGB con el contenido actual
            de la pantalla del emulador.

        Raises:
            ADBCommandError: Si el comando ADB falla o retorna código != 0.
            ADBConnectionError: Si el dispositivo no está disponible.
        """
        return adb.screenshot()

    # ------------------------------------------------------------------
    # v2 — Detección visual (pendiente)
    # ------------------------------------------------------------------

    def check_condition(self, frame: Image.Image, condition: dict) -> bool:
        """Evalúa una condición visual sobre el fotograma dado.

        Despacha al método de detección adecuado según
        ``condition["method"]``:

        - ``"template_match"`` → :meth:`find_template`
        - ``"color_change"``   → :meth:`detect_color_change`
        - ``"pixel_value"``    → comparación directa del valor RGBA de un
          píxel central del ROI contra un color de referencia.

        Esquema del dict ``condition``::

            {
                "roi": {"x": int, "y": int, "w": int, "h": int},
                "method": "template_match" | "color_change" | "pixel_value",
                "template": "ruta/template.png",   # solo para template_match
                "threshold": 0.0–1.0,
                "on_match":    "execute" | "skip",
                "on_no_match": "execute" | "skip" | "stop"
            }

        Args:
            frame:     Fotograma capturado con :meth:`get_frame`.
            condition: Dict con los campos descritos arriba.

        Returns:
            ``True`` si la condición se cumple, ``False`` en caso contrario.

        Raises:
            NotImplementedError: Siempre (v2 pendiente).
            ValueError: (v2) Si ``condition["method"]`` no es un valor válido.
        """
        raise NotImplementedError("v2 - pendiente")

    def find_template(
        self,
        frame: Image.Image,
        template_path: str,
        roi: dict,
        threshold: float,
    ) -> bool:
        """Busca una imagen plantilla dentro del ROI del fotograma.

        Previsto para usar ``cv2.matchTemplate`` con el método
        ``TM_CCOEFF_NORMED``.  El score máximo de coincidencia se compara
        contra ``threshold``; si es mayor o igual se retorna ``True``.

        Flujo esperado (v2):

        1. Recortar ``frame`` al rectángulo ``roi``.
        2. Cargar ``template_path`` como imagen en escala de grises.
        3. Ejecutar ``cv2.matchTemplate(crop_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)``.
        4. Obtener ``max_val`` con ``cv2.minMaxLoc``.
        5. Retornar ``max_val >= threshold``.

        Args:
            frame:         Fotograma completo (PIL.Image).
            template_path: Ruta al archivo PNG de la plantilla.
            roi:           Dict ``{"x", "y", "w", "h"}`` en píxeles de imagen.
            threshold:     Valor de coincidencia mínimo en el rango [0.0, 1.0].

        Returns:
            ``True`` si se encontró la plantilla con score >= threshold.

        Raises:
            FileNotFoundError: Si ``template_path`` no existe.
            ValueError:        Si ``threshold`` no está en [0.0, 1.0].
        """
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(
                f"threshold debe estar en [0.0, 1.0], recibido: {threshold}"
            )
        if not Path(template_path).is_file():
            raise FileNotFoundError(f"Template no encontrado: {template_path}")

        import cv2          # lazy: no rompe entornos sin cv2
        import numpy as np

        frame_np = cv2.cvtColor(
            np.array(frame.convert("RGB")), cv2.COLOR_RGB2BGR
        )
        crop = frame_np[
            roi["y"] : roi["y"] + roi["h"],
            roi["x"] : roi["x"] + roi["w"],
        ]
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        tpl = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
        if tpl is None:
            raise FileNotFoundError(f"cv2 no pudo leer: {template_path}")

        # Template más grande que el ROI → imposible encontrar
        if tpl.shape[0] > crop_gray.shape[0] or tpl.shape[1] > crop_gray.shape[1]:
            return False

        result = cv2.matchTemplate(crop_gray, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return bool(max_val >= threshold)

    def detect_color_change(
        self,
        frame: Image.Image,
        roi: dict,
        baseline: Image.Image,
        threshold: float,
    ) -> bool:
        """Detecta si el color medio del ROI cambió respecto a una imagen base.

        Compara el color promedio (R, G, B) del área ``roi`` en ``frame``
        contra el color promedio de la misma área en ``baseline``.  Si la
        distancia euclidiana normalizada supera ``threshold``, retorna ``True``.

        Flujo esperado (v2):

        1. Recortar ``frame`` y ``baseline`` al rectángulo ``roi``.
        2. Calcular el color medio de cada recorte con
           ``ImageStat.Stat(crop).mean[:3]``.
        3. Calcular distancia euclidiana entre los dos vectores RGB.
        4. Normalizar al rango [0, 1] dividiendo por ``sqrt(3) * 255``.
        5. Retornar ``distancia_normalizada >= threshold``.

        Args:
            frame:     Fotograma actual (PIL.Image).
            roi:       Dict ``{"x", "y", "w", "h"}`` en píxeles de imagen.
            baseline:  Fotograma de referencia capturado previamente.
            threshold: Umbral de cambio en el rango [0.0, 1.0].

        Returns:
            ``True`` si el cambio de color supera el umbral.

        Raises:
            NotImplementedError: Siempre (v2 pendiente).
            ValueError:          (v2) Si ``baseline`` tiene dimensiones distintas
                                 a ``frame``.
        """
        raise NotImplementedError("v2 - pendiente")
