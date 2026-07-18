import os
import sys
import re
import shutil
import subprocess

def main():
    print("=== VPT Studio Executable Builder ===")
    
    # 1. Check for pyinstaller
    try:
        import PyInstaller
        print("PyInstaller is already installed.")
    except ImportError:
        print("PyInstaller is not installed. Installing it now...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("PyInstaller installed successfully.")
        except Exception as e:
            print(f"Error installing PyInstaller: {e}")
            sys.exit(1)
            
    # 2. Get the root path (parent of dist)
    dist_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(dist_dir)
    vpt_path = os.path.join(project_root, "vpt.py")
    
    if not os.path.exists(vpt_path):
        print(f"Error: Could not find vpt.py at {vpt_path}")
        sys.exit(1)
        
    # 3. Read version from vpt.py
    version = "1.0.0"
    try:
        with open(vpt_path, "r", encoding="utf-8") as f:
            content = f.read()
            match = re.search(r'^VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', content, re.MULTILINE)
            if match:
                version = match.group(1)
                print(f"Detected version: {version}")
            else:
                print("Warning: Could not find VERSION variable in vpt.py. Using default 1.0.0.")
    except Exception as e:
        print(f"Error reading version from vpt.py: {e}. Using default 1.0.0.")

    # 4. Generate file_version_info.txt
    # We parse the version (e.g. "1.0.0") into 4 tuple integers (e.g. 1, 0, 0, 0)
    version_parts = version.split('.')
    while len(version_parts) < 4:
        version_parts.append('0')
    version_tuple = tuple(int(x) for x in version_parts[:4])
    
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
        [StringStruct('CompanyName', 'TheHexenjagd'),
         StringStruct('FileDescription', 'Video Processing Toolkit Studio'),
         StringStruct('FileVersion', '{version}'),
         StringStruct('InternalName', 'vpt'),
         StringStruct('LegalCopyright', 'Copyright (c) 2026 TheHexenjagd'),
         StringStruct('OriginalFilename', 'VPT_Studio_v{version}.exe'),
         StringStruct('ProductName', 'VPT Studio'),
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
        print("Generated file_version_info.txt successfully.")
    except Exception as e:
        print(f"Error writing version info file: {e}")
        sys.exit(1)

    # 5. Clean up old builds and SPEC files in dist
    exe_name = f"VPT_Studio_v{version}"
    final_exe_path = os.path.join(dist_dir, f"{exe_name}.exe")
    if os.path.exists(final_exe_path):
        try:
            os.remove(final_exe_path)
            print(f"Removed old executable: {final_exe_path}")
        except Exception as e:
            print(f"Warning: Could not remove old executable: {e}")

    # Remove build folder and spec file if they exist
    build_dir = os.path.join(dist_dir, "build")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
            print("Cleaned up old build workspace.")
        except Exception as e:
            print(f"Warning: Could not clean build directory: {e}")

    spec_file_path = os.path.join(dist_dir, f"{exe_name}.spec")
    if os.path.exists(spec_file_path):
        try:
            os.remove(spec_file_path)
            print("Removed old spec file.")
        except Exception as e:
            print(f"Warning: Could not remove old spec file: {e}")

    # 6. Run PyInstaller
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--name={exe_name}",
        f"--version-file={version_info_path}",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={dist_dir}",
        vpt_path
    ]
    
    print(f"Running PyInstaller command: {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd)
        print("\nPyInstaller build completed successfully.")
    except Exception as e:
        print(f"\nError running PyInstaller: {e}")
        sys.exit(1)

    # 7. Post-build cleanup
    print("Cleaning up temporary build files...")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
        except Exception as e:
            print(f"Warning: Could not remove build folder: {e}")
            
    if os.path.exists(spec_file_path):
        try:
            os.remove(spec_file_path)
        except Exception as e:
            print(f"Warning: Could not remove spec file: {e}")

    if os.path.exists(version_info_path):
        try:
            os.remove(version_info_path)
        except Exception as e:
            print(f"Warning: Could not remove version info file: {e}")

    print(f"\nSuccess! Independent executable created at:")
    print(final_exe_path)

if __name__ == "__main__":
    main()
