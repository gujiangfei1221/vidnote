const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    // 选择文件
    selectVideo: () => ipcRenderer.invoke('select-video'),

    // 下载视频
    downloadVideo: (params) => ipcRenderer.send('download-video', params),
    getVideoInfo: (params) => ipcRenderer.send('get-video-info', params),

    // 处理视频
    processVideo: (params) => ipcRenderer.send('process-video', params),

    // 依赖检查
    checkDeps: () => ipcRenderer.send('check-deps'),

    // 配置
    loadConfig: () => ipcRenderer.send('load-config'),
    saveConfig: (params) => ipcRenderer.send('save-config', params),

    // 历史记录
    listHistory: (params) => ipcRenderer.send('list-history', params),

    // 文件操作
    openFolder: (path) => ipcRenderer.send('open-folder', path),
    openFile: (path) => ipcRenderer.send('open-file', path),
    copyToClipboard: (text) => ipcRenderer.send('copy-to-clipboard', text),

    // 监听 Python 消息
    onPythonMessage: (callback) => {
        ipcRenderer.on('python-message', (event, msg) => callback(msg));
    },
});
