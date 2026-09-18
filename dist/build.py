import os
import sys
import re
import shutil
import subprocess
import importlib.util

def is_in_venv():
    """Detecta si el script se esta ejecutando dentro de un entorno virtual."""
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def get_missing_dependencies():
    """Comprueba si PyInstaller esta instalado sin cargarlo en memoria."""
    required = {
        "PyInstaller": "pyinstaller",
    }
    missing = []
    for mod_name, pkg_name in required.items():
        if importlib.util.find_spec(mod_name) is None:
            missing.append(pkg_name)
    return missing

def verify_and_handle_dependencies(auto_confirm=False):
    """Verifica dependencias de compilacion aplicando buenas practicas con entornos virtuales."""
    missing = get_missing_dependencies()
    
    if not missing:
        print("[OK] Herramienta de compilacion (PyInstaller) disponible.")
        return

    in_venv = is_in_venv()
    print("\n[!] Se detectaron herramientas faltantes para compilar el proyecto:")
    for pkg in missing:
        print(f"    - {pkg}")

    if not in_venv:
        activate_example = r"venv\Scripts\activate   (en Windows)" if sys.platform == "win32" else "source venv/bin/activate (en Linux/macOS)"
        builder_example = "build.bat o build.py" if sys.platform == "win32" else "build.sh o build.py"
        print("\n" + "=" * 65)
        print("  [AVISO DE BUENA PRACTICA]")
        print("  Actualmente NO estas dentro de un entorno virtual (venv).")
        print("  Instalar paquetes directamente en el Python global del sistema")
        print("  puede generar conflictos con otros proyectos.")
        print("\n  Recomendacion:")
        print("    1. Crear un entorno virtual:")
        print("       python -m venv venv")
        print("    2. Activarlo:")
        print(f"       {activate_example}")
        print("    3. Instalar PyInstaller:")
        print("       pip install pyinstaller")
        print(f"    4. Ejecutar de nuevo {builder_example}")
        print("=" * 65 + "\n")

        if auto_confirm:
            proceed = True
        elif not sys.stdin.isatty():
            print("[ERROR] Ejecucion no interactiva y sin entorno virtual.")
            print("Por favor crea/activa un venv e instala pyinstaller antes de compilar.")
            sys.exit(1)
        else:
            resp = input("¿Deseas instalar pyinstaller de todos modos en el Python global? (s/N): ").strip().lower()
            proceed = resp in ['s', 'si', 'y', 'yes']

        if not proceed:
            print("\nOperacion cancelada por el usuario.")
            print("Crea tu entorno virtual y vuelve a intentarlo.")
            sys.exit(0)

    else:
        print(f"\n[*] Entorno virtual detectado: {sys.prefix}")
        if auto_confirm:
            proceed = True
        elif not sys.stdin.isatty():
            proceed = True
        else:
            resp = input("¿Deseas instalar PyInstaller en este entorno? (S/n): ").strip().lower()
            proceed = resp in ['', 's', 'si', 'y', 'yes']

        if not proceed:
            print("\nOperacion cancelada.")
            print("Puedes instalarlo manualmente ejecutando: pip install pyinstaller")
            sys.exit(0)

    print("\n[*] Instalando PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("[OK] PyInstaller instalado con exito.\n")
    except Exception as e:
        print(f"[ERROR] No se pudo instalar PyInstaller: {e}")
        sys.exit(1)

def main():
    print("=======================================================")
    print("   Generador de Ejecutable - Video Workstation (VW)")
    print("   Desarrollado por Gabriel Giraldo & Jorge Nieto")
    print("=======================================================\n")

    auto_confirm = "--yes" in sys.argv or "-y" in sys.argv
    
    # 1. Rutas principales
    dist_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(dist_dir)
    vw_path = os.path.join(project_root, "vw.py")
    
    if not os.path.exists(vw_path):
        print(f"[ERROR] No se encontro el archivo principal: {vw_path}")
        sys.exit(1)

    # 2. Verificar dependencias de build y buenas practicas de entorno
    verify_and_handle_dependencies(auto_confirm=auto_confirm)

    # 3. Verificar posible conflicto con paquete obsoleto 'pathlib' de PyPI
    try:
        import pathlib
        pathlib_file = getattr(pathlib, '__file__', '')
        if pathlib_file and 'site-packages' in pathlib_file.lower():
            print("[!] Detectado paquete externo obsoleto 'pathlib' en site-packages.")
            print("    Desinstalando para evitar conflictos con PyInstaller...")
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "pathlib", "-y"])
    except Exception:
        pass

    # 4. Leer version desde vw.py
    version = "1.0.0"
    try:
        with open(vw_path, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'^(?:APP_)?VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', content, re.MULTILINE)
            if match:
                version = match.group(1)
                print(f"[*] Version detectada: {version}")
            else:
                print(f"[*] No se encontro variable VERSION en vw.py. Usando default {version}.")
    except Exception as e:
        print(f"[!] Error leyendo version desde vw.py: {e}. Usando default {version}.")

    # 5. Generar file_version_info.txt para los metadatos de Windows (solo en Windows)
    is_windows = (sys.platform == "win32")
    version_arg = []
    version_info_path = None

    if is_windows:
        version_parts = version.split('.')
        while len(version_parts) < 4:
            version_parts.append('0')
        version_tuple = tuple(int(x) if x.isdigit() else 0 for x in version_parts[:4])
        
        version_info_content = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'Gabriel Giraldo Herrera & Jorge Iván Nieto Triviño'),
         StringStruct('FileDescription', 'Video Workstation'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'vw'),
         StringStruct('LegalCopyright', 'Copyright (c) 2026 Gabriel Giraldo Herrera & Jorge Iván Nieto Triviño'),
         StringStruct('OriginalFilename', 'VW_v{version}.exe'),
         StringStruct('ProductName', 'Video Workstation'),
         StringStruct('ProductVersion', '{version}')])
      ]), 
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
        version_info_path = os.path.join(dist_dir, "file_version_info.txt")
        try:
            with open(version_info_path, "w", encoding="utf-8") as f:
                f.write(version_info_content)
            print("[OK] Metadatos de ejecutable de Windows generados.")
            version_arg = [f"--version-file={version_info_path}"]
        except Exception as e:
            print(f"[ERROR] No se pudo crear el archivo de version: {e}")
            sys.exit(1)
    else:
        print("[*] Plataforma no-Windows detectada (Linux/macOS). Omitiendo metadatos PE de Windows.")

    # 6. Limpiar compilaciones anteriores en dist/
    exe_name = f"VW_v{version}"
    binary_name = f"{exe_name}.exe" if is_windows else exe_name
    final_exe_path = os.path.join(dist_dir, binary_name)
    if os.path.exists(final_exe_path):
        try:
            os.remove(final_exe_path)
            print(f"[*] Ejecutable anterior eliminado: {final_exe_path}")
        except Exception as e:
            print(f"[!] Advertencia: No se pudo eliminar el ejecutable anterior: {e}")

    build_dir = os.path.join(dist_dir, "build")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
            print("[*] Carpeta temporal build/ limpiada.")
        except Exception as e:
            print(f"[!] Advertencia al limpiar build/: {e}")

    spec_file_path = os.path.join(dist_dir, f"{exe_name}.spec")
    if os.path.exists(spec_file_path):
        try:
            os.remove(spec_file_path)
            print("[*] Archivo .spec anterior eliminado.")
        except Exception as e:
            print(f"[!] Advertencia al eliminar .spec: {e}")

    # 7. Buscar icono si existe
    icon_candidate_paths = [
        os.path.join(project_root, "icon.icns"),
        os.path.join(project_root, "icon.ico"),
        os.path.join(project_root, "assets", "icon.icns"),
        os.path.join(project_root, "assets", "icon.ico"),
        os.path.join(project_root, "assets", "icon.png"),
        os.path.join(dist_dir, "icon.ico"),
    ]
    icon_arg = []
    for icon_path in icon_candidate_paths:
        if os.path.exists(icon_path):
            print(f"[*] Icono encontrado: {icon_path}")
            icon_arg = [f"--icon={icon_path}"]
            break

    # 8. Comando PyInstaller
    # VW utiliza la biblioteca estandar pura de Python (sin librerias externas pesadas)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--name={exe_name}",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={dist_dir}",
    ] + version_arg + icon_arg + [vw_path]
    
    print(f"\n[*] Ejecutando PyInstaller...")
    try:
        subprocess.check_call(cmd)
        print("\n[OK] Compilacion de PyInstaller completada con exito.")
    except Exception as e:
        print(f"\n[ERROR] Error durante la ejecucion de PyInstaller: {e}")
        sys.exit(1)

    # 9. Limpieza posterior a la compilación
    print("[*] Limpiando archivos temporales...")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
        except Exception as e:
            print(f"[!] Advertencia: No se pudo eliminar la carpeta build/: {e}")
            
    if os.path.exists(spec_file_path):
        try:
            os.remove(spec_file_path)
        except Exception as e:
            print(f"[!] Advertencia: No se pudo eliminar el archivo spec: {e}")

    if version_info_path and os.path.exists(version_info_path):
        try:
            os.remove(version_info_path)
        except Exception as e:
            print(f"[!] Advertencia: No se pudo eliminar el archivo de version temporal: {e}")

    print("\n=======================================================")
    print("   [EXITO] Ejecutable portable creado correctamente:")
    print(f"   -> {final_exe_path}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
