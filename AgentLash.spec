# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller --noconfirm --clean AgentLash.spec


# Only the assets the app actually loads (the old whip_*/handle_*/crop_* sprites are no longer used)
datas = [
    ('assets/app_icon.png', 'assets'),
    ('assets/app_icon.ico', 'assets'),
    ('assets/pow.png', 'assets'),
    ('assets/zap.png', 'assets'),
    ('assets/crack.png', 'assets'),
    ('assets/sounds/whip_comic.wav', 'assets/sounds'),
    ('assets/sounds/whip_cyber.wav', 'assets/sounds'),
    ('assets/sounds/whip_classic.wav', 'assets/sounds'),
    ('assets/custom_animation/README.txt', 'assets/custom_animation'),
    ('assets/custom_sounds/README.txt', 'assets/custom_sounds'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PIL', 'numpy', 'tkinter', 'unittest', 'pydoc',
        'PyQt6.QtMultimedia', 'PyQt6.QtNetwork', 'PyQt6.QtQml', 'PyQt6.QtQuick', 'PyQt6.QtPdf',
        'PyQt6.QtSvg', 'PyQt6.QtSql', 'PyQt6.QtOpenGL', 'PyQt6.QtDBus', 'PyQt6.QtWebEngineCore',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AgentLash',
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
