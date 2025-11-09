/**
 * Model Manager UI
 * Manages RL model training, loading, and evaluation
 */

class ModelManager {
    constructor() {
        this.models = [];
        this.currentModel = null;
        this.activeJobs = {};

        this.init();
    }

    init() {
        console.log('[ModelManager] Initializing...');

        // Create UI
        this.createUI();

        // Setup event listeners
        this.setupEventListeners();

        // Listen to WebSocket for training progress
        this.setupWebSocketListeners();

        // Load models
        this.loadModels();

        console.log('[ModelManager] Ready');
    }

    createUI() {
        // Create Model Manager Panel
        const panel = document.createElement('div');
        panel.id = 'modelManagerPanel';
        panel.className = 'model-manager-panel';
        panel.innerHTML = `
            <div class="model-manager-header">
                <h3>ML Model Manager</h3>
                <button class="close-btn" id="modelManagerClose">×</button>
            </div>

            <div class="model-manager-content">
                <!-- Model Selection -->
                <div class="model-section">
                    <label>Current Model:</label>
                    <select id="modelSelect" class="model-select">
                        <option value="">Loading...</option>
                    </select>
                    <button id="loadModelBtn" class="btn-small">Load</button>
                    <button id="deleteModelBtn" class="btn-danger-small" style="margin-left: 4px;">Delete</button>
                </div>

                <!-- Model Info -->
                <div id="modelInfo" class="model-info" style="display: none;">
                    <div class="info-row">
                        <span class="label">Created:</span>
                        <span id="modelCreated">-</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Steps:</span>
                        <span id="modelSteps">-</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Train:</span>
                        <span id="modelTrainReturn" class="metric">-</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Test:</span>
                        <span id="modelTestReturn" class="metric">-</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Overfitting:</span>
                        <span id="modelOverfitting" class="metric">-</span>
                    </div>
                </div>

                <!-- Actions -->
                <div class="model-actions">
                    <button id="trainNewBtn" class="btn-primary">Train New Model</button>
                </div>

                <!-- Training Progress -->
                <div id="trainingProgress" class="training-progress" style="display: none;">
                    <div class="progress-header">
                        <span id="trainingModelName">training...</span>
                        <button id="stopTrainingBtn" class="btn-danger-small">Stop</button>
                    </div>
                    <div class="progress-bar-container">
                        <div id="progressBar" class="progress-bar"></div>
                    </div>
                    <div id="progressText" class="progress-text">0 / 50000 steps (0%)</div>
                    <div id="progressMetrics" class="progress-metrics"></div>
                </div>
            </div>

            <!-- Training Dialog -->
            <div id="trainingDialog" class="modal" style="display: none;">
                <div class="modal-content">
                    <h3>Train New Model</h3>

                    <label>Model Name:</label>
                    <input type="text" id="newModelName" placeholder="strategy_v1" />

                    <label>Training Steps:</label>
                    <select id="trainingSteps">
                        <option value="1000">Quick Test - 1,000 (~2min)</option>
                        <option value="10000" selected>Minimum - 10,000 (~15min)</option>
                        <option value="50000">Recommended - 50,000 (~1h)</option>
                        <option value="100000">Production - 100,000 (~2h)</option>
                    </select>

                    <div class="modal-actions">
                        <button id="cancelTrainBtn" class="btn-secondary">Cancel</button>
                        <button id="startTrainBtn" class="btn-primary">Start Training</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(panel);
    }

    setupEventListeners() {
        // Close panel
        document.getElementById('modelManagerClose').addEventListener('click', () => {
            document.getElementById('modelManagerPanel').style.display = 'none';
        });

        // Model selection changed
        document.getElementById('modelSelect').addEventListener('change', () => {
            this.onModelSelected();
        });

        // Load model button
        document.getElementById('loadModelBtn').addEventListener('click', () => {
            this.loadSelectedModel();
        });

        // Delete model button
        document.getElementById('deleteModelBtn').addEventListener('click', () => {
            this.deleteSelectedModel();
        });

        // Train new model button
        document.getElementById('trainNewBtn').addEventListener('click', () => {
            this.showTrainingDialog();
        });

        // Training dialog buttons
        document.getElementById('cancelTrainBtn').addEventListener('click', () => {
            this.hideTrainingDialog();
        });

        document.getElementById('startTrainBtn').addEventListener('click', () => {
            this.startTraining();
        });

        // Stop training
        document.getElementById('stopTrainingBtn').addEventListener('click', () => {
            this.stopTraining();
        });
    }

    setupWebSocketListeners() {
        // Listen for training progress messages
        window.addEventListener('websocket-message', (event) => {
            const message = event.detail;

            // Check if it's a training progress message
            if (message.job_id) {
                this.onTrainingProgress(message);
            }
        });
    }

    async loadModels() {
        try {
            const response = await fetch('/api/ml/models');
            const data = await response.json();

            this.models = data.models || [];
            this.currentModel = data.current_model;

            this.updateModelSelect();

            console.log(`[ModelManager] Loaded ${this.models.length} models`);
        } catch (error) {
            console.error('[ModelManager] Failed to load models:', error);
        }
    }

    updateModelSelect() {
        const select = document.getElementById('modelSelect');

        if (this.models.length === 0) {
            select.innerHTML = '<option value="">No models available</option>';
            return;
        }

        select.innerHTML = this.models.map(model =>
            `<option value="${model.name}">${model.name}</option>`
        ).join('');

        // Select first model by default
        if (this.models.length > 0) {
            select.value = this.models[0].name;
            this.onModelSelected();
        }
    }

    onModelSelected() {
        const select = document.getElementById('modelSelect');
        const modelName = select.value;

        if (!modelName) {
            document.getElementById('modelInfo').style.display = 'none';
            return;
        }

        const model = this.models.find(m => m.name === modelName);
        if (!model) return;

        // Update model info display
        document.getElementById('modelCreated').textContent = new Date(model.created_at).toLocaleString();
        document.getElementById('modelSteps').textContent = model.total_steps.toLocaleString();

        const trainReturn = (model.train_return * 100).toFixed(2);
        const testReturn = model.test_return ? (model.test_return * 100).toFixed(2) : 'N/A';
        const overfitting = model.overfitting_score ? (model.overfitting_score * 100).toFixed(1) : 'N/A';

        document.getElementById('modelTrainReturn').textContent = `${trainReturn}%`;
        document.getElementById('modelTrainReturn').className = 'metric ' + (model.train_return > 0 ? 'positive' : 'negative');

        document.getElementById('modelTestReturn').textContent = `${testReturn}%`;
        if (model.test_return !== null) {
            document.getElementById('modelTestReturn').className = 'metric ' + (model.test_return > 0 ? 'positive' : 'negative');
        }

        document.getElementById('modelOverfitting').textContent = `${overfitting}%`;
        if (model.overfitting_score !== null) {
            const severity = model.overfitting_score < 0.2 ? 'positive' : model.overfitting_score < 0.5 ? 'warning' : 'negative';
            document.getElementById('modelOverfitting').className = 'metric ' + severity;
        }

        document.getElementById('modelInfo').style.display = 'block';
    }

    async loadSelectedModel() {
        const select = document.getElementById('modelSelect');
        const modelName = select.value;

        if (!modelName) {
            alert('Please select a model');
            return;
        }

        try {
            const response = await fetch('/api/ml/load_model', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({model_name: modelName})
            });

            const data = await response.json();

            if (data.success) {
                alert(`Model "${modelName}" loaded successfully!`);
                this.currentModel = modelName;
            } else {
                alert('Failed to load model');
            }
        } catch (error) {
            console.error('[ModelManager] Load model error:', error);
            alert('Error loading model');
        }
    }

    async deleteSelectedModel() {
        const select = document.getElementById('modelSelect');
        const modelName = select.value;

        if (!modelName) {
            alert('Please select a model');
            return;
        }

        // Confirm deletion
        if (!confirm(`Are you sure you want to delete model "${modelName}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch(`/api/ml/models/${modelName}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                alert(`Model "${modelName}" deleted successfully!`);

                // Reload models list
                await this.loadModels();

                // Hide model info
                document.getElementById('modelInfo').style.display = 'none';
            } else {
                alert('Failed to delete model');
            }
        } catch (error) {
            console.error('[ModelManager] Delete model error:', error);
            alert('Error deleting model');
        }
    }

    showTrainingDialog() {
        document.getElementById('trainingDialog').style.display = 'flex';
    }

    hideTrainingDialog() {
        document.getElementById('trainingDialog').style.display = 'none';
    }

    async startTraining() {
        const modelName = document.getElementById('newModelName').value.trim();
        const steps = parseInt(document.getElementById('trainingSteps').value);

        if (!modelName) {
            alert('Please enter a model name');
            return;
        }

        // Close dialog
        this.hideTrainingDialog();

        // Show progress panel
        document.getElementById('trainingProgress').style.display = 'block';
        document.getElementById('trainingModelName').textContent = modelName;
        document.getElementById('progressBar').style.width = '0%';
        document.getElementById('progressText').textContent = `0 / ${steps.toLocaleString()} steps (0%)`;

        try {
            const response = await fetch('/api/ml/train', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    model_name: modelName,
                    total_steps: steps,
                    train_ratio: 0.7
                })
            });

            const data = await response.json();

            if (data.status === 'started') {
                console.log(`[ModelManager] Training started: ${data.job_id}`);
                this.activeJobs[data.job_id] = {
                    model_name: modelName,
                    total_steps: steps
                };
            } else {
                alert('Failed to start training');
                document.getElementById('trainingProgress').style.display = 'none';
            }
        } catch (error) {
            console.error('[ModelManager] Training error:', error);
            alert('Error starting training');
            document.getElementById('trainingProgress').style.display = 'none';
        }
    }

    onTrainingProgress(message) {
        const job = this.activeJobs[message.job_id];
        if (!job) return;

        console.log('[ModelManager] Training progress:', message);

        const progressText = document.getElementById('progressText');
        const progressBar = document.getElementById('progressBar');
        const progressMetrics = document.getElementById('progressMetrics');

        // Handle different message types with phase indicators
        if (message.type === 'init') {
            progressText.textContent = `🔧 Initializing: ${message.model_name}`;
            progressBar.style.width = '0%';
        }

        else if (message.type === 'data_loading') {
            if (message.status === 'started') {
                progressText.textContent = '📊 Loading data...';
                progressBar.style.width = '5%';
            } else if (message.status === 'completed') {
                progressText.textContent = `📊 Data loaded: ${message.total_candles.toLocaleString()} candles`;
                progressBar.style.width = '10%';
            }
        }

        else if (message.type === 'data_split') {
            if (message.status === 'started') {
                progressText.textContent = '✂️ Splitting train/test data...';
                progressBar.style.width = '12%';
            } else if (message.status === 'completed') {
                progressText.textContent = `✂️ Split: ${message.train_candles.toLocaleString()} train / ${message.test_candles.toLocaleString()} test`;
                progressBar.style.width = '15%';
            }
        }

        else if (message.type === 'training') {
            if (message.status === 'started') {
                progressText.textContent = '🚀 Training started...';
                progressBar.style.width = '20%';
            } else if (message.status === 'completed') {
                progressText.textContent = '✅ Training completed!';
                progressBar.style.width = '60%';
            }
        }

        else if (message.type === 'training_progress') {
            const progress = message.progress || 0;
            const currentStep = message.current_step || 0;
            const totalSteps = job.total_steps;

            // Progress bar: 20% (start) to 60% (end) during training
            const trainingProgress = 20 + (progress * 40);
            progressBar.style.width = `${trainingProgress}%`;

            progressText.textContent =
                `🚀 Training: ${currentStep.toLocaleString()} / ${totalSteps.toLocaleString()} steps (${(progress * 100).toFixed(1)}%)`;

            // Update metrics
            if (message.balance) {
                progressMetrics.textContent = `Balance: ${message.balance.toFixed(0)}€ | Trades: ${message.total_trades || 0}`;
            }
        }

        else if (message.type === 'evaluation') {
            if (message.status === 'started') {
                const phase = message.data_split === 'train' ? 'Train' : 'Test';
                progressText.textContent = `📈 Evaluating ${phase} data (${message.candles.toLocaleString()} candles)...`;
                progressBar.style.width = message.data_split === 'train' ? '65%' : '75%';
            } else if (message.status === 'completed') {
                const phase = message.data_split === 'train' ? 'Train' : 'Test';
                progressText.textContent = `📈 ${phase} Evaluation: ${(message.total_return * 100).toFixed(2)}% return`;
                progressBar.style.width = message.data_split === 'train' ? '70%' : '85%';
            }
        }

        else if (message.type === 'saving') {
            if (message.status === 'started') {
                progressText.textContent = '💾 Saving model and metadata...';
                progressBar.style.width = '90%';
            } else if (message.status === 'completed') {
                progressText.textContent = '💾 Model saved successfully!';
                progressBar.style.width = '95%';
            }
        }

        else if (message.type === 'completed') {
            delete this.activeJobs[message.job_id];

            // Final completion
            progressBar.style.width = '100%';
            progressText.textContent = `🎉 Training completed! Train: ${(message.train_return * 100).toFixed(2)}% | Test: ${(message.test_return * 100).toFixed(2)}%`;

            // Hide progress after 3 seconds
            setTimeout(() => {
                document.getElementById('trainingProgress').style.display = 'none';
                // Reload models
                this.loadModels();
            }, 3000);

            // Show success
            alert(`Training completed!\n\nTrain Return: ${(message.train_return * 100).toFixed(2)}%\nTest Return: ${(message.test_return * 100).toFixed(2)}%\nOverfitting Score: ${(message.overfitting_score * 100).toFixed(1)}%`);
        }

        else if (message.type === 'error') {
            delete this.activeJobs[message.job_id];

            progressBar.style.width = '0%';
            progressText.textContent = `❌ Training failed: ${message.error}`;
            progressMetrics.textContent = '';

            // Hide progress after 5 seconds
            setTimeout(() => {
                document.getElementById('trainingProgress').style.display = 'none';
            }, 5000);

            alert(`Training failed: ${message.error}`);
        }
    }

    async stopTraining() {
        const jobId = Object.keys(this.activeJobs)[0];
        if (!jobId) return;

        try {
            await fetch(`/api/ml/jobs/${jobId}/stop`, {method: 'POST'});
            delete this.activeJobs[jobId];
            document.getElementById('trainingProgress').style.display = 'none';
        } catch (error) {
            console.error('[ModelManager] Stop training error:', error);
        }
    }
}

// Initialize on page load
let modelManager;
document.addEventListener('DOMContentLoaded', () => {
    modelManager = new ModelManager();
    window.modelManager = modelManager;
});
