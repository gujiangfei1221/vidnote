@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ═══════════════════════════════════════════════════════════════
::   VidNote Windows 一键打包脚本
::   功能：自动检测环境 → 安装缺失工具 → 构建 Windows 安装包
::   作者：gujiangfei
:: ═══════════════════════════════════════════════════════════════

title VidNote Windows 构建工具

echo.
echo  ██╗   ██╗██╗██████╗ ███╗   ██╗ ██████╗ ████████╗███████╗
echo  ██║   ██║██║██╔══██╗████╗  ██║██╔═══██╗╚══██╔══╝██╔════╝
echo  ██║   ██║██║██║  ██║██╔██╗ ██║██║   ██║   ██║   █████╗
echo  ╚██╗ ██╔╝██║██║  ██║██║╚██╗██║██║   ██║   ██║   ██╔══╝
echo   ╚████╔╝ ██║██████╔╝██║ ╚████║╚██████╔╝   ██║   ███████╗
echo    ╚═══╝  ╚═╝╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝   ╚══════╝
echo.
echo  Windows 一键打包脚本 ^| VidNote Build Tool
echo  ───────────────────────────────────────────────────────────
echo.

:: 路径设置
set "ROOT_DIR=%~dp0"
set "APP_DIR=%ROOT_DIR%app"
set "RESOURCES_DIR=%APP_DIR%\resources"
set "DIST_DIR=%APP_DIR%\dist"
set "WHISPER_DIR=%ROOT_DIR%.build_cache\whisper.cpp"
set "CACHE_DIR=%ROOT_DIR%.build_cache"
set "FFMPEG_EXE=%CACHE_DIR%\ffmpeg.exe"
set "MODEL_FILE=%CACHE_DIR%\ggml-base.bin"

:: ───────────────────────────────────────────────────────────
:: 代理设置（国内访问 GitHub / HuggingFace 加速）
:: 如不需要代理，将下方 SET_PROXY 改为 0
:: ───────────────────────────────────────────────────────────
set "SET_PROXY=1"
set "HTTP_PROXY_ADDR=127.0.0.1:10809"
set "SOCKS_PROXY_ADDR=127.0.0.1:10808"

if "%SET_PROXY%"=="1" (
    echo  🌐 设置代理：HTTP/HTTPS → %HTTP_PROXY_ADDR%  SOCKS5 → %SOCKS_PROXY_ADDR%
    set "HTTP_PROXY=http://%HTTP_PROXY_ADDR%"
    set "HTTPS_PROXY=http://%HTTP_PROXY_ADDR%"
    set "ALL_PROXY=socks5://%SOCKS_PROXY_ADDR%"
    :: git 代理
    git config --global http.proxy "http://%HTTP_PROXY_ADDR%"
    git config --global https.proxy "http://%HTTP_PROXY_ADDR%"
    :: pip 代理（通过环境变量生效）
    set "PIP_INDEX_URL=https://pypi.org/simple"
    echo  ✅ 代理设置完成
    echo.
)

:: ───────────────────────────────────────────────────────────
:: STEP 0: 检查管理员权限（winget 安装需要）
:: ───────────────────────────────────────────────────────────
echo [STEP 0] 检查运行权限...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  ⚠️  提示：部分安装操作需要管理员权限
    echo     如果工具安装失败，请右键脚本选择"以管理员身份运行"
    echo.
    pause
)

:: ───────────────────────────────────────────────────────────
:: STEP 1: 检查并安装基础工具
:: ───────────────────────────────────────────────────────────
echo [STEP 1] 检查基础环境...
echo.

:: 检查 winget
where winget >nul 2>&1
if %errorLevel% neq 0 (
    echo  ❌ 未找到 winget，请手动安装 App Installer 后重试
    echo     下载地址：https://aka.ms/getwinget
    pause & exit /b 1
)
echo  ✅ winget 已就绪

:: ── 检查 Git ──
call :check_and_install "git" "Git.Git" "Git"

:: ── 检查 Python 3.11 ──
python --version 2>&1 | findstr "3\." >nul
if %errorLevel% neq 0 (
    echo  ⚙️  安装 Python 3.11...
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    :: 刷新PATH
    call :refresh_path
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo  ✅ Python !PY_VER! 已就绪
)

