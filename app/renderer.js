/* ═══════════════════════════════════════════════════
   渲染进程 — 前端交互逻辑
   ═══════════════════════════════════════════════════ */

// ─── 状态 ───
let selectedVideoPath = null;
let currentResult = null;
let isProcessing = false;
let isDownloading = false;
let currentInputMode = 'file'; // 'file' | 'url'

// ─── DOM 元素 ───
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropZone = $('#drop-zone');
const dropZoneContent = $('#drop-zone-content');
const fileSelected = $('#file-selected');
const fileName = $('#file-name');
const filePath = $('#file-path');
const btnSelectFile = $('#btn-select-file');
const btnRemoveFile = $('#btn-remove-file');
const btnStart = $('#btn-start');
const pipeline = $('#pipeline');
const progressDetail = $('#progress-detail');
const resultPanel = $('#result-panel');
const resultContent = $('#result-content');
const resultMeta = $('#result-meta');
const keyframesGrid = $('#keyframes-grid');
const statusDot = $('#status-dot');
const statusText = $('#status-text');

// ─── 导航 ───
$$('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
        const view = btn.dataset.view;
        $$('.nav-item').forEach(n => n.classList.remove('active'));
        btn.classList.add('active');
        $$('.view').forEach(v => v.classList.remove('active'));
        $(`#view-${view}`).classList.add('active');

        if (view === 'history') loadHistory();
        if (view === 'settings') loadConfig();
    });
});

// ─── 输入模式切换 ───
$$('.input-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        $$('.input-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        currentInputMode = tab.dataset.inputMode;

        if (currentInputMode === 'file') {
            dropZone.classList.remove('hidden');
            $('#url-zone').classList.add('hidden');
        } else {
            dropZone.classList.add('hidden');
            $('#url-zone').classList.remove('hidden');
        }

        // 切换模式时重置按钮状态
        if (currentInputMode === 'url') {
            btnStart.disabled = true;
        } else {
            btnStart.disabled = !selectedVideoPath;
        }
    });
});

// ─── URL 输入区 ───
$('#btn-fetch-info').addEventListener('click', () => {
    const url = $('#url-input').value.trim();
    if (!url) return;

    $('#btn-fetch-info').textContent = '⏳';
    $('#btn-fetch-info').disabled = true;
    $('#video-preview-card').classList.add('hidden');

    window.api.getVideoInfo({ url });
});

$('#url-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') $('#btn-fetch-info').click();
});

$('#btn-download-process').addEventListener('click', () => {
    const url = $('#url-input').value.trim();
    if (!url || isDownloading || isProcessing) return;

    startDownloadAndProcess(url);
});

function startDownloadAndProcess(url) {
    isDownloading = true;
    isProcessing = true;
    btnStart.disabled = true;
    btnStart.innerHTML = '<span class="btn-icon">⏳</span> 处理中...';

    // 显示进度流水线
    pipeline.classList.remove('hidden');
    progressDetail.classList.remove('hidden');
    resultPanel.classList.add('hidden');
    $$('.pipeline-step').forEach(step => step.classList.remove('active', 'done'));

    // 标记下载步骤（步骤1）为进行中
    updateProgress(1, 6, '视频下载', '正在下载视频...');

    // 显示下载进度条
    const barWrap = $('#download-bar-wrap');
    barWrap.classList.remove('hidden');
    $('#download-bar-fill').style.width = '0%';
    $('#download-bar-info').textContent = '正在解析链接...';

    $('#video-preview-card').classList.add('hidden');

    window.api.downloadVideo({ url });
}

// ─── 拖拽上传 ───
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        selectFile(files[0].path);
    }
});

btnSelectFile.addEventListener('click', async () => {
    const path = await window.api.selectVideo();
    if (path) selectFile(path);
});

btnRemoveFile.addEventListener('click', () => {
    clearFile();
});

function selectFile(path) {
    selectedVideoPath = path;
    const name = path.split('/').pop();
    fileName.textContent = name;
    filePath.textContent = path;

    dropZoneContent.classList.add('hidden');
    fileSelected.classList.remove('hidden');
    dropZone.classList.add('has-file');
    btnStart.disabled = false;
}

function clearFile() {
    selectedVideoPath = null;
    dropZoneContent.classList.remove('hidden');
    fileSelected.classList.add('hidden');
    dropZone.classList.remove('has-file');
    btnStart.disabled = true;
}

// ─── 开始处理（本地文件模式）───
btnStart.addEventListener('click', () => {
    if (isProcessing) return;
    if (currentInputMode === 'file') {
        if (!selectedVideoPath) return;
        startProcessing(selectedVideoPath);
    }
});

