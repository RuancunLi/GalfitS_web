const state = {
    catalogPath: '',
    workspacePath: '',
    runName: '',
    targets: [],
    selectedTarget: null,
    zoom: 1,
    panX: 0,
    panY: 0,
    isPanning: false,
    panStartX: 0,
    panStartY: 0,
    previewMode: 'fit',
};

const ZOOM_MIN = 1;
const ZOOM_MAX = 6;
const ZOOM_STEP = 0.2;

function showStatus(message, isError = false) {
    const box = document.getElementById('statusBox');
    box.textContent = message;
    box.className = `status-box ${isError ? 'err' : 'ok'}`;
    box.style.display = 'block';

    if (!isError) {
        setTimeout(() => {
            box.style.display = 'none';
        }, 3000);
    }
}

function getInputs() {
    return {
        catalog_path: document.getElementById('catalogPath').value.trim(),
        workspace_path: document.getElementById('workspacePath').value.trim(),
        run_name: document.getElementById('runName').value.trim(),
    };
}

function requireInputs(payload) {
    if (!payload.catalog_path || !payload.workspace_path || !payload.run_name) {
        showStatus('Please fill catalog path, workspace path, and run.', true);
        return false;
    }
    return true;
}

function updateSummaryText(text) {
    document.getElementById('summaryText').textContent = text;
}

function applyImageTransform() {
    const img = document.getElementById('jobPreviewImage');
    if (!img) return;
    img.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
}

function resetZoomPan() {
    state.zoom = 1;
    state.panX = 0;
    state.panY = 0;
    applyImageTransform();
}

function updateModeButtons() {
    const sedBtn = document.getElementById('sedBtn');
    if (!sedBtn) return;
    const sedActive = state.previewMode === 'sed';
    sedBtn.classList.toggle('active', sedActive);
    sedBtn.textContent = sedActive ? 'FIT' : 'SED';
}

function changeZoom(delta) {
    state.zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, state.zoom + delta));
    if (state.zoom <= 1) {
        state.panX = 0;
        state.panY = 0;
    }
    applyImageTransform();
}

function setupZoomPanHandlers() {
    const stage = document.getElementById('imageStage');
    const img = document.getElementById('jobPreviewImage');
    if (!stage || !img) return;

    stage.addEventListener('wheel', (event) => {
        event.preventDefault();
        if (event.deltaY < 0) {
            changeZoom(ZOOM_STEP);
        } else {
            changeZoom(-ZOOM_STEP);
        }
    }, { passive: false });

    stage.addEventListener('mousedown', (event) => {
        if (state.zoom <= 1) return;
        state.isPanning = true;
        state.panStartX = event.clientX - state.panX;
        state.panStartY = event.clientY - state.panY;
        stage.classList.add('dragging');
    });

    window.addEventListener('mousemove', (event) => {
        if (!state.isPanning) return;
        state.panX = event.clientX - state.panStartX;
        state.panY = event.clientY - state.panStartY;
        applyImageTransform();
    });

    window.addEventListener('mouseup', () => {
        state.isPanning = false;
        stage.classList.remove('dragging');
    });

    img.addEventListener('dragstart', (event) => {
        event.preventDefault();
    });
}

function renderPreview(target) {
    const previewWrap = document.getElementById('previewWrap');
    if (!previewWrap || !target) return;

    const showSed = state.previewMode === 'sed';
    const path = showSed ? target.sed_model_path : target.image_fit_path;
    const exists = showSed ? target.has_sed_model : target.has_image;

    if (exists) {
        const encoded = encodeURIComponent(path);
        previewWrap.innerHTML = `
            <div id="imageStage" class="image-stage">
                <img id="jobPreviewImage" class="zoom-image" src="/job_monitor/image?path=${encoded}" alt="${target.name} preview image">
            </div>
        `;
        resetZoomPan();
        setupZoomPanHandlers();
    } else {
        const missingName = showSed ? 'SED_model.png' : 'image_fit.png';
        previewWrap.innerHTML = `<div class="hint">${missingName} not found for this target.</div>`;
    }
}

function renderTargetList() {
    const list = document.getElementById('targetList');
    list.innerHTML = '';

    if (state.targets.length === 0) {
        list.innerHTML = '<div style="padding: 10px; color: #667085;">No targets loaded.</div>';
        return;
    }

    state.targets.forEach((target) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'target-item';
        if (state.selectedTarget && state.selectedTarget.name === target.name) {
            btn.classList.add('active');
        }
        if (!target.has_lyric) {
            btn.classList.add('no-run');
        }

        const left = document.createElement('span');
        left.className = 'target-name';
        left.textContent = target.name;

        const right = document.createElement('span');
        right.className = 'status-group';

        const runStatus = document.createElement('span');
        if (!target.has_lyric) {
            runStatus.className = 'status-pill none';
            runStatus.textContent = 'none';
        } else {
            runStatus.className = `status-pill ${target.finished ? 'finished' : 'unfinished'}`;
            runStatus.textContent = target.finished ? 'finished' : 'unfinished';
        }

        const reviewStatus = document.createElement('span');
        if (!target.has_lyric) {
            reviewStatus.className = 'status-pill none';
            reviewStatus.textContent = 'n/a';
        } else {
            reviewStatus.className = `status-pill ${target.reviewed ? 'reviewed' : 'unreviewed'}`;
            reviewStatus.textContent = target.reviewed ? 'reviewed' : 'unreviewed';
        }

        right.appendChild(runStatus);
        right.appendChild(reviewStatus);

        btn.appendChild(left);
        btn.appendChild(right);
        btn.addEventListener('click', () => selectTarget(target.name));

        list.appendChild(btn);
    });
}

