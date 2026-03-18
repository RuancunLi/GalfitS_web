let currentImageData = null;
let isDragging = false;
let imageShape = null; // [ny, nx]

function toggleInputMode() {
    const mode = document.querySelector('input[name="inputMode"]:checked').value;
    const fileMode = document.getElementById('fileMode');
    const pathMode = document.getElementById('pathMode');

    if (mode === 'upload') {
        fileMode.style.display = 'block';
        pathMode.style.display = 'none';
    } else {
        fileMode.style.display = 'none';
        pathMode.style.display = 'block';
    }
}

function showStatus(message, type = 'success') {
    const statusDiv = document.getElementById('statusMsg');
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
    statusDiv.style.display = 'block';

    if (type === 'success') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 3000);
    }
}

function showLoading(show) {
    document.getElementById('loadingDiv').style.display = show ? 'block' : 'none';
    document.getElementById('loadBtn').disabled = show;
}

function handleFileSelect() {
    const fileInput = document.getElementById('imageFile');
    if (fileInput.files.length > 0) {
        showStatus(`Selected: ${fileInput.files[0].name}`, 'success');
    }
}

function screenToImagePixels(clientX, clientY) {
    if (!imageShape) return { px: 0, py: 0 };

    const imageDisplay = document.getElementById('imageDisplay');
    const rect = imageDisplay.getBoundingClientRect();

    const relativeX = (clientX - rect.left) / rect.width;
    const relativeY = (clientY - rect.top) / rect.height;

    let px = Math.round(relativeX * (imageShape[1] - 1));
    let py = Math.round((1 - relativeY) * (imageShape[0] - 1));

    px = Math.max(0, Math.min(imageShape[1] - 1, px));
    py = Math.max(0, Math.min(imageShape[0] - 1, py));

    return { px, py };
}

function updateCrosshairPosition(px, py) {
    const crosshair = document.getElementById('crosshair');
    const draggableArea = document.getElementById('draggableArea');
    const imageDisplay = document.getElementById('imageDisplay');

    if (!imageShape || !imageDisplay) return;

    const rect = imageDisplay.getBoundingClientRect();
    const relativeX = px / (imageShape[1] - 1);
    const relativeY = 1 - (py / (imageShape[0] - 1));
    const displayX = relativeX * rect.width;
    const displayY = relativeY * rect.height;

    crosshair.style.left = `${displayX - 10}px`;
    crosshair.style.top = `${displayY - 10}px`;
    draggableArea.style.left = `${displayX - 10}px`;
    draggableArea.style.top = `${displayY - 10}px`;
}

function setupDragging() {
    const draggableArea = document.getElementById('draggableArea');

    draggableArea.onmousedown = function onMouseDown(e) {
        isDragging = true;
        e.preventDefault();
    };

    document.onmousemove = function onMouseMove(e) {
        if (isDragging && currentImageData && imageShape) {
            const coords = screenToImagePixels(e.clientX, e.clientY);
            updateCrosshairPosition(coords.px, coords.py);
            updateCoordinates(coords.px, coords.py);
        }
    };

    document.onmouseup = function onMouseUp() {
        isDragging = false;
    };
}

function setupImageClick() {
    const imageDisplay = document.getElementById('imageDisplay');

    imageDisplay.onclick = function onImageClick(e) {
        if (!currentImageData || !imageShape) return;

        const coords = screenToImagePixels(e.clientX, e.clientY);
        updateCrosshairPosition(coords.px, coords.py);
        updateCoordinates(coords.px, coords.py);
    };
}

