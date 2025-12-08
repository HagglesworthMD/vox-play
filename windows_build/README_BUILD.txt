═══════════════════════════════════════════════════════════════════════════════════
                    VOXELMASK v1.0 - WINDOWS BUILD KIT
              Intelligent DICOM De-Identification Workstation
═══════════════════════════════════════════════════════════════════════════════════

This folder contains everything needed to build VoxelMask as a standalone
Windows executable (.exe) that doesn't require Python or Docker to run.


PREREQUISITES
─────────────────────────────────────────────────────────────────────────────────────

1. Windows 10 or Windows 11 (64-bit)

2. Python 3.8 or higher
   - Download from: https://www.python.org/downloads/
   - IMPORTANT: During installation, check "Add Python to PATH"
   - Recommended: Python 3.10 or 3.11 for best compatibility

3. Internet connection (to download dependencies during build)

4. At least 2GB of free disk space


BUILD INSTRUCTIONS
─────────────────────────────────────────────────────────────────────────────────────

Step 1: Copy this entire folder to your Windows machine
        - Copy the 'windows_build' folder
        - Also copy the 'src' folder (sibling to windows_build)
        - Also copy the '.streamlit' folder if it exists

        Your folder structure should look like:
        
        VoxelMask/
        ├── windows_build/
        │   ├── build.bat
        │   ├── VoxelMask.spec
        │   ├── voxelmask_wrapper.py
        │   └── README_BUILD.txt (this file)
        ├── src/
        │   ├── app.py
        │   ├── research_mode/
        │   └── ...
        └── .streamlit/
            └── config.toml

Step 2: Open Command Prompt or PowerShell
        - Press Win+R, type 'cmd', press Enter
        - Or search for "Command Prompt" in Start menu

Step 3: Navigate to the windows_build folder
        > cd C:\path\to\VoxelMask\windows_build

Step 4: Run the build script
        > build.bat

Step 5: Wait for the build to complete
        - This typically takes 5-15 minutes
        - Dependencies will be downloaded automatically
        - You'll see progress messages in the console

Step 6: Find your executable
        - Location: windows_build\dist\VoxelMask\VoxelMask.exe
        - The entire 'VoxelMask' folder in 'dist' is your distributable


RUNNING THE APPLICATION
─────────────────────────────────────────────────────────────────────────────────────

1. Navigate to: dist\VoxelMask\

2. Double-click: VoxelMask.exe

3. A console window will appear showing:
   - Server startup messages
   - The URL to access the application (usually http://localhost:8501)

4. Your default web browser should open automatically
   - If not, manually navigate to http://localhost:8501

5. To stop the application:
   - Close the console window, OR
   - Press Ctrl+C in the console


DISTRIBUTING TO END USERS
─────────────────────────────────────────────────────────────────────────────────────

To share VoxelMask with users who don't have Python:

1. Copy the entire 'dist\VoxelMask\' folder to a USB drive or network share

2. Users simply:
   - Copy the VoxelMask folder to their computer
   - Double-click VoxelMask.exe
   - No installation required!

3. Optional: Create a desktop shortcut
   - Right-click VoxelMask.exe
   - Select "Create shortcut"
   - Move shortcut to desktop


TROUBLESHOOTING
─────────────────────────────────────────────────────────────────────────────────────

Problem: "Python is not recognized as an internal or external command"
Solution: Reinstall Python and check "Add Python to PATH"

Problem: Build fails with "ModuleNotFoundError"
Solution: Run these commands manually:
          > pip install streamlit pydicom numpy pillow pandas pyinstaller
          > pip install opencv-python streamlit-drawable-canvas

Problem: Application starts but browser doesn't open
Solution: Manually open http://localhost:8501 in your browser

Problem: "Port 8501 is already in use"
Solution: Close any other VoxelMask instances or applications using port 8501

Problem: Antivirus blocks the .exe
Solution: Add an exception for VoxelMask.exe in your antivirus software
          (This is a false positive - the exe is safe)


FILES IN THIS BUILD KIT
─────────────────────────────────────────────────────────────────────────────────────

build.bat           - Automated build script (run this!)
VoxelMask.spec      - PyInstaller configuration file
voxelmask_wrapper.py - Application entry point/bootloader
README_BUILD.txt    - This documentation file


TECHNICAL NOTES
─────────────────────────────────────────────────────────────────────────────────────

- The build uses PyInstaller to bundle Python and all dependencies
- Streamlit runs as a local web server on port 8501
- The console window shows server logs (useful for debugging)
- To hide the console in production, edit VoxelMask.spec:
  Change: console=True
  To:     console=False
  Then rebuild.


SUPPORT
─────────────────────────────────────────────────────────────────────────────────────

For issues with the build process:
- Check that Python is correctly installed and in PATH
- Ensure you have internet access for downloading dependencies
- Try running build.bat as Administrator

For application issues:
- Check the console window for error messages
- Ensure no other application is using port 8501


═══════════════════════════════════════════════════════════════════════════════════
                         VoxelMask v1.0 - Build Kit
                    © 2025 VoxelMask Engineering Team
═══════════════════════════════════════════════════════════════════════════════════
