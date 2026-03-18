document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const lyricPathInput = document.getElementById('lyric-path');
    const modelImagesGrid = document.getElementById('model-images-grid');
    const sedToggleBtn = document.getElementById('sed-toggle-btn');
    const parameterForm = document.getElementById('parameters-form');
    const submitButton = document.getElementById('recalculate-button');
    const workspaceShell = document.getElementById('workspace-shell');

    let currentSessionId = null;
    let previewMode = 'fit';
    let hasSedImage = false;

    if (!uploadForm || !lyricPathInput || !modelImagesGrid || !parameterForm || !submitButton) {
        return;
    }

    uploadForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const lyricPath = lyricPathInput.value.trim();
        if (!lyricPath) {
            alert('Please input absolute .lyric path.');
            return;
        }

        fetch('/model_editor/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ lyric_path: lyricPath })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentSessionId = data.session_id;
                    hasSedImage = Boolean(data.has_sed_image);
                    previewMode = 'fit';
                    updateSedButton();
                    renderPreviewImage(data.preview_url || '');
                    populateParametersTree(data.parameters_tree || []);
                    applyLayoutMode(data.nimage);
                } else {
                    alert('Error loading lyric: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });

    submitButton.addEventListener('click', function(event) {
        event.preventDefault();
        if (!currentSessionId) {
            alert('Please load a lyric first.');
            return;
        }

        const updates = getUpdatedParameters();
        fetch('/model_editor/update_parameters', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                updates: updates
            })
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    hasSedImage = Boolean(data.has_sed_image);
                    updateSedButton();
                    renderPreviewImage(data.preview_url || '');
                    populateParametersTree(data.parameters_tree || []);
                    applyLayoutMode(data.nimage);
                } else {
                    alert('Error updating parameters: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    });

    if (sedToggleBtn) {
        sedToggleBtn.addEventListener('click', function() {
            if (!hasSedImage || !currentSessionId) return;
            previewMode = previewMode === 'fit' ? 'sed' : 'fit';
            updateSedButton();
            renderPreviewImage(`/model_editor/preview_image/${currentSessionId}`);
        });
    }

    function updateSedButton() {
        if (!sedToggleBtn) return;
        if (!currentSessionId || !hasSedImage) {
            sedToggleBtn.style.display = 'none';
            return;
        }
        sedToggleBtn.style.display = 'inline-block';
        sedToggleBtn.textContent = previewMode === 'fit' ? 'SED' : 'FIT';
    }

    function renderPreviewImage(previewUrl) {
        modelImagesGrid.innerHTML = '';
        if (!previewUrl || !currentSessionId) {
            const empty = document.createElement('p');
            empty.textContent = 'No preview image returned.';
            modelImagesGrid.appendChild(empty);
            return;
        }

        const card = document.createElement('div');
        card.className = 'model-image-card';

        const title = document.createElement('div');
        title.className = 'model-image-title';
        title.textContent = 'Current Fit Overview';

        const img = document.createElement('img');
        img.src = `${previewUrl}?kind=${previewMode}&t=${Date.now()}`;
        img.alt = 'Fit display image';

        card.appendChild(title);
        card.appendChild(img);
        modelImagesGrid.appendChild(card);
    }

    function populateParametersTree(parametersTree) {
        parameterForm.innerHTML = '';

        if (!Array.isArray(parametersTree) || parametersTree.length === 0) {
            const empty = document.createElement('p');
            empty.textContent = 'No editable parameters found.';
            parameterForm.appendChild(empty);
            return;
        }

        parametersTree.forEach((modelNode) => {
            const section = document.createElement('fieldset');
            section.className = 'parameter-component';

            const legend = document.createElement('legend');
            legend.textContent = `${modelNode.model_name} (${modelNode.model_type})`;
            section.appendChild(legend);

            const ownGrid = document.createElement('div');
            ownGrid.className = 'params-grid';
            (modelNode.parameters || []).forEach((param) => {
                ownGrid.appendChild(buildParamRow(param));
            });
            if (ownGrid.childElementCount > 0) {
                section.appendChild(ownGrid);
            }

            (modelNode.subcomponents || []).forEach((subNode) => {
                const subTitle = document.createElement('h4');
                subTitle.className = 'subcomponent-title';
                subTitle.textContent = subNode.name;
                section.appendChild(subTitle);

                const subGrid = document.createElement('div');
                subGrid.className = 'params-grid';
                (subNode.parameters || []).forEach((param) => {
                    subGrid.appendChild(buildParamRow(param));
                });
                if (subGrid.childElementCount > 0) {
                    section.appendChild(subGrid);
                }
            });

            parameterForm.appendChild(section);
        });
    }

    function buildParamRow(param) {
        const row = document.createElement('div');
        row.className = 'parameter-row';

        const label = document.createElement('label');
        label.textContent = param.name;
        label.setAttribute('for', param.full_key);

        const input = document.createElement('input');
        input.type = 'text';
        input.id = param.full_key;
        input.name = param.full_key;
        input.value = param.value;

        row.appendChild(label);
        row.appendChild(input);
        return row;
    }

    function applyLayoutMode(nimage) {
        if (!workspaceShell) return;
        const n = Number(nimage || 0);
        workspaceShell.classList.remove('split-mode', 'stack-mode');
        if (n > 16) {
            workspaceShell.classList.add('stack-mode');
            workspaceShell.style.setProperty('--param-cols', '7');
        } else {
            workspaceShell.classList.add('split-mode');
            workspaceShell.style.setProperty('--param-cols', '3');
        }
    }

    function getUpdatedParameters() {
        const inputs = parameterForm.getElementsByTagName('input');
        const updatedParameters = {};
        for (let i = 0; i < inputs.length; i += 1) {
            const input = inputs[i];
            updatedParameters[input.name] = input.value;
        }
        return updatedParameters;
    }
});
