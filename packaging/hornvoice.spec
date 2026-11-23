# PyInstaller spec: builds dist/HornVoice/HornVoice.exe (windowed, tray app).  Run from the repo root:  pyinstaller packaging/hornvoice.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

datas = collect_data_files('faster_whisper') + collect_data_files('onnxruntime')
binaries = collect_dynamic_libs('ctranslate2') + collect_dynamic_libs('onnxruntime') + collect_dynamic_libs('av')
hidden = collect_submodules('pystray') + ['hornvoice.app', 'keyboard', 'sounddevice', 'PIL._tkinter_finder']

a = Analysis(
    ['entry.py'],
    pathex=['../src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=['tkinter', 'matplotlib', 'torch', 'tensorflow', 'scipy', 'pandas'],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HornVoice', console=False, icon='icon.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='HornVoice')
