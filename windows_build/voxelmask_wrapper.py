#!/usr/bin/env python3
"""
VoxelMask Windows Standalone Wrapper

This script acts as the bootloader for the PyInstaller-bundled VoxelMask application.
It handles both frozen (PyInstaller) and development environments, then launches
the Streamlit application.
"""

import os
import sys


def get_app_path():
    """
    Determine the absolute path to app.py.
    
    Handles both:
    - Frozen PyInstaller state (_MEIPASS temp directory)
    - Normal development state (relative to this script)
    
    Returns:
        str: Absolute path to the app.py file
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        # _MEIPASS is the temp directory where PyInstaller extracts files
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to find the src directory
        base_path = os.path.dirname(base_path)
    
    app_path = os.path.join(base_path, 'src', 'app.py')
    
    # Verify the file exists
    if not os.path.exists(app_path):
        print(f"ERROR: Could not find app.py at: {app_path}")
        print(f"Base path: {base_path}")
        print(f"Frozen: {getattr(sys, 'frozen', False)}")
        if getattr(sys, 'frozen', False):
            print(f"_MEIPASS: {sys._MEIPASS}")
            print(f"Contents of _MEIPASS:")
            for item in os.listdir(sys._MEIPASS):
                print(f"  - {item}")
        sys.exit(1)
    
    return app_path


def setup_environment():
    """
    Set up environment variables for Streamlit in bundled mode.
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        
        # Set Streamlit config directory
        streamlit_config = os.path.join(base_path, '.streamlit')
        if os.path.exists(streamlit_config):
            os.environ['STREAMLIT_CONFIG_DIR'] = streamlit_config
        
        # Disable Streamlit's file watcher (not needed in production)
        os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'
        
        # Disable development mode
        os.environ['STREAMLIT_GLOBAL_DEVELOPMENT_MODE'] = 'false'
        
        # Set browser gathering to false
        os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
        
        # Set theme
        os.environ['STREAMLIT_THEME_BASE'] = 'dark'
        os.environ['STREAMLIT_THEME_PRIMARY_COLOR'] = '#00d4ff'
        os.environ['STREAMLIT_THEME_BACKGROUND_COLOR'] = '#0e1117'
        os.environ['STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR'] = '#262730'


def main():
    """
    Main entry point for VoxelMask Windows standalone.
    
    Sets up sys.argv to emulate running:
        streamlit run app.py --global.developmentMode=false
    
    Then calls Streamlit's CLI main function.
    """
    print("=" * 60)
    print("  VoxelMask v1.0 - Intelligent DICOM De-Identification")
    print("=" * 60)
    print()
    
    # Setup environment
    setup_environment()
    
    # Get path to app.py
    app_path = get_app_path()
    print(f"Starting VoxelMask from: {app_path}")
    print()
    print("The application will open in your default web browser.")
    print("If it doesn't open automatically, navigate to: http://localhost:8501")
    print()
    print("Press Ctrl+C in this window to stop the server.")
    print("-" * 60)
    print()
    
    # Set sys.argv to emulate: streamlit run app.py --global.developmentMode=false
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
        "--theme.primaryColor=#00d4ff",
        "--theme.backgroundColor=#0e1117",
        "--theme.secondaryBackgroundColor=#262730",
    ]
    
    # Import and run Streamlit
    try:
        from streamlit.web import cli as stcli
        stcli.main()
    except ImportError:
        # Fallback for older Streamlit versions
        try:
            from streamlit import cli as stcli
            stcli.main()
        except ImportError as e:
            print(f"ERROR: Failed to import Streamlit CLI: {e}")
            print("Please ensure Streamlit is properly installed.")
            sys.exit(1)


if __name__ == "__main__":
    main()
