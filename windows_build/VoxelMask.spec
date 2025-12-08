# -*- mode: python ; coding: utf-8 -*-
"""
VoxelMask PyInstaller Spec File

This spec file configures PyInstaller to bundle VoxelMask into a standalone
Windows executable. It handles:
- Streamlit's internal static assets (HTML/JS/CSS)
- DICOM processing libraries (pydicom, numpy, PIL)
- Application source code and configuration

Build with: pyinstaller --noconfirm --clean VoxelMask.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Get the directory containing this spec file
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.dirname(spec_dir)

# ═══════════════════════════════════════════════════════════════════════════════
# COLLECT STREAMLIT DATA FILES
# ═══════════════════════════════════════════════════════════════════════════════
# Streamlit requires its static assets (HTML, JS, CSS) to be bundled

streamlit_datas = collect_data_files('streamlit')
altair_datas = collect_data_files('altair')
pydeck_datas = collect_data_files('pydeck')

# Streamlit drawable canvas component
try:
    canvas_datas = collect_data_files('streamlit_drawable_canvas')
except Exception:
    canvas_datas = []

# Validators
try:
    validators_datas = collect_data_files('validators')
except Exception:
    validators_datas = []

# ═══════════════════════════════════════════════════════════════════════════════
# COLLECT APPLICATION DATA
# ═══════════════════════════════════════════════════════════════════════════════

# Application source code
app_datas = [
    (os.path.join(project_root, 'src'), 'src'),
]

# Streamlit configuration
streamlit_config = os.path.join(project_root, '.streamlit')
if os.path.exists(streamlit_config):
    app_datas.append((streamlit_config, '.streamlit'))

# Presets file if it exists
presets_file = os.path.join(project_root, 'src', 'presets.json')
if os.path.exists(presets_file):
    app_datas.append((presets_file, 'src'))

# Combine all data files
all_datas = streamlit_datas + altair_datas + pydeck_datas + canvas_datas + validators_datas + app_datas

# ═══════════════════════════════════════════════════════════════════════════════
# HIDDEN IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
# These modules are imported dynamically and PyInstaller can't detect them

hidden_imports = [
    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMLIT CORE & WEB
    # ═══════════════════════════════════════════════════════════════════════════
    'streamlit',
    'streamlit.web',
    'streamlit.web.cli',
    'streamlit.web.server',
    'streamlit.web.server.server',
    'streamlit.web.server.browser_websocket_handler',
    'streamlit.web.server.component_request_handler',
    'streamlit.web.server.media_file_handler',
    'streamlit.web.server.routes',
    'streamlit.web.server.server_util',
    'streamlit.web.server.upload_file_request_handler',
    'streamlit.runtime',
    'streamlit.runtime.scriptrunner',
    'streamlit.runtime.scriptrunner.script_runner',
    'streamlit.runtime.scriptrunner.magic_funcs',
    'streamlit.runtime.caching',
    'streamlit.runtime.caching.cache_data_api',
    'streamlit.runtime.caching.cache_resource_api',
    'streamlit.runtime.state',
    'streamlit.runtime.uploaded_file_manager',
    'streamlit.runtime.media_file_manager',
    'streamlit.runtime.memory_media_file_storage',
    'streamlit.components',
    'streamlit.components.v1',
    'streamlit.components.v1.components',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMLIT DEPENDENCIES
    # ═══════════════════════════════════════════════════════════════════════════
    'altair',
    'altair.vegalite',
    'altair.vegalite.v5',
    'pydeck',
    'validators',
    'toml',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'gitpython',
    'git',
    'rich',
    'rich.console',
    'rich.text',
    'tenacity',
    'cachetools',
    'pympler',
    'tzlocal',
    'click',
    'tornado',
    'tornado.web',
    'tornado.websocket',
    'tornado.ioloop',
    'protobuf',
    'google.protobuf',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STREAMLIT DRAWABLE CANVAS
    # ═══════════════════════════════════════════════════════════════════════════
    'streamlit_drawable_canvas',
    'streamlit_drawable_canvas.frontend',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PYDICOM AND IMAGE PROCESSING
    # ═══════════════════════════════════════════════════════════════════════════
    'pydicom',
    'pydicom.encoders',
    'pydicom.encoders.pylibjpeg',
    'pydicom.encoders.gdcm',
    'pydicom.encoders.native',
    'pydicom.pixel_data_handlers',
    'pydicom.pixel_data_handlers.numpy_handler',
    'pydicom.pixel_data_handlers.pillow_handler',
    'pydicom.pixel_data_handlers.gdcm_handler',
    'pydicom.pixel_data_handlers.pylibjpeg_handler',
    'pydicom.pixel_data_handlers.rle_handler',
    'pydicom.uid',
    'pydicom.valuerep',
    'pydicom.dataset',
    'pydicom.sequence',
    'pydicom.filereader',
    'pydicom.filewriter',
    
    # PyLibJPEG
    'pylibjpeg',
    'pylibjpeg.utils',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PIL / PILLOW
    # ═══════════════════════════════════════════════════════════════════════════
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'PIL.ImageOps',
    'PIL.ImageFilter',
    'PIL.PngImagePlugin',
    'PIL.JpegImagePlugin',
    'PIL.GifImagePlugin',
    'PIL.BmpImagePlugin',
    'PIL.TiffImagePlugin',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NUMPY
    # ═══════════════════════════════════════════════════════════════════════════
    'numpy',
    'numpy.core',
    'numpy.core._methods',
    'numpy.core._dtype_ctypes',
    'numpy.lib',
    'numpy.lib.format',
    'numpy.random',
    'numpy.fft',
    'numpy.linalg',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # OPENCV (HEADLESS)
    # ═══════════════════════════════════════════════════════════════════════════
    'cv2',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PANDAS
    # ═══════════════════════════════════════════════════════════════════════════
    'pandas',
    'pandas.core',
    'pandas.core.frame',
    'pandas.core.series',
    'pandas.io',
    'pandas.io.formats',
    'pandas.io.formats.style',
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ADDITIONAL UTILITIES
    # ═══════════════════════════════════════════════════════════════════════════
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    'importlib_metadata',
    'typing_extensions',
    'magic',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'json',
    'hashlib',
    'secrets',
    'uuid',
    'tempfile',
    'shutil',
    'zipfile',
    'io',
    'base64',
    'datetime',
    're',
    'os',
    'sys',
    'pathlib',
]

# Collect all submodules for key packages
hidden_imports += collect_submodules('streamlit')
hidden_imports += collect_submodules('pydicom')

# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

block_cipher = None

a = Analysis(
    ['voxelmask_wrapper.py'],
    pathex=[spec_dir, project_root],
    binaries=[],
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ═══════════════════════════════════════════════════════════════════════════════
# PYZ ARCHIVE
# ═══════════════════════════════════════════════════════════════════════════════

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTABLE
# ═══════════════════════════════════════════════════════════════════════════════

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoxelMask',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for debugging; set to False for production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if available: icon='voxelmask.ico'
)

# ═══════════════════════════════════════════════════════════════════════════════
# COLLECT
# ═══════════════════════════════════════════════════════════════════════════════

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VoxelMask',
)
