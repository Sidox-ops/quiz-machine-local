from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "backend" / "desktop_main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "agent.md"), "."),
        (str(root / "data" / "reference"), "data/reference"),
    ],
    hiddenimports=collect_submodules("uvicorn"),
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
    a.binaries,
    a.datas,
    [],
    name="quiz_backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
