# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for VideoStats application.
Build with: pyinstaller VideoStats.spec
"""

block_cipher = None

a = Analysis(
    ['RocketsVideoStats.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include all UI files
        ('RocketsVideoStats.ui', '.'),
        ('viewpaths.ui', '.'),
        ('inputTouchesVoice.ui', '.'),
        ('create_game_dialog.ui', '.'),
        ('contact-popup1.ui', '.'),
        ('configScreen.ui', '.'),
        # Include JSON config file
        ('data/config_receive_rating.json', 'data'),
        # Include highlight_title_creator.py as a data file (it's launched as a subprocess)
        ('highlight_title_creator.py', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtUiTools',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'sqlite3',
        'json',
        'pathlib',
        'utils',
        'database',
        'stats_calc',
        'data_entry',
        'view_paths',
        'create_game_dialog',
        'create_team_dialog',
        'edit_team_dialog',
        'list_games_dialog',
        'coordinate_mapper',
        'lineup_manager',
        'lineup_models',
        'reprocess_outcomes',
        'stats_app',
        'config_screen',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoStats',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (GUI application)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # You can add an icon file here if you have one: 'icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoStats',
)

