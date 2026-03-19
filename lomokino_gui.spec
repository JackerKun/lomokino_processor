# PyInstaller spec file for LomoKino GUI
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['lomokino_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['cv2', 'numpy', 'PyQt6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LomoKinoGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LomoKinoGUI',
)

# For macOS
app = BUNDLE(
    coll,
    name='LomoKinoGUI.app',
    icon='LomoKinoGUI.icns',
    bundle_identifier='com.lomokino.gui',
)
