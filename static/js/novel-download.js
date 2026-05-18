// ???????????????

async function openNovelFile(novelId) {
    openReader(novelId);
}

function stripContentDispositionQuotes(value) {
    const trimmed = (value || '').trim();
    if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
        return trimmed.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, '\\');
    }
    return trimmed;
}

function decodeRfc5987FilenameValue(value) {
    const unquotedValue = stripContentDispositionQuotes(value);
    const encodedMatch = /^([^']*)'[^']*'(.*)$/.exec(unquotedValue);
    const encodedFilename = encodedMatch ? encodedMatch[2] : unquotedValue;

    try {
        return decodeURIComponent(encodedFilename);
    } catch (err) {
        console.warn('解析下载文件名失败:', err);
        return '';
    }
}

function parseDownloadFilename(contentDisposition, fallbackFilename) {
    const fallback = fallbackFilename || 'novel.txt';
    if (!contentDisposition) return fallback;

    const encodedFilenameMatch = /(?:^|;)\s*filename\*\s*=\s*([^;]+)/i.exec(contentDisposition);
    if (encodedFilenameMatch) {
        const decodedFilename = decodeRfc5987FilenameValue(encodedFilenameMatch[1]);
        if (decodedFilename) return decodedFilename;
    }

    const filenameMatch = /(?:^|;)\s*filename\s*=\s*("[^"]*"|[^;]+)/i.exec(contentDisposition);
    if (filenameMatch) {
        const filename = stripContentDispositionQuotes(filenameMatch[1]);
        if (filename) return filename;
    }

    return fallback;
}

async function downloadNovel(novelId) {
    const novel = state.novels.find(n => n.id === novelId);
    if (!novel) {
        showToast('小说不存在', 'error');
        return;
    }

    if (!novel.file_path) {
        showToast('该小说未设置文件路径', 'error');
        return;
    }

    try {
        // 显示下载中提示
        showToast('正在准备下载...', 'success');

        // 调用后端下载API
        const response = await fetch(`/api/novels/${novelId}/download`);

        if (!response.ok) {
            const res = await response.json();
            showToast(res.message || '下载失败', 'error');
            return;
        }

        // 获取文件名
        const contentDisposition = response.headers.get('Content-Disposition');
        const filename = parseDownloadFilename(contentDisposition, novel.title + '.txt');

        // 创建下载链接
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('下载已开始', 'success');
    } catch (err) {
        console.error('下载失败:', err);
        showToast('下载失败: ' + err.message, 'error');
    }
}

// 添加小说
