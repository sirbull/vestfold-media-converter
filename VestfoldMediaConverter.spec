# PyInstaller onedir. Bygg på Windows med låste avhengigheter fra uv.lock.
from pathlib import Path

root = Path(SPECPATH)
licenses = root / 'build' / 'licenses'
datas = [(str(licenses), 'licenses'), (str(root / 'vendor/ffmpeg/origin.json'), 'vendor/ffmpeg'),
         (str(root / 'README.md'), 'docs'), (str(root / 'IT-GODKJENNING.md'), 'docs'),
         (str(root / 'docs'), 'docs'), (str(root / 'LICENSE'), 'licenses'),
         (str(root / 'src/vestfold_converter/assets'), 'vestfold_converter/assets')]
binaries = [(str(root / 'vendor/ffmpeg/bin' / name), 'vendor/ffmpeg/bin')
            for name in ('ffmpeg.exe', 'ffprobe.exe')]
a = Analysis([str(root / 'scripts/entrypoint.py')], pathex=[str(root / 'src')],
             binaries=binaries, datas=datas, hiddenimports=[], hookspath=[],
             excludes=['PySide6.QtNetwork', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWebEngineCore',
                       'PySide6.QtMultimedia', 'tkinter', 'pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='VestfoldMediaConverter',
          debug=False, strip=False, upx=False, console=False,
          manifest=str(root / 'scripts/windows.manifest'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='VestfoldMediaConverter')

