"""
PyInstaller hook for streamlit-drawable-canvas

This Streamlit component requires its static assets (JavaScript, CSS)
to be bundled with the executable.
"""

from PyInstaller.utils.hooks import (
    copy_metadata,
    collect_data_files,
)


# Copy package metadata
datas = copy_metadata('streamlit_drawable_canvas')

# Collect the component's static files (frontend bundle)
datas += collect_data_files('streamlit_drawable_canvas')
