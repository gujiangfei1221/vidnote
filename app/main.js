const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// ─── 文件日志（打包后方便排查问题）───
let logStream = null;
function initLog() {
    const logPath = path.join(app.getPath('userData'), 'vidnote.log');
    logStream = fs.createWriteStream(logPath, { flags: 'w', encoding: 'utf-8' });
    const origLog = console.log;
    console.log = (...args) => {
        const line = `[${new Date().toISOString()}] ${args.join(' ')}`;
        origLog(line);
        if (logStream) logStream.write(line + '\n');
    };
    console.log(`[Main] Log file: ${logPath}`);
}

let mainWindow;
let pythonProcess = null;

// ─── 路径计算 ───
// 开发模式：app/ 的上级就是项目根目录
// 打包模式：使用用户数据目录保存配置和输出
function getProjectRoot() {
    return app.isPackaged
        ? app.getPath('userData')
        : path.resolve(__dirname, '..');
}

function getBinPath() {
    if (app.isPackaged) {
        // 打包后：从 Contents/Resources/bin 获取内置工具
        return path.join(process.resourcesPath, 'bin');
    }
    return null; // 开发模式不使用内置工具
}

// ─── 窗口创建 ───
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1100,
        height: 780,
        minWidth: 900,
        minHeight: 650,
        titleBarStyle: 'hiddenInset',
        trafficLightPosition: { x: 16, y: 18 },
        backgroundColor: '#0f0f1a',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });

    mainWindow.loadFile(path.join(__dirname, 'index.html'));

    mainWindow.on('closed', () => {
        mainWindow = null;
        killPython();
    });
}