:: ── 检查 Node.js ──
call :check_and_install "node" "OpenJS.NodeJS.LTS" "Node.js 20 LTS"

:: ── 检查 CMake ──
call :check_and_install "cmake" "Kitware.CMake" "CMake"

:: ── 检查 Visual Studio Build Tools (C++ 编译器) ──
echo.
echo  🔍 检查 C++ 编译器...
where cl >nul 2>&1
if %errorLevel% neq 0 (
    :: 尝试找到 vcvars64.bat
    set "VCVARS="
    for %%p in (
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
        "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
    ) do (
        if exist %%p set "VCVARS=%%p"
    )

    if defined VCVARS (
        echo  ✅ 找到 Visual Studio，初始化编译环境...
        call "!VCVARS!"
    ) else (
        echo  ⚙️  安装 Visual Studio Build Tools 2022（含C++工作负载）...
        echo     这个比较大（约3GB），请耐心等待...
        winget install -e --id Microsoft.VisualStudio.2022.BuildTools --accept-package-agreements --accept-source-agreements ^
            --override "--quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
        echo  ✅ VS Build Tools 安装完成，请重新运行此脚本以激活编译环境
        pause & exit /b 0
    )
) else (
    echo  ✅ C++ 编译器已就绪
)

echo.
echo  ───────────────────────────────────────────────────────────
echo  ✅ 基础环境检查完成
echo  ───────────────────────────────────────────────────────────
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 2: 创建缓存目录
:: ───────────────────────────────────────────────────────────
if not exist "%CACHE_DIR%" mkdir "%CACHE_DIR%"
if not exist "%RESOURCES_DIR%" mkdir "%RESOURCES_DIR%"

:: ───────────────────────────────────────────────────────────
:: STEP 3: 安装 Python 依赖
:: ───────────────────────────────────────────────────────────
echo [STEP 2] 安装 Python 依赖...
cd /d "%ROOT_DIR%"
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet
echo  ✅ Python 依赖安装完成
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 4: 下载 FFmpeg（有缓存则跳过）
:: ───────────────────────────────────────────────────────────
echo [STEP 3] 准备 FFmpeg...
if exist "%FFMPEG_EXE%" (
    echo  ✅ FFmpeg 已缓存，跳过下载
) else (
    echo  ⬇️  下载 FFmpeg Windows 静态包...
    curl -L -o "%CACHE_DIR%\ffmpeg.zip" ^
        "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    echo  📦 解压 FFmpeg...
    powershell -command "Expand-Archive -Path '%CACHE_DIR%\ffmpeg.zip' -DestinationPath '%CACHE_DIR%\ffmpeg_extracted' -Force"
    :: 找到 ffmpeg.exe 并复制
    for /r "%CACHE_DIR%\ffmpeg_extracted" %%f in (ffmpeg.exe) do (
        copy "%%f" "%FFMPEG_EXE%" >nul
        goto :ffmpeg_done
    )
    :ffmpeg_done
    del "%CACHE_DIR%\ffmpeg.zip" >nul 2>&1
    echo  ✅ FFmpeg 准备完成
)
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 5: 编译 whisper.cpp（有缓存则跳过）
:: ───────────────────────────────────────────────────────────
echo [STEP 4] 准备 whisper.cpp...
set "WHISPER_EXE=%WHISPER_DIR%\build\bin\Release\whisper-cli.exe"
if exist "%WHISPER_EXE%" (
    echo  ✅ whisper-cli.exe 已缓存，跳过编译
) else (
    echo  📥 克隆 whisper.cpp 仓库...
    if exist "%WHISPER_DIR%" rmdir /s /q "%WHISPER_DIR%"
    git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git "%WHISPER_DIR%"

    echo  🔨 编译 whisper.cpp（CPU 版本）...
    cd /d "%WHISPER_DIR%"
    cmake -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release
    cd /d "%ROOT_DIR%"

    if not exist "%WHISPER_EXE%" (
        echo  ❌ whisper.cpp 编译失败，请检查 C++ 环境
        pause & exit /b 1
    )
    echo  ✅ whisper.cpp 编译完成
)
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 6: 下载 Whisper 模型（有缓存则跳过）
:: ───────────────────────────────────────────────────────────
echo [STEP 5] 准备 Whisper 模型...
if exist "%MODEL_FILE%" (
    echo  ✅ ggml-base.bin 已缓存，跳过下载
) else (
    echo  ⬇️  下载 Whisper base 模型 ^(约141MB^)...
    curl -L -o "%MODEL_FILE%" ^
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
    echo  ✅ 模型下载完成
)
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 7: PyInstaller 打包 Python 后端
:: ───────────────────────────────────────────────────────────
echo [STEP 6] PyInstaller 打包 Python 后端...
cd /d "%ROOT_DIR%"
pyinstaller --name api_backend --onefile ^
    --add-data "processor;processor" ^
    --add-data "config.py;." ^
    --add-data ".env.example;." ^
    --hidden-import opencc ^
    --hidden-import yt_dlp ^
    --hidden-import requests ^
    --hidden-import dotenv ^
    --hidden-import watchdog ^
    --collect-data opencc ^
    --distpath "%ROOT_DIR%dist" ^
    api.py

