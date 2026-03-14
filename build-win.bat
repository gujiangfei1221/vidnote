@echo off
setlocal EnableDelayedExpansion

:: ===============================================================
::   VidNote Windows Build Script
::   Auto-detect env -> Install missing tools -> Build installer
:: ===============================================================

title VidNote Windows Build Tool

echo.
echo  ** VidNote Windows Build Tool **
echo  -------------------------------------------------------
echo.

:: Path settings
set "ROOT_DIR=%~dp0"
set "APP_DIR=%ROOT_DIR%app"
set "RESOURCES_DIR=%APP_DIR%\resources"
set "DIST_DIR=%APP_DIR%\dist"
set "WHISPER_DIR=%ROOT_DIR%.build_cache\whisper.cpp"
set "CACHE_DIR=%ROOT_DIR%.build_cache"
set "FFMPEG_EXE=%CACHE_DIR%\ffmpeg.exe"
set "MODEL_FILE=%CACHE_DIR%\ggml-base.bin"

:: -------------------------------------------------------
:: Proxy settings (for GitHub / HuggingFace access)
:: Set SET_PROXY=0 to disable
:: -------------------------------------------------------
set "SET_PROXY=1"
set "HTTP_PROXY_ADDR=127.0.0.1:10809"
set "SOCKS_PROXY_ADDR=127.0.0.1:10808"

if "%SET_PROXY%"=="1" (
    echo  [PROXY] HTTP/HTTPS -^> %HTTP_PROXY_ADDR%  SOCKS5 -^> %SOCKS_PROXY_ADDR%
    set "HTTP_PROXY=http://%HTTP_PROXY_ADDR%"
    set "HTTPS_PROXY=http://%HTTP_PROXY_ADDR%"
    set "ALL_PROXY=socks5://%SOCKS_PROXY_ADDR%"
    git config --global http.proxy "http://%HTTP_PROXY_ADDR%"
    git config --global https.proxy "http://%HTTP_PROXY_ADDR%"
    set "PIP_INDEX_URL=https://pypi.org/simple"
    echo  [PROXY] Done
    echo.
)

:: -------------------------------------------------------
:: STEP 0: Check admin privileges
:: -------------------------------------------------------
echo [STEP 0] Checking privileges...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [!] Some installs need admin rights.
    echo      Right-click this script and "Run as administrator" if install fails.
    echo.
    pause
)

:: -------------------------------------------------------
:: STEP 1: Check and install tools
:: -------------------------------------------------------
echo [STEP 1] Checking environment...
echo.

:: Check winget
where winget >nul 2>&1
if %errorLevel% neq 0 (
    echo  [X] winget not found. Please install App Installer first.
    echo      Download: https://aka.ms/getwinget
    pause
    exit /b 1
)
echo  [OK] winget ready

:: Check Git
call :check_and_install "git" "Git.Git" "Git"

:: Check Python
python --version 2>&1 | findstr "3\." >nul
if %errorLevel% neq 0 (
    echo  [..] Installing Python 3.11...
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    call :refresh_path
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo  [OK] Python !PY_VER! ready
)

:: Check Node.js
call :check_and_install "node" "OpenJS.NodeJS.LTS" "Node.js LTS"

:: Check CMake
call :check_and_install "cmake" "Kitware.CMake" "CMake"

:: Check C++ compiler (Visual Studio Build Tools)
echo.
echo  [..] Checking C++ compiler...

:: Pre-set vswhere path OUTSIDE if-block to avoid ProgramFiles(x86) parenthesis issue
set "VSWHERE_PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VS_INSTALLER=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vs_installer.exe"

where cl >nul 2>&1
if %errorLevel% equ 0 (
    echo  [OK] C++ compiler ready
    goto :cpp_done
)

set "VCVARS="

:: Method 1: Use vswhere.exe to find VS installation
if exist "!VSWHERE_PATH!" (
    for /f "tokens=*" %%i in ('"!VSWHERE_PATH!" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2^>nul') do (
        if exist "%%i\VC\Auxiliary\Build\vcvars64.bat" set "VCVARS=%%i\VC\Auxiliary\Build\vcvars64.bat"
    )
)

