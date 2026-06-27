"""Packaging builder — creates standalone VAYU executable and manages updates.

Usage:
    python packaging/build.py          — build .exe with PyInstaller
    python packaging/build.py --install — build + create NSIS installer
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def build_exe():
    root = _project_root()
    dist = root / "dist"
    build_dir = root / "build"

    print("[Package] Cleaning previous builds...")
    for d in [dist, build_dir]:
        if d.exists():
            shutil.rmtree(d)

    print("[Package] Running PyInstaller...")
    spec_path = root / "vayu.spec"

    if not spec_path.exists():
        pyinstaller_args = [
            sys.executable, "-m", "PyInstaller",
            "--name", "VAYU",
            "--windowed",
            "--onefile",
            "--add-data", f"core{os.pathsep}core",
            "--add-data", f"config{os.pathsep}config",
            "--add-data", f"memory{os.pathsep}memory",
            "--add-data", f"actions{os.pathsep}actions",
            "--add-data", f"brain{os.pathsep}brain",
            "--add-data", f"voice{os.pathsep}voice",
            "--add-data", f"vision{os.pathsep}vision",
            "--add-data", f"plugins{os.pathsep}plugins",
            "--hidden-import", "win32com",
            "--hidden-import", "win32gui",
            "--hidden-import", "sounddevice",
            "--hidden-import", "PIL",
            "--hidden-import", "qrcode",
            "--exclude-module", "torch",
            "--exclude-module", "scipy",
            "--exclude-module", "pandas",
            "--exclude-module", "matplotlib",
            "--exclude-module", "scipy.linalg",
            "--exclude-module", "scipy.special",
            "--exclude-module", "tensorboard",
            "--collect-all", "groq_client",
            "--collect-all", "or_client",
            str(root / "main.py"),
        ]
        if (root / "icon.ico").exists():
            pyinstaller_args.insert(4, "--icon")
            pyinstaller_args.insert(5, str(root / "icon.ico"))
    else:
        pyinstaller_args = [
            sys.executable, "-m", "PyInstaller",
            str(spec_path),
        ]

    result = subprocess.run(pyinstaller_args, cwd=str(root))
    if result.returncode != 0:
        print("[Package] PyInstaller failed!")
        return False

    print(f"[Package] Build complete: {dist / 'VAYU.exe'}")
    return True


def create_installer():
    root = _project_root()
    dist = root / "dist"
    exe_path = dist / "VAYU.exe"

    if not exe_path.exists():
        print("[Package] Build the exe first: python packaging/build.py")
        return False

    nsis_script = root / "packaging" / "installer.nsi"
    if not nsis_script.exists():
        nsis_dir = root / "packaging"
        nsis_dir.mkdir(parents=True, exist_ok=True)
        nsis_script = nsis_dir / "installer.nsi"
        nsis_script.write_text(f"""!include "MUI2.nsh"

Name "VAYU AI Assistant"
OutFile "..\\dist\\VAYU_Setup.exe"
InstallDir "$PROGRAMFILES\\VAYU"
RequestExecutionLevel admin

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File "..\\dist\\VAYU.exe"
    CreateShortCut "$DESKTOP\\VAYU.lnk" "$INSTDIR\\VAYU.exe"
    CreateDirectory "$STARTMENU\\Programs\\VAYU"
    CreateShortCut "$STARTMENU\\Programs\\VAYU\\VAYU.lnk" "$INSTDIR\\VAYU.exe"
    WriteUninstaller "$INSTDIR\\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\\VAYU.exe"
    Delete "$INSTDIR\\Uninstall.exe"
    RMDir "$INSTDIR"
    Delete "$DESKTOP\\VAYU.lnk"
    RMDir /r "$STARTMENU\\Programs\\VAYU"
SectionEnd
""")

    print("[Package] Running NSIS installer builder...")
    result = subprocess.run(["makensis", str(nsis_script)], cwd=str(root / "packaging"))
    if result.returncode != 0:
        print("[Package] NSIS failed! Install NSIS from https://nsis.sourceforge.io")
        return False

    print(f"[Package] Installer created: {root / 'dist' / 'VAYU_Setup.exe'}")
    return True


class AutoUpdater:
    def __init__(self):
        self._version_url = "https://raw.githubusercontent.com/your-org/vayu/main/version.txt"
        self._current_version = self._read_current_version()

    def _read_current_version(self) -> str:
        root = _project_root()
        ver_file = root / "version.txt"
        if ver_file.exists():
            return ver_file.read_text(encoding="utf-8").strip()
        return "1.0.0"

    def check_update(self) -> str | None:
        try:
            import urllib.request
            resp = urllib.request.urlopen(self._version_url, timeout=5)
            latest = resp.read().decode().strip()
            if latest != self._current_version:
                return latest
        except Exception:
            pass
        return None


if __name__ == "__main__":
    if "--install" in sys.argv:
        if build_exe():
            create_installer()
    else:
        build_exe()