if not exist "%ROOT_DIR%dist\api_backend.exe" (
    echo  ❌ PyInstaller 打包失败
    pause & exit /b 1
)
echo  ✅ Python 后端打包完成
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 8: 组装 resources 目录
:: ───────────────────────────────────────────────────────────
echo [STEP 7] 组装 resources 目录...
:: 清理旧的 resources
if exist "%RESOURCES_DIR%" rmdir /s /q "%RESOURCES_DIR%"
mkdir "%RESOURCES_DIR%"

copy "%ROOT_DIR%dist\api_backend.exe"  "%RESOURCES_DIR%\api_backend.exe" >nul
copy "%FFMPEG_EXE%"                    "%RESOURCES_DIR%\ffmpeg.exe"      >nul
copy "%WHISPER_EXE%"                   "%RESOURCES_DIR%\whisper-cli.exe" >nul
copy "%MODEL_FILE%"                    "%RESOURCES_DIR%\ggml-base.bin"   >nul

echo  ✅ resources 目录组装完成
echo.

:: ───────────────────────────────────────────────────────────
:: STEP 9: 安装 Node 依赖 & 构建 Electron
:: ───────────────────────────────────────────────────────────
echo [STEP 8] 构建 Electron Windows 安装包...
cd /d "%APP_DIR%"
npm install --silent
npm run build:win

if %errorLevel% neq 0 (
    echo  ❌ Electron 打包失败
    pause & exit /b 1
)
echo.

:: ───────────────────────────────────────────────────────────
:: 完成！
:: ───────────────────────────────────────────────────────────
echo  ───────────────────────────────────────────────────────────
echo  🎉 打包完成！安装包位置：
echo.
for %%f in ("%DIST_DIR%\*.exe") do echo     %%f
echo.
echo  ───────────────────────────────────────────────────────────
echo.

:: 打开输出目录
explorer "%DIST_DIR%"

pause
exit /b 0


:: ═══════════════════════════════════════════════════════════════
::   辅助函数：检查命令是否存在，不存在则用 winget 安装
::   用法：call :check_and_install "命令名" "winget包ID" "显示名"
:: ═══════════════════════════════════════════════════════════════
:check_and_install
where %~1 >nul 2>&1
if %errorLevel% neq 0 (
    echo  ⚙️  安装 %~3...
    winget install -e --id %~2 --accept-package-agreements --accept-source-agreements
    call :refresh_path
) else (
    echo  ✅ %~3 已就绪
)
exit /b 0

:: ═══════════════════════════════════════════════════════════════
::   辅助函数：刷新 PATH 环境变量
:: ═══════════════════════════════════════════════════════════════
:refresh_path
for /f "tokens=*" %%a in ('powershell -command "[System.Environment]::GetEnvironmentVariable(\"Path\", \"Machine\") + \";\" + [System.Environment]::GetEnvironmentVariable(\"Path\", \"User\")"') do set "PATH=%%a"
exit /b 0
