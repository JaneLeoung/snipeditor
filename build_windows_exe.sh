#!/usr/bin/env bash
set -euo pipefail

APP_NAME="snip_edit"
PY_FILE="snip_edit.py"
ICO_FILE="icon.ico"
PNG_FALLBACK="icon.png"

echo "==> Starting build for ${APP_NAME}"

if [[ ! -f "$PY_FILE" ]]; then
  echo "ERROR: ${PY_FILE} not found in the current folder."
  echo "Run this script from the project directory that contains ${PY_FILE}."
  exit 1
fi

echo "==> Upgrading pip and installing build dependencies"
python -m pip install --upgrade pip
python -m pip install pyinstaller pillow pywin32

if [[ ! -f "$ICO_FILE" ]]; then
  if [[ -f "$PNG_FALLBACK" ]]; then
    echo "==> ${ICO_FILE} not found, creating it from ${PNG_FALLBACK}"
    python - <<'PY'
from PIL import Image
img = Image.open("icon.png")
img.save(
    "icon.ico",
    format="ICO",
    sizes=[(16,16), (24,24), (32,32), (48,48), (64,64), (128,128), (256,256)]
)
print("Created icon.ico from icon.png")
PY
  else
    echo "WARNING: Neither ${ICO_FILE} nor ${PNG_FALLBACK} was found."
    echo "The build will continue without a custom icon."
  fi
fi

echo "==> Cleaning previous build output"
rm -rf build dist "${APP_NAME}.spec"

if [[ -f "$ICO_FILE" ]]; then
  echo "==> Building EXE with custom icon"
  pyinstaller --onefile --windowed --clean --icon="$ICO_FILE" --name "$APP_NAME" "$PY_FILE"
else
  echo "==> Building EXE without custom icon"
  pyinstaller --onefile --windowed --clean --name "$APP_NAME" "$PY_FILE"
fi

echo
echo "==> Build finished"
echo "Output:"
echo "  dist/${APP_NAME}.exe"
echo
echo "If Windows still shows the old icon, rename the EXE or clear Explorer icon cache."