function findTargetByName(name) {
    return state.targets.find((row) => row.name === name) || null;
}

function selectTarget(name) {
    const target = findTargetByName(name);
    if (!target) return;

    state.selectedTarget = target;
    renderTargetList();

    const viewerTitle = document.getElementById('viewerTitle');
    const targetMeta = document.getElementById('targetMeta');
    const commentInput = document.getElementById('commentInput');
    const saveCommentBtn = document.getElementById('saveCommentBtn');

    viewerTitle.textContent = `Target Preview: ${target.name}`;
    targetMeta.innerHTML = [
        `Summary: ${target.summary_path}`,
        `Lyric: ${target.lyric_path}`,
        `Image: ${target.image_fit_path}`,
        `SED: ${target.sed_model_path}`,
    ].join('<br>');

    commentInput.value = target.comment || '';
    saveCommentBtn.disabled = false;

    renderPreview(target);
}

async function scanJobs() {
    const payload = getInputs();
    if (!requireInputs(payload)) return;

    document.getElementById('scanBtn').disabled = true;
    document.getElementById('exportBtn').disabled = true;
    document.getElementById('saveCommentBtn').disabled = true;

    try {
        const response = await fetch('/job_monitor/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Failed to scan jobs.');
        }

        state.catalogPath = result.catalog_path;
        state.workspacePath = result.workspace_path;
        state.runName = result.run_name;
        state.targets = result.targets || [];
        state.selectedTarget = null;
        state.previewMode = 'fit';
        updateModeButtons();

        renderTargetList();

        updateSummaryText(`Loaded ${result.total_targets} targets. Unfinished: ${result.unfinished_count}.`);
        document.getElementById('exportBtn').disabled = false;

        const previewWrap = document.getElementById('previewWrap');
        previewWrap.innerHTML = '<div class="hint">Click a target to display image_fit.png.</div>';
        document.getElementById('viewerTitle').textContent = 'Target Preview';
        document.getElementById('targetMeta').textContent = '';
        document.getElementById('commentInput').value = '';

        showStatus('Job scan completed.');
    } catch (error) {
        showStatus(error.message, true);
    } finally {
        document.getElementById('scanBtn').disabled = false;
    }
}

function toggleSedMode() {
    state.previewMode = state.previewMode === 'fit' ? 'sed' : 'fit';
    updateModeButtons();
    if (state.selectedTarget) {
        renderPreview(state.selectedTarget);
    }
}

async function exportUnfinished() {
    const payload = getInputs();
    if (!requireInputs(payload)) return;

    document.getElementById('exportBtn').disabled = true;

    try {
        const response = await fetch('/job_monitor/export_unfinished', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Failed to export unfinished targets.');
        }

        showStatus(`Unfinished targets exported to: ${result.output_path}`);
    } catch (error) {
        showStatus(error.message, true);
    } finally {
        document.getElementById('exportBtn').disabled = false;
    }
}

async function saveComment() {
    if (!state.selectedTarget) {
        showStatus('Please click a target first.', true);
        return;
    }

    const comment = document.getElementById('commentInput').value;
    const payload = {
        workspace_path: state.workspacePath,
        run_name: state.runName,
        target_name: state.selectedTarget.name,
        comment,
    };

    try {
        const response = await fetch('/job_monitor/save_comment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || 'Failed to save comment.');
        }

        const target = findTargetByName(state.selectedTarget.name);
        if (target) {
            target.comment = comment;
            target.reviewed = comment.trim().length > 0;
            state.selectedTarget = target;
        }

        renderTargetList();

        showStatus(`Comment saved to: ${result.comments_path}`);
    } catch (error) {
        showStatus(error.message, true);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('scanBtn').addEventListener('click', scanJobs);
    document.getElementById('exportBtn').addEventListener('click', exportUnfinished);
    document.getElementById('saveCommentBtn').addEventListener('click', saveComment);
    document.getElementById('zoomInBtn').addEventListener('click', () => changeZoom(ZOOM_STEP));
    document.getElementById('zoomOutBtn').addEventListener('click', () => changeZoom(-ZOOM_STEP));
    document.getElementById('zoomResetBtn').addEventListener('click', resetZoomPan);
    document.getElementById('sedBtn').addEventListener('click', toggleSedMode);
    updateModeButtons();
});
