let autoRefreshEnabled = false;
let refreshInterval = null;
const REFRESH_INTERVAL_MS = 1000;
let selectedFileHandle = null;

async function selectDirectory() {
    try {
        if (!window.showOpenFilePicker) {
            alert('Directory selection is not supported in this browser. Please use Chrome or Edge.');
            return;
        }
        const fileHandles = await window.showOpenFilePicker({
            types: [
                {
                    description: 'JSON Files',
                    accept: {
                        'application/json': ['.json']
                    }
                }
            ],
            multiple: false
        });
        const fileHandle = fileHandles[0];
        selectedFileHandle = fileHandle;

        document.getElementById('directory-btn').innerHTML = `<i class="fas fa-folder-open"></i> ${selectedFileHandle.name}`;
        await loadAllData();
    } catch (error) {
        if (error.name !== 'AbortError') {
            console.error('Directory selection error:', error);
            alert('Error selecting directory: ' + error.message);
        }
    }
}

function setupCollapsibleSection() {
    const header = document.querySelector('.section-header');
    header.addEventListener('click', () => {
        document.getElementById('execution-data').parentElement.classList.toggle('collapsed');
    });
}

function setupAutoRefresh() {
    const refreshBtn = document.getElementById('refresh-btn');
    refreshBtn.addEventListener('click', () => {
        autoRefreshEnabled = !autoRefreshEnabled;
        if (autoRefreshEnabled) {
            refreshBtn.classList.add('active');
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Show From Server: On';
            refreshInterval = setInterval(loadAllDataFromServer, REFRESH_INTERVAL_MS);
        } else {
            refreshBtn.classList.remove('active');
            refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Show From Server: Off';
            clearInterval(refreshInterval);
        }
    });
}

function formatInputs(inputs) {
    if (!inputs || !inputs.pipeline_data) return 'None';
    const items = inputs.pipeline_data.split(';').filter(Boolean);
    if (items.length === 0) return 'None';
    return `<ul class="inputs-list">${
        items.map(item => `<li>${item.trim()}</li>`).join('')
    }</ul>`;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
}

function displayExecutionData(uiViewData) {
    const executionData = uiViewData.execution;
    const container = document.getElementById('execution-data');
    container.classList.remove('loading');
    container.innerHTML = `
        <div class="execution-info">
            <div class="info-row">
                <div class="info-label">Pipeline ID:</div>
                <div class="info-value">${executionData.id || 'N/A'}</div>
                <div class="info-label">Pipeline Name:</div>
                <div class="info-value">${executionData.name || 'N/A'}</div>

            </div>
            <div class="info-row">
                <div class="info-label">Status:</div>
                <div class="info-value">
                    <span class="status status-${executionData.status}">${executionData.status}</span>
                </div>

                <div class="info-label">Dry Run:</div>
                <div class="info-value">${executionData.is_dry_run ? 'Yes' : 'No'}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Start Time:</div>
                <div class="info-value">${formatDate(executionData.start_time)}</div>

                <div class="info-label">Finish Time:</div>
                <div class="info-value">${formatDate(executionData.finish_time)}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Duration:</div>
                <div class="info-value">${executionData.duration || 'N/A'}</div>

                <div class="info-label">Execution Dir:</div>
                <div class="info-value">${executionData.exec_dir || 'N/A'}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Inputs:</div>
                <div class="info-value">${formatInputs(executionData.inputs)}</div>
            </div>
        </div>
    `;
}

function calculateDuration(startTime, endTime) {
    if (!startTime || !endTime) return 'N/A';
    const start = new Date(startTime);
    const end = new Date(endTime);
    const seconds = Math.round((end - start) / 1000);

    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
}

