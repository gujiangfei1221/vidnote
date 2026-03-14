#!/bin/bash
set -e

# ===============================================================
#   VidNote macOS Build Script (Apple Silicon)
#   Auto-detect env -> Install missing tools -> Build DMG
# ===============================================================

echo ""
echo "  ** VidNote macOS Build Tool **"
echo "  -------------------------------------------------------"
echo ""

# Path settings (scripts/ is inside ROOT_DIR)
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
APP_DIR="$ROOT_DIR/app"
RESOURCES_DIR="$APP_DIR/resources"
DIST_DIR="$APP_DIR/dist"
CACHE_DIR="$ROOT_DIR/.build_cache"
WHISPER_DIR="$CACHE_DIR/whisper.cpp"
FFMPEG_BIN="$CACHE_DIR/ffmpeg"
MODEL_FILE="$CACHE_DIR/ggml-base.bin"
CPU_CORES=$(sysctl -n hw.physicalcpu 2>/dev/null || echo 4)

# -------------------------------------------------------
# STEP 1: Check and install tools
# -------------------------------------------------------
echo "[STEP 1] Checking environment..."
echo ""

# Check Homebrew
if ! command -v brew &>/dev/null; then
    echo "  [..] Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "  [OK] Homebrew ready"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "  [..] Installing Python 3..."
    brew install python@3.11
fi
PY_VER=$(python3 --version 2>&1)
echo "  [OK] $PY_VER ready"

# Check Node.js
if ! command -v node &>/dev/null; then
    echo "  [..] Installing Node.js..."
    brew install node
fi
NODE_VER=$(node --version 2>&1)
echo "  [OK] Node.js $NODE_VER ready"

# Check CMake
if ! command -v cmake &>/dev/null; then
    echo "  [..] Installing CMake..."
    brew install cmake
fi
echo "  [OK] CMake ready"

# Check pip / pyinstaller
if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null; then
    echo "  [..] Installing pip..."
    python3 -m ensurepip --upgrade
fi
echo "  [OK] pip ready"

echo ""
echo "  -------------------------------------------------------"
echo "  [OK] All tools ready"
echo "  -------------------------------------------------------"
echo ""

# -------------------------------------------------------
# Create cache dir
# -------------------------------------------------------
mkdir -p "$CACHE_DIR"
mkdir -p "$RESOURCES_DIR"

# -------------------------------------------------------
# STEP 2: Install Python dependencies
# -------------------------------------------------------
echo "[STEP 2] Installing Python dependencies..."
cd "$BACKEND_DIR"
pip3 install -r requirements.txt --quiet
pip3 install pyinstaller --quiet
echo "  [OK] Python dependencies installed"
echo ""

# -------------------------------------------------------
# STEP 3: Prepare FFmpeg (cached)
# -------------------------------------------------------
echo "[STEP 3] Preparing FFmpeg..."
if [ -f "$FFMPEG_BIN" ]; then
    echo "  [OK] FFmpeg cached, skipping"
else
    if command -v ffmpeg &>/dev/null; then
        echo "  [..] Copying system ffmpeg..."
        cp "$(which ffmpeg)" "$FFMPEG_BIN"
    else
        echo "  [..] Installing FFmpeg via Homebrew..."
        brew install ffmpeg
        cp "$(which ffmpeg)" "$FFMPEG_BIN"
    fi
    chmod +x "$FFMPEG_BIN"
    echo "  [OK] FFmpeg ready"
fi
echo ""

# -------------------------------------------------------
# STEP 4: Build whisper.cpp with Metal (cached)
# -------------------------------------------------------
echo "[STEP 4] Preparing whisper.cpp..."
WHISPER_CLI="$WHISPER_DIR/build/bin/whisper-cli"
if [ -f "$WHISPER_CLI" ]; then
    echo "  [OK] whisper-cli cached, skipping build"
else
    echo "  [..] Cloning whisper.cpp..."
    rm -rf "$WHISPER_DIR"
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR"

    echo "  [..] Building whisper.cpp (Metal GPU acceleration)..."
    cd "$WHISPER_DIR"
    cmake -B build -DWHISPER_METAL=ON
    cmake --build build --config Release -j"$CPU_CORES"
    cd "$ROOT_DIR"

    if [ ! -f "$WHISPER_CLI" ]; then
        echo "  [X] whisper.cpp build FAILED"
        exit 1
    fi
    echo "  [OK] whisper.cpp build done"
