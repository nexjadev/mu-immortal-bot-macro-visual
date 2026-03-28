# CLAUDE.md — mu-immortal-bot-macro-visual

## Qué es este proyecto
Bot de automatización para MU Online que ejecuta secuencias de clics
definidas sobre ROIs (zonas rectangulares) en un emulador Android.
Controlado via ADB. UI en PyQt6. Scripts persistidos en JSON.

## Stack
- Python 3.10+
- PyQt6 (UI exclusivamente)
- ADB (control del emulador)
- Pillow + OpenCV (captura e imágenes)
- JSON (persistencia de scripts)

## Estructura de módulos

core/
  adb_controller.py   → ÚNICO punto de contacto con ADB
  bot_engine.py       → bucle de ejecución, lógica de clics
  script_manager.py   → lectura/escritura de JSON, validación
  logger.py           → logging centralizado, sesiones
  orchestrator.py     → coordina todo, no tiene lógica propia
  visual_detector.py  → captura (v1), detección visual (v2)

ui/
  main_window.py      → QMainWindow principal
  roi_canvas.py       → canvas con dibujo de ROIs
  action_panel.py     → sidebar de configuración
  dialogs.py          → diálogos de acción

scripts/              → archivos .json de scripts de usuario
logs/                 → archivos .log por sesión
config/
  profiles.json       → perfiles de emulador guardados

## Reglas CRÍTICAS

1. La UI (ui/) NUNCA importa core/ directamente.
   Todo pasa por señales PyQt6 hacia el Orchestrator.
2. Solo adb_controller.py ejecuta comandos ADB.
3. Solo script_manager.py lee/escribe archivos JSON de scripts.
4. Todo logging va por BotLogger. NUNCA usar print() en producción.
5. Cada módulo tiene su propio archivo. No mezclar responsabilidades.
6. Resolución del emulador debe coincidir con la del script.
   Si difiere → advertir y detener, NO escalar silenciosamente.
7. Cualquier error NO controlado detiene el bot y se loggea con ERROR + traceback.

## Orden de desarrollo

Fase 1: logger.py → script_manager.py → adb_controller.py
Fase 2: bot_engine.py
Fase 3: ui/ (main_window, roi_canvas, action_panel, dialogs)
Fase 4: orchestrator.py (integración final)
Fase 5: visual_detector.py v2 (backlog)

## Formato del script JSON
{

"meta": { "name": "", "resolution": {"width": 1280, "height": 720},

"created_at": "", "version": "1.0" },

"emulator": { "host": "127.0.0.1", "port": 5555 },

"actions": [

{ "id": "", "name": "", "enabled": true,

"roi": {"x": 0, "y": 0, "w": 100, "h": 50},

"click_type": "single", "delay_before": 100,

"delay_after": 200, "on_error": "stop" }

],

"cycle_delay": 500

}

## Reglas de pruebas (OBLIGATORIO)

8. Toda funcionalidad de `core/` debe tener pruebas funcionales en `tests/`.
   No basta con pruebas unitarias con mocks: debe existir al menos un test
   que verifique el comportamiento real de extremo a extremo (I/O incluido).

9. Cobertura mínima por área:
   - **Guardado/carga de scripts**: crear archivo, verificar contenido, sobrescribir.
   - **Flujos del Orchestrator**: cada método público con resultado observable.
   - **Validación de datos**: campos requeridos, tipos incorrectos, valores límite.
   - **Manejo de errores**: cada `return False` / excepción debe tener un test
     que confirme que el fallo es visible (no silencioso).

10. Antes de declarar un bug como resuelto, agregar un test que lo reproduzca
    y verifique el fix. Si el test no existía antes, el bug era prevenible.

11. Ejecutar la suite completa con:
    ```
    python -m unittest discover -s tests -v
    ```
    Debe terminar con `OK` (o `OK (skipped=N)` solo para tests que requieren
    hardware externo como Pillow/ADB). Ningún ERROR ni FAIL es aceptable.

12. Para dependencias de runtime opcionales (PIL, ADB), mockear con
    `sys.modules` al inicio del archivo de test, antes de cualquier import
    de `core/`. Los tests que requieran la dependencia real deben usar
    `@unittest.skipUnless` con mensaje explicativo.

## Formato de log

Archivo: logs/session_YYYYMMDD_HHMMSS.log
Cada sesión empieza y termina con separador de 80 '='.
Niveles: DEBUG / INFO / ACTION (custom, valor 25) / WARN / ERROR
