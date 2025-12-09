#!/usr/bin/env python3
"""
VoxelMask PyInstaller Entry Point

This is a special wrapper for PyInstaller that correctly invokes
Streamlit's CLI to run the main app.py file.

Handles frozen (PyInstaller) vs. development mode path resolution.
"""

import sys
import os


def get_app_path():
    """
    Resolve the correct path to app.py, handling both frozen (PyInstaller)
    and development environments.
    
    Returns:
        str: Absolute path to app.py
    """
    # Check if running from a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        # sys._MEIPASS is the path to the temporary folder with extracted files
        bundle_dir = sys._MEIPASS
        app_path = os.path.join(bundle_dir, 'src', 'app.py')
    else:
        # Running in normal Python environment
        # Get the directory where this script is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        app_path = os.path.join(current_dir, 'app.py')
    
    return app_path


def main():
    """
    Main entry point for the VoxelMask Windows executable.
    
    Programmatically invokes Streamlit to run the app.py file with
    production settings (development mode disabled).
    """
    # Get the correct path to app.py
    app_path = get_app_path()
    
    # Verify the app file exists
    if not os.path.exists(app_path):
        print(f"ERROR: Could not find app.py at: {app_path}")
        print("Please ensure the application was bundled correctly.")
        sys.exit(1)
    
    # Set up sys.argv as if we called: streamlit run src/app.py --global.developmentMode=false
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    
    # Import and run Streamlit's CLI
    # Handle different Streamlit versions (structure changed over time)
    try:
        # Streamlit >= 1.12.0
        from streamlit.web import cli as stcli
        sys.exit(stcli.main())
    except ImportError:
        try:
            # Streamlit < 1.12.0
            from streamlit import cli as stcli
            sys.exit(stcli.main())
        except ImportError as e:
            print(f"ERROR: Could not import Streamlit CLI: {e}")
            print("Please ensure Streamlit is installed correctly.")
            sys.exit(1)


if __name__ == "__main__":
    main()
