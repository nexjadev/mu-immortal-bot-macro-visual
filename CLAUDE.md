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

"emulator": { "host": "127.0.0.1", "port": 5555, "window_title": "" },

"actions": [

{ "id": "", "name": "", "enabled": true,

"roi": {"x": 0, "y": 0, "w": 100, "h": 50},

"click_type": "single", "delay_before": 100,

"delay_after": 200, "on_error": "stop" }

],

"cycle_delay": 500

}

## Formato de log

Archivo: logs/session_YYYYMMDD_HHMMSS.log
Cada sesión empieza y termina con separador de 80 '='.
Niveles: DEBUG / INFO / ACTION (custom, valor 25) / WARN / ERROR
