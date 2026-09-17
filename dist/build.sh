#!/usr/bin/env bash
set -e

# ==============================================================================
# VW Builder - Generador de Ejecutable para Linux y macOS
# Video Workstation (VW)
# Desarrollado por Gabriel Giraldo & Jorge Nieto
# ==============================================================================

# Resolver rutas relativas al script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "======================================================="
echo "   VW Builder - Generador de Ejecutable (Linux / macOS)"
echo "======================================================="

# 1. Detectar si existe un entorno virtual creado en la raíz del proyecto
PYTHON_BIN=""

if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/venv/bin/python"
    echo "[*] Entorno virtual detectado en venv/"
elif [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
    echo "[*] Entorno virtual detectado en .venv/"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] No se encontro Python en el sistema."
    echo "Por favor instala Python 3.10+ para continuar."
    exit 1
fi

# 2. Ejecutar el script orquestador de compilación en Python
"$PYTHON_BIN" "$SCRIPT_DIR/build.py" "$@"

echo ""
echo "Proceso finalizado con exito."
