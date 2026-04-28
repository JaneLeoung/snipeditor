Usage

Run t./build_windows_exe.sh in Git Bash from the project folder:

bash build_windows_exe.sh

What it does:
1. Installs/updates:
   - pyinstaller
   - pillow
   - pywin32
2. Uses icon.ico if present
3. If icon.ico is missing but icon.png exists, converts icon.png -> icon.ico
4. Deletes old build/dist/spec
5. Builds:
   dist/snip_edit.exe

Expected files in the same folder:
- snip_edit.py
- icon.ico   OR   icon.png
