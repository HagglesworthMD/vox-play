"""
PyInstaller hook for Streamlit

Streamlit requires its package metadata and static assets to be bundled
with the executable. This hook ensures all necessary components are included.
"""

from PyInstaller.utils.hooks import (
    copy_metadata,
    collect_data_files,
    collect_submodules,
)


# Copy package metadata (required for Streamlit to function)
datas = copy_metadata('streamlit')

# Collect Streamlit's static files (CSS, JS, HTML templates, etc.)
datas += collect_data_files('streamlit')

# Collect all Streamlit submodules (many are dynamically imported)
hiddenimports = collect_submodules('streamlit')

# Additional common dependencies that Streamlit uses
hiddenimports += [
    'streamlit.runtime.scriptrunner.magic_funcs',
    'streamlit.runtime.secrets',
    'streamlit.runtime.state',
    'streamlit.runtime.uploaded_file_manager',
    'streamlit.web.server.websocket_headers',
    'streamlit.web.server.routes',
    'streamlit.components.v1',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    'importlib_metadata',
    'toml',
    'validators',
    'gitpython',
    'watchdog',
    'cachetools',
    'pyarrow',
    'altair',
    'tornado',
    'blinker',
]
