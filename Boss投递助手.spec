# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['boss_delivery_v2.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.sip', 'DrissionPage', 'DrissionPage._pages',
        'browser_cookie3', 'pymysql',
        'Crypto', 'win32crypt', 'win32.win32crypt', 'openai', 'PyPDF2',
        'requests', 'cryptography', 'websocket', 'websocket-client',
        'json', 'sqlite3', 'threading', 'queue', 'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Boss投递助手',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Boss投递助手',
)