// ─── Python 进程管理 ───
function startPython() {
    if (pythonProcess) return;

    const projectRoot = getProjectRoot();
    const binPath = getBinPath();

    if (binPath) {
        // ══════════════════════════════════════
        // 打包模式：启动内置的 api_backend 可执行文件
        // ══════════════════════════════════════
        const isWin = process.platform === 'win32';
        const backendPath = path.join(binPath, isWin ? 'api_backend.exe' : 'api_backend');
        const ffmpegPath = path.join(binPath, isWin ? 'ffmpeg.exe' : 'ffmpeg');
        const whisperPath = path.join(binPath, isWin ? 'whisper-cli.exe' : 'whisper-cli');
        const modelPath = path.join(binPath, 'ggml-base.bin');

        // 确保用户数据目录存在
        const outputDir = path.join(projectRoot, 'output');
        fs.mkdirSync(outputDir, { recursive: true });

        console.log(`[Main] Packaged mode`);
        console.log(`[Main] Backend: ${backendPath}`);
        console.log(`[Main] Bin dir: ${binPath}`);

        pythonProcess = spawn(backendPath, [], {
            cwd: projectRoot,
            stdio: ['pipe', 'pipe', 'pipe'],
            env: {
                ...process.env,
                PYTHONUNBUFFERED: '1',
                PYTHONIOENCODING: 'utf-8',
                PYTHONUTF8: '1',
                // 将 bin 目录加入 PATH，让 yt-dlp 也能找到 ffmpeg
                PATH: binPath + path.delimiter + (process.env.PATH || ''),
                // 通过环境变量传入所有工具路径
                PROJECT_ROOT: projectRoot,
                FFMPEG_PATH: ffmpegPath,
                WHISPER_CPP_PATH: whisperPath,
                WHISPER_MODEL_PATH: modelPath,
                OUTPUT_DIR: outputDir,
            },
        });
    } else {
        // ══════════════════════════════════════
        // 开发模式：使用 conda Python 环境
        // ══════════════════════════════════════
        const homeDir = process.env.HOME || process.env.USERPROFILE;

        const candidatePaths = [
            path.join(homeDir, 'miniconda3', 'envs', 'vidnote', 'bin', 'python'),
            path.join(homeDir, 'miniforge3', 'envs', 'vidnote', 'bin', 'python'),
            path.join(homeDir, 'opt', 'miniconda3', 'envs', 'vidnote', 'bin', 'python'),
            '/opt/miniconda3/envs/vidnote/bin/python',
            '/opt/miniforge3/envs/vidnote/bin/python',
            '/opt/homebrew/Caskroom/miniconda/base/envs/vidnote/bin/python',
        ];

        let pythonPath = 'python3';
        for (const p of candidatePaths) {
            if (fs.existsSync(p)) {
                pythonPath = p;
                break;
            }
        }

        console.log(`[Main] Dev mode`);
        console.log(`[Main] Python: ${pythonPath}`);
        console.log(`[Main] Working dir: ${projectRoot}`);

        pythonProcess = spawn(pythonPath, [path.join(projectRoot, 'api.py')], {
            cwd: projectRoot,
            stdio: ['pipe', 'pipe', 'pipe'],
            env: { ...process.env, PYTHONUNBUFFERED: '1' },
        });
    }

    // ─── 共享的 stdout/stderr 处理 ───
    let buffer = '';

    pythonProcess.stdout.setEncoding('utf-8');
    pythonProcess.stdout.on('data', (data) => {
        buffer += data;
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
            if (!line.trim()) continue;
            try {
                const msg = JSON.parse(line);
                console.log(`[Python] ${msg.type}`);
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.webContents.send('python-message', msg);
                }
            } catch (e) {
                console.log(`[Python stdout] ${line}`);
            }
        }
    });

    pythonProcess.stderr.setEncoding('utf-8');
    pythonProcess.stderr.on('data', (data) => {
        console.log(`[Python stderr] ${data.trim()}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`[Main] Python process exited with code ${code}`);
        pythonProcess = null;
    });
}

function killPython() {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
    }
}

function sendToPython(action, params = {}) {
    if (!pythonProcess) {
        startPython();
        setTimeout(() => {
            if (pythonProcess && pythonProcess.stdin.writable) {
                const cmd = JSON.stringify({ action, params }) + '\n';
                pythonProcess.stdin.write(cmd);
            }
        }, 1500);
    } else {
        const cmd = JSON.stringify({ action, params }) + '\n';
        pythonProcess.stdin.write(cmd);
    }
}

// ─── IPC 处理器 ───
ipcMain.handle('select-video', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        title: '选择视频文件',
        properties: ['openFile'],
        filters: [
            { name: '视频文件', extensions: ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv'] },
            { name: '所有文件', extensions: ['*'] },
        ],
    });
    return result.canceled ? null : result.filePaths[0];
});

ipcMain.on('process-video', (event, params) => {
    sendToPython('process_video', params);
});

ipcMain.on('download-video', (event, params) => {
    sendToPython('download_video', params);
});

ipcMain.on('get-video-info', (event, params) => {
    sendToPython('get_video_info', params);
});

ipcMain.on('check-deps', () => {
    sendToPython('check_deps');
});

ipcMain.on('load-config', () => {
    sendToPython('load_config');
});

ipcMain.on('save-config', (event, params) => {
    sendToPython('save_config', params);
});

ipcMain.on('list-history', (event, params) => {
    sendToPython('list_history', params || {});
});

ipcMain.on('open-folder', (event, folderPath) => {
    shell.openPath(folderPath);
});

ipcMain.on('open-file', (event, filePath) => {
    if (filePath.startsWith('http://') || filePath.startsWith('https://')) {
        shell.openExternal(filePath);
    } else {
        shell.openPath(filePath);
    }
});

ipcMain.on('copy-to-clipboard', (event, text) => {
    const { clipboard } = require('electron');
    clipboard.writeText(text);
});

// ─── 应用生命周期 ───
app.whenReady().then(() => {
    initLog();
    createWindow();
    startPython();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    killPython();
    if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
    killPython();
});