async function renderPipelineVisualization(uiViewData) {
    const container = document.getElementById('pipeline-visualization');
    container.innerHTML = `<div class="pipeline-container" id="pipeline-graph"></div>`;
    container.classList.remove('loading');
    const pipelineData = uiViewData;
    if (!pipelineData.stages || pipelineData.stages.length === 0) {
        container.innerHTML += '<p>No stages found in pipeline</p>';
        return;
    }
    const graphContainer = document.getElementById('pipeline-graph');
    const stageContainer = document.createElement('div');
    stageContainer.className = 'stage-container';
    graphContainer.appendChild(stageContainer);

    for (const stage of pipelineData.stages) {
        const row = await createStageElement(stage);
        stageContainer.appendChild(row);
    }
    container.appendChild(graphContainer);
}

async function createStageElement(stage) {
    const row = document.createElement('div');
    row.className = 'stage-row';

    if (stage.parallelStages && stage.parallelStages.length > 0) {
        const parallelGroup = document.createElement('div');
        parallelGroup.className = 'parallel-group';

        const parallelBlocks = await Promise.all(
            stage.parallelStages.map(parallelStage =>
                createStageElement(parallelStage).catch(e => {
                    console.error('Error creating parallel stage:', e);
                    return null;
                })
            )
        );

        parallelBlocks.filter(Boolean).forEach(parallelBlock => {
            parallelGroup.appendChild(parallelBlock);
        });
        row.appendChild(parallelGroup);
    } else {
        const stageBlock = await createStageBlock(stage);
        row.appendChild(stageBlock);
    }

    return row;
}

async function createStageBlock(stage) {
    let block = document.createElement('div');
    block.className = `stage-block stage-${stage.status}`;

    const name = document.createElement('div');
    name.className = 'stage-name';
    name.textContent = stage.name;
    block.appendChild(name);

    if (stage.start_time) {
        const duration = document.createElement('div');
        duration.className = 'stage-duration';
        duration.textContent = calculateDuration(stage.start_time, stage.finish_time);
        block.appendChild(duration);
    }

    if (stage.type === 'ATLAS_PIPELINE_TRIGGER' && stage.nestedPipeline) {
        const nestedData = stage.nestedPipeline;
        if (nestedData && nestedData.stages) {
            block.classList.add('has-nested');

            const nestedContainer = document.createElement('div');
            nestedContainer.className = 'nested-pipeline';

            const nestedStages = await Promise.all(
                nestedData.stages.map(nestedStage =>
                    createStageElement(nestedStage)
                )
            );

            nestedStages.forEach(nestedStage => {
                nestedContainer.appendChild(nestedStage);
            });

            const wrapper = document.createElement('div');
            wrapper.className = 'nested-stage-wrapper';
            wrapper.appendChild(block);
            wrapper.appendChild(nestedContainer);
            return wrapper;
        }
    }
    return block;
}

async function loadAllData() {
    if (!selectedFileHandle) return;
    try {
        const uiViewFile = await selectedFileHandle.getFile();
        const uiViewData = JSON.parse(await uiViewFile.text());
        displayExecutionData(uiViewData);
        await renderPipelineVisualization(uiViewData);
    } catch (error) {
        console.error('Loading error:', error);
        alert('Error loading pipeline data: ' + error.message);
        if (autoRefreshEnabled) {
            document.getElementById('refresh-btn').click();
        }
    }
}

async function loadAllDataFromServer() {
    try {
        const response = await fetch('/get_report');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const uiViewData = await response.json();
        displayExecutionData(uiViewData);
        await renderPipelineVisualization(uiViewData);
    } catch (error) {
        console.error('Loading error:', error);
        alert('Error loading pipeline data: ' + error.message);
        if (autoRefreshEnabled) {
            document.getElementById('refresh-btn').click();
        }
    }
}

function setupControls() {
    setupAutoRefresh();
    const directoryBtn = document.getElementById('directory-btn');
    directoryBtn.addEventListener('click', selectDirectory);
}

window.addEventListener('DOMContentLoaded', () => {
    setupCollapsibleSection();
    setupControls();
});