async function updateCoordinates(px, py) {
    if (!currentImageData) return;

    try {
        const response = await fetch('/get_coordinates', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_id: currentImageData.image_id,
                pixel_x: px,
                pixel_y: py,
            }),
        });

        if (response.ok) {
            const result = await response.json();

            document.getElementById('mousePixelX').textContent = px.toFixed(0);
            document.getElementById('mousePixelY').textContent = py.toFixed(0);
            document.getElementById('mouseDeltaRA').textContent = result.mouse_delta_ra.toFixed(3);
            document.getElementById('mouseDeltaDec').textContent = result.mouse_delta_dec.toFixed(3);

            document.getElementById('peakPixelX').textContent = result.peak_pixel_x.toFixed(0);
            document.getElementById('peakPixelY').textContent = result.peak_pixel_y.toFixed(0);
            document.getElementById('peakDeltaRA').textContent = result.peak_delta_ra.toFixed(3);
            document.getElementById('peakDeltaDec').textContent = result.peak_delta_dec.toFixed(3);
        } else {
            const error = await response.json();
            showStatus(`Error: ${error.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Network error: ${error.message}`, 'error');
    }
}

async function loadImage() {
    const mode = document.querySelector('input[name="inputMode"]:checked').value;
    const ra = document.getElementById('ra').value;
    const dec = document.getElementById('dec').value;
    const layer = document.getElementById('layer').value;
    const cutRadius = document.getElementById('cutRadius').value;

    if (!ra || !dec) {
        showStatus('Please enter RA/DEC coordinates', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('ra', ra);
    formData.append('dec', dec);
    formData.append('layer', layer);
    formData.append('cut_radius', cutRadius);

    if (mode === 'upload') {
        const fileInput = document.getElementById('imageFile');
        if (!fileInput.files[0]) {
            showStatus('Please select a file', 'error');
            return;
        }
        formData.append('file', fileInput.files[0]);
    } else {
        const imagePath = document.getElementById('imagePath').value;
        if (!imagePath) {
            showStatus('Please enter a file path', 'error');
            return;
        }
        formData.append('file_path', imagePath);
    }

    showLoading(true);

    try {
        const response = await fetch('/load_image', {
            method: 'POST',
            body: formData,
        });

        if (response.ok) {
            const result = await response.json();
            currentImageData = result;
            imageShape = result.image_shape;

            const imageDisplay = document.getElementById('imageDisplay');
            imageDisplay.src = `/get_image/${result.image_id}`;

            imageDisplay.onload = function onImageLoaded() {
                const centerX = Math.floor(imageShape[1] / 2);
                const centerY = Math.floor(imageShape[0] / 2);

                updateCrosshairPosition(centerX, centerY);
                updateCoordinates(centerX, centerY);

                setupDragging();
                setupImageClick();
            };

            document.getElementById('imageContainer').style.display = 'block';
            document.getElementById('infoPanel').style.display = 'grid';
            document.getElementById('clearBtn').disabled = false;

            showStatus('Image loaded successfully!', 'success');
        } else {
            const error = await response.json();
            showStatus(`Error: ${error.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Network error: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

function clearResults() {
    document.getElementById('imageContainer').style.display = 'none';
    document.getElementById('infoPanel').style.display = 'none';
    document.getElementById('clearBtn').disabled = true;
    currentImageData = null;
    imageShape = null;

    document.getElementById('mousePixelX').textContent = '-';
    document.getElementById('mousePixelY').textContent = '-';
    document.getElementById('mouseDeltaRA').textContent = '-';
    document.getElementById('mouseDeltaDec').textContent = '-';
    document.getElementById('peakPixelX').textContent = '-';
    document.getElementById('peakPixelY').textContent = '-';
    document.getElementById('peakDeltaRA').textContent = '-';
    document.getElementById('peakDeltaDec').textContent = '-';

    showStatus('Results cleared', 'success');
}

window.addEventListener('resize', () => {
    if (currentImageData && imageShape) {
        const px = parseInt(document.getElementById('mousePixelX').textContent, 10) || Math.floor(imageShape[1] / 2);
        const py = parseInt(document.getElementById('mousePixelY').textContent, 10) || Math.floor(imageShape[0] / 2);
        updateCrosshairPosition(px, py);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[name="inputMode"]').forEach((el) => {
        el.addEventListener('change', toggleInputMode);
    });
    document.getElementById('imageFile').addEventListener('change', handleFileSelect);
    document.getElementById('loadBtn').addEventListener('click', loadImage);
    document.getElementById('clearBtn').addEventListener('click', clearResults);
    toggleInputMode();
});