function startProcessing(videoPath) {
    isProcessing = true;
    btnStart.disabled = true;
    btnStart.innerHTML = '<span class="btn-icon">⏳</span> 处理中...';

    pipeline.classList.remove('hidden');
    progressDetail.classList.remove('hidden');
    resultPanel.classList.add('hidden');
    $$('.pipeline-step').forEach(step => step.classList.remove('active', 'done'));

    // 本地文件直接从步骤2（音频提取）开始，步骤1（下载）标为跳过
    const step1 = document.querySelector('.pipeline-step[data-step="1"]');
    if (step1) step1.classList.add('done'); // 无需下载，跳过

    progressDetail.textContent = '正在处理...';

    const language = $('#param-language').value;
    const model = $('#param-model').value;

    window.api.processVideo({
        video_path: videoPath,
        language,
        model,
    });
}

// ─── Python 消息处理 ───
window.api.onPythonMessage((msg) => {
    switch (msg.type) {
        case 'ready':
            statusDot.classList.add('connected');
            statusText.textContent = '后端就绪';
            break;

        case 'progress':
            // process_video 步骤1-5 → 映射到 UI 步骤2-6（步骤1是下载）
            updateProgress(msg.step + 1, 6, msg.label, msg.detail);
            break;

        case 'result':
            showResult(msg);
            break;

        case 'error':
            handleError(msg.message);
            break;

        case 'video_info':
            showVideoInfo(msg);
            break;

        case 'download_progress':
            updateDownloadProgress(msg);
            break;

        case 'download_done':
            onDownloadDone(msg);
            break;

        case 'config':
            fillConfig(msg);
            break;

        case 'config_saved':
            showToast('✅ 设置已保存', 'success');
            break;

        case 'deps_result':
            showDepsResult(msg);
            break;

        case 'history':
            renderHistory(msg.records);
            break;
    }
});

// ─── 视频信息预览 ───
function showVideoInfo(info) {
    $('#btn-fetch-info').textContent = '🔍 解析';
    $('#btn-fetch-info').disabled = false;

    const card = $('#video-preview-card');
    card.classList.remove('hidden');

    const dur = info.duration ? `${Math.floor(info.duration / 60)}:${String(info.duration % 60).padStart(2, '0')}` : '';
    const uploader = info.uploader ? `@${info.uploader}` : '';

    $('#vpc-title').textContent = info.title || '视频';
    $('#vpc-meta').textContent = [dur, uploader].filter(Boolean).join(' · ');
}

// ─── 下载进度更新 ───
function updateDownloadProgress(msg) {
    const bar = $('#download-bar-fill');
    const info = $('#download-bar-info');

    bar.style.width = `${msg.percent}%`;
    info.textContent = msg.detail || '下载中...';

    // 同步更新流水线步骤1
    updateProgress(1, 6, '视频下载', msg.detail);
}

// ─── 下载完成，自动触发处理 ───
function onDownloadDone(msg) {
    isDownloading = false;
    showToast('✅ 视频下载完成，开始处理...', 'success');

    // 隐藏下载进度条
    $('#download-bar-wrap').classList.add('hidden');

    // 标记步骤1完成
    const step1 = document.querySelector('.pipeline-step[data-step="1"]');
    if (step1) { step1.classList.add('done'); step1.classList.remove('active'); }
    progressDetail.textContent = '下载完成，开始处理...';

    // 自动传入下载好的视频路径继续处理
    const language = $('#param-language').value;
    const model = $('#param-model').value;

    window.api.processVideo({
        video_path: msg.video_path,
        language,
        model,
    });
}

function updateProgress(step, total, label, detail) {
    $$('.pipeline-step').forEach(el => {
        const s = parseInt(el.dataset.step);
        if (s < step) {
            el.classList.add('done');
            el.classList.remove('active');
        } else if (s === step) {
            el.classList.add('active');
            el.classList.remove('done');
        } else {
            el.classList.remove('active', 'done');
        }
    });
    progressDetail.textContent = detail || label;
}

function showResult(msg) {
    isProcessing = false;
    btnStart.disabled = !selectedVideoPath;
    btnStart.innerHTML = '<span class="btn-icon">▶</span> 开始处理';

    $$('.pipeline-step').forEach(step => {
        step.classList.add('done');
        step.classList.remove('active');
    });

    progressDetail.textContent = `✅ 处理完成，耗时 ${msg.elapsed} 秒`;
    currentResult = msg;

    resultPanel.classList.remove('hidden');
    resultMeta.textContent = `耗时 ${msg.elapsed}s | 输出: ${msg.md_path}`;
    resultContent.innerHTML = renderMarkdown(msg.summary);

    if (msg.keyframes && msg.keyframes.length > 0) {
        keyframesGrid.classList.remove('hidden');
        keyframesGrid.innerHTML = msg.keyframes.map(kf => {
            const imgSrc = kf.image_path ? `file://${kf.image_path}` : '';
            return `
        <div class="keyframe-card">
          ${imgSrc ? `<img src="${imgSrc}" alt="${kf.title}">` : ''}
          <div class="keyframe-info">
            <div class="keyframe-time">⏱️ ${kf.time}</div>
            <div class="keyframe-title">${kf.title}</div>
          </div>
        </div>
      `;
        }).join('');
    } else {
        keyframesGrid.classList.add('hidden');
    }

    showToast('🎉 视频处理完成！', 'success');
}

