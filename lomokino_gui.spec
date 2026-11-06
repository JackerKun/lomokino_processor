# Build on the target OS/architecture; no cross-compilation is assumed.
import sys
from importlib.metadata import distribution
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

licenses = [('LICENSE', 'licenses/project'), ('docs/THIRD-PARTY.md', 'licenses')]
for package in ('PyQt6', 'PyQt6-Qt6', 'opencv-python', 'numpy', 'imageio-ffmpeg'):
    metadata = distribution(package)
    for entry in metadata.files or []:
        if 'license' in str(entry).lower() and metadata.locate_file(entry).is_file():
            source = str(metadata.locate_file(entry))
            licenses.append((source, 'licenses/' + package + '/' + str(Path(str(entry)).parent)))

a = Analysis(['lomokino_gui.py'], pathex=[], binaries=[],
    datas=[('assets/icon.png', 'assets'), ('assets/demo', 'assets/demo')] + collect_data_files('imageio_ffmpeg') + licenses,
    hiddenimports=['imageio_ffmpeg'], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='LomoKinoGUI',
    debug=False, strip=False, upx=False, console=False,
    icon='assets/icon.ico' if sys.platform == 'win32' else None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='LomoKinoGUI')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='LomoKinoGUI.app', icon='LomoKinoGUI.icns',
        bundle_identifier='com.lomokino.gui', info_plist={
            'CFBundleDisplayName': 'LomoKino Studio', 'CFBundleShortVersionString': '4.0.0',
            'CFBundleVersion': '4.0.0', 'NSHighResolutionCapable': True})