:: Method 2: Hardcoded common paths as fallback
if not defined VCVARS (
    for %%p in (
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
        "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
    ) do (
        if exist %%p set "VCVARS=%%~p"
    )
)

if defined VCVARS (
    echo  [OK] Found vcvars64.bat, initializing C++ env...
    call "!VCVARS!"
    goto :cpp_done
)

echo.
echo  [X] C++ build tools NOT found.
echo.
echo      VS Build Tools is installed, but the C++ workload is missing.
echo      Please install it manually:
echo.
echo      1. Opening Visual Studio Installer now...
echo      2. Click "Modify" on Build Tools 2022
echo      3. Check "Desktop development with C++"
echo      4. Click "Install" and wait for it to finish
echo      5. Then RE-RUN this script
echo.
if exist "!VS_INSTALLER!" (
    start "" "!VS_INSTALLER!"
) else (
    echo      Could not auto-open installer.
    echo      Search "Visual Studio Installer" in Start Menu.
)
pause
exit /b 1

:cpp_done

echo.
echo  -------------------------------------------------------
echo  [OK] All tools ready
echo  -------------------------------------------------------
echo.

:: -------------------------------------------------------
:: Create cache dir
:: -------------------------------------------------------
if not exist "%CACHE_DIR%" mkdir "%CACHE_DIR%"
if not exist "%RESOURCES_DIR%" mkdir "%RESOURCES_DIR%"

:: -------------------------------------------------------
:: STEP 2: Install Python dependencies
:: -------------------------------------------------------
echo [STEP 2] Installing Python dependencies...
cd /d "%ROOT_DIR%"
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
echo  [OK] Python dependencies installed
echo.

:: -------------------------------------------------------
:: STEP 3: Download FFmpeg (cached)
:: -------------------------------------------------------
echo [STEP 3] Preparing FFmpeg...
if exist "%FFMPEG_EXE%" (
    echo  [OK] FFmpeg cached, skipping download
    goto :ffmpeg_done
)
:: Try to recover from previous extraction first
if exist "%CACHE_DIR%\ffmpeg_extracted" (
    echo  [..] Found previous extraction, recovering...
    powershell -command "$f = Get-ChildItem -Path '%CACHE_DIR%\ffmpeg_extracted' -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($f) { Copy-Item $f.FullName '%FFMPEG_EXE%' -Force; Write-Host 'Recovered:' $f.FullName }"
)
if exist "%FFMPEG_EXE%" (
    echo  [OK] FFmpeg recovered from cache
    goto :ffmpeg_done
)

:: Download fresh
echo  [..] Downloading FFmpeg static build...
curl -L -o "%CACHE_DIR%\ffmpeg.zip" "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
if not exist "%CACHE_DIR%\ffmpeg.zip" (
    echo  [X] FFmpeg download FAILED
    pause
    exit /b 1
)
echo  [..] Extracting FFmpeg...
powershell -command "Expand-Archive -Path '%CACHE_DIR%\ffmpeg.zip' -DestinationPath '%CACHE_DIR%\ffmpeg_extracted' -Force; $f = Get-ChildItem -Path '%CACHE_DIR%\ffmpeg_extracted' -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue | Select-Object -First 1; if ($f) { Copy-Item $f.FullName '%FFMPEG_EXE%' -Force; Write-Host 'Copied:' $f.FullName } else { Write-Host 'ERROR: ffmpeg.exe not found in zip' }"
del "%CACHE_DIR%\ffmpeg.zip" >nul 2>&1
if not exist "%FFMPEG_EXE%" (
    echo  [X] FFmpeg extract FAILED - ffmpeg.exe not found
    echo      Check .build_cache\ffmpeg_extracted\ manually
    pause
    exit /b 1
)
echo  [OK] FFmpeg ready

:ffmpeg_done
echo.

:: -------------------------------------------------------
:: STEP 4: Build whisper.cpp (cached)
:: -------------------------------------------------------
echo [STEP 4] Preparing whisper.cpp...
set "WHISPER_EXE=%WHISPER_DIR%\build\bin\Release\whisper-cli.exe"
if exist "%WHISPER_EXE%" (
    echo  [OK] whisper-cli.exe cached, skipping build
    goto :whisper_done
)

