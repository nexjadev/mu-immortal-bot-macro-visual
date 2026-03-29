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
        
        # Depuración: Mostrar información en consola
        print(f"[MatchTemplate] Template: {Path(template_path).name} | "
              f"Threshold: {threshold:.2f} | Match: {max_val:.4f} | "
              f"Found: {'YES' if max_val >= threshold else 'NO'}")

        return bool(max_val >= threshold)

    def find_color(
        self,
        frame: Image.Image,
        roi: dict,
        target_color: list[int],
        tolerance: int,
        min_ratio: float = 0.05,
    ) -> bool:
        """Busca un color objetivo dentro del ROI del fotograma.

        Recorre todos los píxeles del recorte y comprueba si cada uno
        está dentro de ``tolerance`` en los tres canales RGB.  Retorna
        ``True`` solo cuando la fracción de píxeles coincidentes es
        mayor o igual a ``min_ratio``.

        Args:
            frame:        Fotograma completo (PIL.Image en modo RGB).
            roi:          Dict ``{"x", "y", "w", "h"}`` en píxeles.
            target_color: Lista ``[R, G, B]`` con valores en [0, 255].
            tolerance:    Máxima diferencia permitida por canal (0-255).
            min_ratio:    Fracción mínima de píxeles coincidentes para
                          considerar el color presente (0.0-1.0).
                          Por defecto 0.05 (5 %).

        Returns:
            ``True`` si la proporción de píxeles coincidentes >= min_ratio.

        Raises:
            ValueError: Si ``tolerance`` no está en [0, 255], si
                        ``min_ratio`` no está en [0.0, 1.0], o si
                        ``target_color`` no es una lista de 3 ints
                        en [0, 255].
        """
        if not (0 <= tolerance <= 255):
            raise ValueError(
                f"tolerance debe estar en [0, 255], recibido: {tolerance}"
            )
        if not (0.0 <= min_ratio <= 1.0):
            raise ValueError(
                f"min_ratio debe estar en [0.0, 1.0], recibido: {min_ratio}"
            )
        if (
            not isinstance(target_color, (list, tuple))
            or len(target_color) != 3
            or not all(isinstance(c, int) and 0 <= c <= 255 for c in target_color)
        ):
            raise ValueError(
                "target_color debe ser una lista de 3 enteros en [0, 255]"
            )

        import numpy as np  # lazy: no rompe entornos sin numpy

        frame_np = np.array(frame.convert("RGB"), dtype=np.int16)
        crop = frame_np[
            roi["y"] : roi["y"] + roi["h"],
            roi["x"] : roi["x"] + roi["w"],
        ]

        tc = np.array(target_color, dtype=np.int16)
        diff = np.abs(crop - tc)                          # (h, w, 3)
        matches = np.all(diff <= tolerance, axis=2)       # (h, w) bool
        total_px = matches.size
        matched_px = int(np.sum(matches))
        ratio = matched_px / total_px if total_px > 0 else 0.0
        found = ratio >= min_ratio

        print(
            f"[FindColor] target={target_color} tol={tolerance} "
            f"min_ratio={min_ratio:.2f} | matched={matched_px}/{total_px} "
            f"({ratio:.3f}) | Found: {'YES' if found else 'NO'}"
        )
        return found

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
