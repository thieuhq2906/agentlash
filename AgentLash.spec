# -*- mode: python ; coding: utf-8 -*-
# Build both editions: pyinstaller --noconfirm --clean AgentLash.spec
#   dist/AgentLash.exe           standard edition (no security-awareness code inside at all)
#   dist/AgentLash_Security.exe  security edition (awareness screen after N minutes of use, F9, tray menu)
import os

# Only the assets the app actually loads (impact words are drawn in code; old PNG sprites are not bundled)
datas = [
    ('assets/app_icon.png', 'assets'),
    ('assets/app_icon.ico', 'assets'),
    ('assets/sounds/whip_comic.wav', 'assets/sounds'),
    ('assets/sounds/whip_cyber.wav', 'assets/sounds'),
    ('assets/sounds/whip_classic.wav', 'assets/sounds'),
    ('assets/sounds/whip_sword.wav', 'assets/sounds'),
    ('assets/custom_animation/README.txt', 'assets/custom_animation'),
    ('assets/custom_sounds/README.txt', 'assets/custom_sounds'),
]
# Local-only sounds (copyrighted Tom & Jerry audio, never committed): bundled when present.
# Without them the taser falls back to the cyber crack and the Tom sound modes play the themed crack.
for optional in ('whip_taser.wav', 'whip_tom_combo.wav', 'tom_scream.wav'):
    if os.path.exists(os.path.join('assets', 'sounds', optional)):
        datas.append((f'assets/sounds/{optional}', 'assets/sounds'))

COMMON_EXCLUDES = [
    'PIL', 'numpy', 'tkinter', 'unittest', 'pydoc',
    'PyQt6.QtMultimedia', 'PyQt6.QtNetwork', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtPdf',
    'PyQt6.QtSvg', 'PyQt6.QtSql', 'PyQt6.QtOpenGL', 'PyQt6.QtDBus', 'PyQt6.QtWebEngineCore',
]


def build_edition(name, security):
    # edition.py imports `_edition`; each exe gets its own generated copy from a private folder
    edition_dir = os.path.join(workpath, f'edition_{name}')
    os.makedirs(edition_dir, exist_ok=True)
    with open(os.path.join(edition_dir, '_edition.py'), 'w', encoding='utf-8') as f:
        f.write(f'SECURITY_EDITION = {security}\n')

    a = Analysis(
        ['main.py'],
        pathex=[edition_dir],
        binaries=[],
        datas=datas,
        hiddenimports=['_edition'],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=COMMON_EXCLUDES + ([] if security else ['security_awareness']),
        noarchive=False,
        optimize=0,
    )
    pyz = PYZ(a.pure)
    EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # UPX tends to corrupt Qt DLLs and triggers antivirus false positives
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=['assets/app_icon.ico'],
    )


build_edition('AgentLash', security=False)
build_edition('AgentLash_Security', security=True)