function handleError(message) {
    isProcessing = false;
    isDownloading = false;
    btnStart.disabled = !selectedVideoPath;
    btnStart.innerHTML = '<span class="btn-icon">▶</span> 开始处理';

    // 恢复 URL 页解析按钮
    $('#btn-fetch-info').textContent = '🔍 解析';
    $('#btn-fetch-info').disabled = false;

    progressDetail.textContent = `❌ ${message}`;
    showToast(`❌ ${message}`, 'error');
}

// ─── 结果操作按钮 ───
$('#btn-copy-md').addEventListener('click', () => {
    if (currentResult && currentResult.md_content) {
        window.api.copyToClipboard(currentResult.md_content);
        showToast('📋 Markdown 已复制到剪贴板', 'success');
    }
});

$('#btn-open-folder').addEventListener('click', () => {
    if (currentResult && currentResult.output_dir) {
        window.api.openFolder(currentResult.output_dir);
    }
});

$('#btn-open-file').addEventListener('click', () => {
    if (currentResult && currentResult.md_path) {
        window.api.openFile(currentResult.md_path);
    }
});

// ─── 设置 ───
function loadConfig() { window.api.loadConfig(); }

function fillConfig(cfg) {
    const keyVal = cfg.SILICONFLOW_API_KEY || '';
    $('#setting-api-key').value = keyVal === 'your_api_key_here' ? '' : keyVal;
    $('#setting-model').value = cfg.SILICONFLOW_MODEL || '';
    $('#setting-ffmpeg').value = cfg.FFMPEG_PATH || '';
    $('#setting-whisper').value = cfg.WHISPER_CPP_PATH || '';
    $('#setting-whisper-model').value = cfg.WHISPER_MODEL_PATH || '';
    $('#setting-output-dir').value = cfg.OUTPUT_DIR || '';
}

$('#btn-save-settings').addEventListener('click', () => {
    const config = {
        SILICONFLOW_API_KEY: $('#setting-api-key').value || 'your_api_key_here',
        SILICONFLOW_MODEL: $('#setting-model').value,
        FFMPEG_PATH: $('#setting-ffmpeg').value,
        WHISPER_CPP_PATH: $('#setting-whisper').value,
        WHISPER_MODEL_PATH: $('#setting-whisper-model').value,
        OUTPUT_DIR: $('#setting-output-dir').value,
    };
    window.api.saveConfig(config);
});

$('#btn-check-deps').addEventListener('click', () => {
    window.api.checkDeps();
    $('#deps-result').classList.remove('hidden');
    $('#deps-result').className = 'deps-result';
    $('#deps-result').textContent = '🔍 检查中...';
});

function showDepsResult(msg) {
    const el = $('#deps-result');
    el.classList.remove('hidden');
    if (msg.ok) {
        el.className = 'deps-result ok';
        el.textContent = '✅ 所有依赖均已就绪！';
    } else {
        el.className = 'deps-result error';
        el.innerHTML = msg.errors.map(e => `<p>${e}</p>`).join('');
    }
}

$('#btn-toggle-pw').addEventListener('click', () => {
    const input = $('#setting-api-key');
    input.type = input.type === 'password' ? 'text' : 'password';
});

$('#link-siliconflow').addEventListener('click', (e) => {
    e.preventDefault();
    window.api.openFile('https://siliconflow.cn/');
});

// ─── 历史记录 ───
function loadHistory() { window.api.listHistory({}); }

function renderHistory(records) {
    const list = $('#history-list');
    if (!records || records.length === 0) {
        list.innerHTML = '<p class="empty-state">📭 暂无历史记录<br><small>处理完视频后，会自动出现在这里</small></p>';
        return;
    }

    list.innerHTML = records.map(r => {
        const date = new Date(r.modified * 1000).toLocaleString('zh-CN');
        return `
      <div class="history-item">
        <div class="history-icon">📹</div>
        <div class="history-info">
          <div class="history-title">${r.title}</div>
          <div class="history-meta">${date} · ${r.size_kb}KB · ${r.screenshot_count} 张截图</div>
        </div>
        <div class="history-actions">
          <button class="btn btn-sm history-open-file" data-path="${r.path}">📄 打开</button>
          <button class="btn btn-sm history-open-dir" data-dir="${r.path.replace(/\/[^/]+$/, '')}">📂 目录</button>
        </div>
      </div>
    `;
    }).join('');

    list.querySelectorAll('.history-open-file').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); window.api.openFile(btn.dataset.path); });
    });
    list.querySelectorAll('.history-open-dir').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); window.api.openFolder(btn.dataset.dir); });
    });
}

// ─── Markdown 渲染 ───
function renderMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
}

// ─── Toast ───
function showToast(message, type = 'info') {
    const container = $('#toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        toast.style.transition = '0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ─── 初始化 ───
window.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => window.api.loadConfig(), 1500);
});
