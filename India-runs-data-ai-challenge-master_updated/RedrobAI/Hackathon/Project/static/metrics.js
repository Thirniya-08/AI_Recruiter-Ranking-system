/**
 * Metrics Dashboard JavaScript
 * Handles the honeypot detection model evaluation metrics modal
 */

// Initialize metrics when page loads
document.addEventListener('DOMContentLoaded', function() {
    initMetricsModal();
});

function initMetricsModal() {
    const metricsBtn = document.getElementById('metrics-btn');
    const metricsModal = document.getElementById('metrics-modal');
    const closeMetricsBtn = document.getElementById('close-metrics-btn');
    const closeMetricsFooterBtn = document.getElementById('close-metrics-footer-btn');
    const refreshMetricsBtn = document.getElementById('refresh-metrics-btn');

    // Open metrics modal
    if (metricsBtn) {
        metricsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openMetricsModal();
        });
    }

    // Close modal from X button
    if (closeMetricsBtn) {
        closeMetricsBtn.addEventListener('click', closeMetricsModal);
    }

    // Close modal from footer button
    if (closeMetricsFooterBtn) {
        closeMetricsFooterBtn.addEventListener('click', closeMetricsModal);
    }

    // Refresh metrics
    if (refreshMetricsBtn) {
        refreshMetricsBtn.addEventListener('click', loadMetrics);
    }

    // Close modal when clicking outside
    window.addEventListener('click', function(event) {
        if (event.target === metricsModal) {
            closeMetricsModal();
        }
    });
}

function openMetricsModal() {
    const modal = document.getElementById('metrics-modal');
    modal.style.display = 'block';
    loadMetrics();
}

function closeMetricsModal() {
    const modal = document.getElementById('metrics-modal');
    modal.style.display = 'none';
}

function loadMetrics() {
    showLoadingState();
    
    // Fetch metrics from API
    Promise.all([
        fetch('/api/honeypot-metrics').then(r => r.json()),
        fetch('/api/honeypot-confusion-matrix').then(r => r.json()),
        fetch('/api/model-info').then(r => r.json())
    ])
    .then(([metricsData, cmData, modelInfo]) => {
        populateMetrics(metricsData, cmData, modelInfo);
        hideLoadingState();
    })
    .catch(error => {
        console.error('Error loading metrics:', error);
        showError(error.message);
        hideLoadingState();
    });
}

function showLoadingState() {
    [
        'metric-accuracy', 'metric-precision', 'metric-recall', 'metric-f1',
        'metric-specificity', 'metric-sensitivity', 'metric-balanced',
        'metric-mcc', 'metric-fpr', 'metric-fnr', 'metric-roc-auc',
        'stat-total', 'stat-honeypot-rate', 'stat-detection-rate'
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = 'Loading...';
    });
}

function hideLoadingState() {
    // Removed - metrics will be populated
}

function showError(message) {
    const body = document.querySelector('.metrics-body');
    if (body) {
        body.innerHTML = `<div style="color: #dc2626; padding: 20px; text-align: center;">Error: ${message}</div>`;
    }
}

function populateMetrics(metricsData, cmData, modelInfo) {
    if (!metricsData.metrics) {
        showError('Failed to load metrics data');
        return;
    }

    const metrics = metricsData.metrics;
    const cm = cmData.confusion_matrix || {};

    // Update performance metrics
    document.getElementById('metric-accuracy').textContent = metrics.accuracy || '-';
    document.getElementById('metric-precision').textContent = metrics.precision || '-';
    document.getElementById('metric-recall').textContent = metrics.recall || '-';
    document.getElementById('metric-f1').textContent = metrics.f1_score || '-';
    document.getElementById('metric-specificity').textContent = metrics.specificity || '-';
    document.getElementById('metric-sensitivity').textContent = metrics.sensitivity || '-';
    document.getElementById('metric-balanced').textContent = metrics.balanced_accuracy || '-';
    document.getElementById('metric-mcc').textContent = metrics.mcc || '-';

    // Update error rates
    document.getElementById('metric-fpr').textContent = metrics.false_positive_rate || '-';
    document.getElementById('metric-fnr').textContent = metrics.false_negative_rate || '-';
    document.getElementById('metric-roc-auc').textContent = metrics.roc_auc || '-';

    // Update confusion matrix
    document.getElementById('cm-tp').innerHTML = `<div class="cm-number">${cm.true_positives || 0}</div><div class="cm-label">TP</div>`;
    document.getElementById('cm-fn').innerHTML = `<div class="cm-number">${cm.false_negatives || 0}</div><div class="cm-label">FN</div>`;
    document.getElementById('cm-fp').innerHTML = `<div class="cm-number">${cm.false_positives || 0}</div><div class="cm-label">FP</div>`;
    document.getElementById('cm-tn').innerHTML = `<div class="cm-number">${cm.true_negatives || 0}</div><div class="cm-label">TN</div>`;

    // Update dataset statistics
    document.getElementById('stat-total').textContent = metrics.total_samples || '0';
    document.getElementById('stat-honeypot-rate').textContent = metrics.honeypot_rate || '-';
    document.getElementById('stat-detection-rate').textContent = metrics.detection_rate || '-';

    // Update model info
    if (modelInfo) {
        modelInfo.label_note = metricsData.label_note;
        modelInfo.label_source = metricsData.label_source;
        populateModelInfo(modelInfo);
    }
}

function populateModelInfo(modelInfo) {
    const infoPanel = document.getElementById('model-info-content');
    if (!infoPanel) return;

    let html = `
        <div class="info-item">
            <strong>Model Name:</strong><br/>
            <span>${modelInfo.model_name || 'N/A'}</span>
        </div>
        <div class="info-item">
            <strong>Version:</strong><br/>
            <span>${modelInfo.version || 'N/A'}</span>
        </div>
        <div class="info-item">
            <strong>Status:</strong><br/>
            <span>${modelInfo.status || 'N/A'}</span>
        </div>
        <div class="info-item">
            <strong>Last Updated:</strong><br/>
            <span>${modelInfo.last_update || 'N/A'}</span>
        </div>
    `;

    if (modelInfo.label_note) {
        html += `
            <div class="info-item" style="grid-column: 1/-1;">
                <strong>Evaluation Source:</strong><br/>
                <span>${modelInfo.label_note}</span>
            </div>
        `;
    }

    if (modelInfo.improvements && modelInfo.improvements.length > 0) {
        html += `<div class="info-item" style="grid-column: 1/-1;"><strong>Latest Improvements:</strong><br/>`;
        modelInfo.improvements.forEach(imp => {
            html += `<div style="margin-left: 12px; color: #aaa;">✓ ${imp}</div>`;
        });
        html += `</div>`;
    }

    if (modelInfo.features) {
        html += `<div class="info-item" style="grid-column: 1/-1;"><strong>Detection Methods:</strong><br/>`;
        Object.entries(modelInfo.features).forEach(([key, value]) => {
            html += `<div style="margin-left: 12px; color: #aaa;">• <strong style="color: #667eea;">${key}:</strong> ${value}</div>`;
        });
        html += `</div>`;
    }

    infoPanel.innerHTML = html;
}

// Export functions for use in other scripts
window.metricsModule = {
    openMetricsModal,
    closeMetricsModal,
    loadMetrics,
};