fi
echo ""

# -------------------------------------------------------
# STEP 5: Download Whisper model (cached)
# -------------------------------------------------------
echo "[STEP 5] Preparing Whisper model..."
if [ -f "$MODEL_FILE" ]; then
    echo "  [OK] ggml-base.bin cached, skipping download"
else
    echo "  [..] Downloading Whisper base model ~141MB..."
    curl -L -o "$MODEL_FILE" \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
    if [ ! -f "$MODEL_FILE" ]; then
        echo "  [X] Model download FAILED"
        exit 1
    fi
    echo "  [OK] Model downloaded"
fi
echo ""

# -------------------------------------------------------
# STEP 6: PyInstaller - package Python backend
# -------------------------------------------------------
echo "[STEP 6] PyInstaller packaging backend..."
cd "$BACKEND_DIR"
pyinstaller --name api_backend --onefile \
    --add-data "processor:processor" \
    --add-data "config.py:." \
    --add-data "$ROOT_DIR/.env.example:." \
    --hidden-import opencc \
    --hidden-import yt_dlp \
    --hidden-import requests \
    --hidden-import dotenv \
    --hidden-import watchdog \
    --collect-data opencc \
    --distpath "$ROOT_DIR/dist" \
    api.py

if [ ! -f "$ROOT_DIR/dist/api_backend" ]; then
    echo "  [X] PyInstaller FAILED"
    exit 1
fi
echo "  [OK] Python backend packaged"
echo ""

# -------------------------------------------------------
# STEP 7: Assemble resources directory
# -------------------------------------------------------
echo "[STEP 7] Assembling resources..."
rm -rf "$RESOURCES_DIR"
mkdir -p "$RESOURCES_DIR"

cp "$ROOT_DIR/dist/api_backend"  "$RESOURCES_DIR/api_backend"
cp "$FFMPEG_BIN"                 "$RESOURCES_DIR/ffmpeg"
cp "$WHISPER_CLI"                "$RESOURCES_DIR/whisper-cli"
cp "$MODEL_FILE"                 "$RESOURCES_DIR/ggml-base.bin"

# Copy whisper.cpp runtime dylibs
echo "  [..] Copying dylibs..."
find "$WHISPER_DIR/build" -name "*.dylib" -exec cp {} "$RESOURCES_DIR/" \;

# Copy Metal shader if exists
find "$WHISPER_DIR/build" -name "*.metallib" -exec cp {} "$RESOURCES_DIR/" \; 2>/dev/null || true

# Fix rpath for whisper-cli and dylibs
echo "  [..] Fixing rpath..."
install_name_tool -add_rpath "@executable_path" "$RESOURCES_DIR/whisper-cli" 2>/dev/null || true
for lib in "$RESOURCES_DIR"/*.dylib; do
    [ -f "$lib" ] || continue
    install_name_tool -id "@rpath/$(basename "$lib")" "$lib" 2>/dev/null || true
    install_name_tool -add_rpath "@loader_path" "$lib" 2>/dev/null || true
    echo "  [OK] Fixed: $(basename "$lib")"
done

# Ensure all binaries are executable
chmod +x "$RESOURCES_DIR/api_backend" \
         "$RESOURCES_DIR/ffmpeg" \
         "$RESOURCES_DIR/whisper-cli"
chmod +x "$RESOURCES_DIR"/*.dylib 2>/dev/null || true

echo "  [OK] Resources assembled"
echo ""

# -------------------------------------------------------
# STEP 8: Build Electron installer
# -------------------------------------------------------
echo "[STEP 8] Building Electron macOS installer..."
cd "$APP_DIR"
npm install --silent
# Skip code signing for local builds (remove CSC_IDENTITY_AUTO_DISCOVERY for release builds)
CSC_IDENTITY_AUTO_DISCOVERY=false npm run build:mac

if [ $? -ne 0 ]; then
    echo "  [X] Electron build FAILED"
    exit 1
fi
echo ""

# -------------------------------------------------------
# DONE
# -------------------------------------------------------
echo "  ======================================================="
echo "  [DONE] Build complete! Output:"
echo ""
for f in "$DIST_DIR"/*.dmg "$DIST_DIR"/*.zip; do
    [ -f "$f" ] && echo "    $f"
done
echo ""
echo "  ======================================================="
echo ""

# Open output directory
open "$DIST_DIR" 2>/dev/null || true
