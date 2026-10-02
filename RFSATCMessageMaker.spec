# -*- mode: python ; coding: utf-8 -*-


from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=collect_data_files('tzdata') + collect_data_files('PySide6', includes=['translations/qtbase_fr.qm', 'translations/qtbase_en.qm']) + [('fuel/data/aircraft_fuel_data.json', 'fuel/data'),
                                      ('fuel/data/airport_alternates.json', 'fuel/data'), ('assets/check.svg', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtNetwork', 'duckdb', 'timezonefinder', 'numpy', 'finder.importer', 'finder.fetch_data'],
    noarchive=False,
    optimize=0,
)
# Qt uses Windows' unversioned ICU API. Collecting an unrelated ICU from PATH
# shadows the system DLL and causes WinError 127 when importing QtWidgets.
a.binaries = [entry for entry in a.binaries
              if entry[0].replace('\\', '/').rsplit('/', 1)[-1].lower()
              not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RFSATCMessageMaker',
    icon='assets/app.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='_internal',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RFSATCMessageMaker',
)