echo  [..] Cloning whisper.cpp...
if exist "%WHISPER_DIR%" rmdir /s /q "%WHISPER_DIR%"
git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "%WHISPER_DIR%"

echo  [..] Building whisper.cpp (CPU)...
cd /d "%WHISPER_DIR%"
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
cd /d "%ROOT_DIR%"

if not exist "%WHISPER_EXE%" (
    echo  [X] whisper.cpp build FAILED. Check C++ environment.
    pause
    exit /b 1
)
echo  [OK] whisper.cpp build done

:whisper_done
echo.

:: -------------------------------------------------------
:: STEP 5: Download Whisper model (cached)
:: -------------------------------------------------------
echo [STEP 5] Preparing Whisper model...
if exist "%MODEL_FILE%" (
    echo  [OK] ggml-base.bin cached, skipping download
    goto :model_done
)

echo  [..] Downloading Whisper base model ~141MB...
curl -L -o "%MODEL_FILE%" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
if not exist "%MODEL_FILE%" (
    echo  [X] Model download FAILED
    pause
    exit /b 1
)
echo  [OK] Model downloaded

:model_done
echo.

:: -------------------------------------------------------
:: STEP 6: PyInstaller - package Python backend
:: -------------------------------------------------------
echo [STEP 6] PyInstaller packaging backend...
cd /d "%ROOT_DIR%"
pyinstaller --name api_backend --onefile --add-data "processor;processor" --add-data "config.py;." --add-data ".env.example;." --hidden-import opencc --hidden-import yt_dlp --hidden-import requests --hidden-import dotenv --hidden-import watchdog --collect-data opencc --distpath "%ROOT_DIR%dist" api.py

if not exist "%ROOT_DIR%dist\api_backend.exe" (
    echo  [X] PyInstaller FAILED
    pause
    exit /b 1
)
echo  [OK] Python backend packaged
echo.

:: -------------------------------------------------------
:: STEP 7: Assemble resources directory
:: -------------------------------------------------------
echo [STEP 7] Assembling resources...
if exist "%RESOURCES_DIR%" rmdir /s /q "%RESOURCES_DIR%"
mkdir "%RESOURCES_DIR%"

copy "%ROOT_DIR%dist\api_backend.exe"  "%RESOURCES_DIR%\api_backend.exe" >nul
copy "%FFMPEG_EXE%"                    "%RESOURCES_DIR%\ffmpeg.exe"      >nul
copy "%WHISPER_EXE%"                   "%RESOURCES_DIR%\whisper-cli.exe" >nul
copy "%MODEL_FILE%"                    "%RESOURCES_DIR%\ggml-base.bin"   >nul

echo  [OK] Resources assembled
echo.

:: -------------------------------------------------------
:: STEP 8: Build Electron installer
:: -------------------------------------------------------
echo [STEP 8] Building Electron Windows installer...
cd /d "%APP_DIR%"
npm install --silent
npm run build:win

if %errorLevel% neq 0 (
    echo  [X] Electron build FAILED
    pause
    exit /b 1
)
echo.

:: -------------------------------------------------------
:: DONE
:: -------------------------------------------------------
echo  =======================================================
echo  [DONE] Build complete! Output:
echo.
for %%f in ("%DIST_DIR%\*.exe") do echo     %%f
echo.
echo  =======================================================
echo.

explorer "%DIST_DIR%"

pause
exit /b 0


:: ===============================================================
::   Helper: check command, install via winget if missing
:: ===============================================================
:check_and_install
where %~1 >nul 2>&1
if %errorLevel% neq 0 (
    echo  [..] Installing %~3...
    winget install -e --id %~2 --accept-package-agreements --accept-source-agreements
    call :refresh_path
) else (
    echo  [OK] %~3 ready
)
exit /b 0

:: ===============================================================
::   Helper: refresh PATH from registry
:: ===============================================================
:refresh_path
for /f "tokens=*" %%a in ('powershell -command "[System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')"') do set "PATH=%%a"
exit /b 0
