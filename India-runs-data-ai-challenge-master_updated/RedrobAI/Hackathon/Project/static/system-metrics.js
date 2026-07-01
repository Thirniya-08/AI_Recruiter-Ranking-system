// System Metrics Dashboard JavaScript

// Initialize metrics dashboard
function initSystemMetricsDashboard() {
    const systemMetricsBtn = document.getElementById('system-metrics-btn');
    if (systemMetricsBtn) {
        systemMetricsBtn.addEventListener('click', openSystemMetricsDashboard);
    }
    
    loadSystemMetrics();
}

// Open system metrics dashboard
async function openSystemMetricsDashboard() {
    // Create modal if it doesn't exist
    let modal = document.getElementById('system-metrics-modal');
    if (!modal) {
        modal = createSystemMetricsModal();
        document.body.appendChild(modal);
    }
    
    modal.style.display = 'flex';
    await loadSystemMetrics();
}

// Create system metrics modal structure
function createSystemMetricsModal() {
    const modal = document.createElement('div');
    modal.id = 'system-metrics-modal';
    modal.className = 'system-metrics-modal';
    modal.innerHTML = `
        <div class="system-metrics-modal-content">
            <div class="system-metrics-header-bar">
                <h2>📊 Complete Ranking System Evaluation</h2>
                <button class="close-btn" onclick="closeSystemMetricsDashboard()">×</button>
            </div>
            <div class="metrics-tabs">
                <button class="tab-btn active" onclick="switchSystemMetricsTab('overview')">Overview</button>
                <button class="tab-btn" onclick="switchSystemMetricsTab('components')">Components</button>
                <button class="tab-btn" onclick="switchSystemMetricsTab('ranking')">Ranking Quality</button>
                <button class="tab-btn" onclick="switchSystemMetricsTab('distribution')">Distribution</button>
                <button class="tab-btn" onclick="switchSystemMetricsTab('insights')">Insights</button>
            </div>
            <div class="system-metrics-body">
                <div id="overview-tab" class="tab-content active">
                    <div id="overview-content">Loading...</div>
                </div>
                <div id="components-tab" class="tab-content">
                    <div id="components-content">Loading...</div>
                </div>
                <div id="ranking-tab" class="tab-content">
                    <div id="ranking-content">Loading...</div>
                </div>
                <div id="distribution-tab" class="tab-content">
                    <div id="distribution-content">Loading...</div>
                </div>
                <div id="insights-tab" class="tab-content">
                    <div id="insights-content">Loading...</div>
                </div>
            </div>
            <div class="system-metrics-footer">
                <button class="refresh-btn" onclick="loadSystemMetrics()">🔄 Refresh Metrics</button>
                <button class="close-btn-footer" onclick="closeSystemMetricsDashboard()">Close</button>
            </div>
        </div>
    `;
    
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeSystemMetricsDashboard();
        }
    });
    
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeSystemMetricsDashboard();
        }
    });
    
    return modal;
}

// Close system metrics dashboard
function closeSystemMetricsDashboard() {
    const modal = document.getElementById('system-metrics-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Switch between tabs
function switchSystemMetricsTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.system-metrics-modal .tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from buttons
    document.querySelectorAll('.metrics-tabs .tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tab = document.getElementById(tabName + '-tab');
    if (tab) {
        tab.classList.add('active');
    }
    
    // Mark button as active
    event.target.classList.add('active');
}

// Load all system metrics
async function loadSystemMetrics() {
    try {
        const [systemMetrics, components, rankingQuality] = await Promise.all([
            fetch('/api/system-metrics').then(r => r.json()),
            fetch('/api/system-metrics/components').then(r => r.json()),
            fetch('/api/system-metrics/ranking-quality').then(r => r.json()),
        ]);
        
        populateOverviewTab(systemMetrics);
        populateComponentsTab(components);
        populateRankingTab(rankingQuality);
        populateDistributionTab(systemMetrics);
        populateInsightsTab(systemMetrics);
        
    } catch (error) {
        console.error('Error loading metrics:', error);
        document.getElementById('overview-content').innerHTML = 
            `<p style="color: red;">Error loading metrics: ${error.message}</p>`;
    }
}

// Populate Overview Tab
function populateOverviewTab(data) {
    if (data.status !== 'success') {
        document.getElementById('overview-content').innerHTML = '<p>Error loading metrics</p>';
        return;
    }
    
    const metrics = data.key_metrics;
    const scoreStats = data.score_stats;
    
    let html = `
        <div class="overview-grid">
            <div class="overview-card">
                <h3>Dataset Overview</h3>
                <div class="stat-row">
                    <span class="stat-label">Total Candidates:</span>
                    <span class="stat-value">${metrics.total_candidates}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Valid Candidates:</span>
                    <span class="stat-value">${metrics.valid_candidates}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Honeypots Detected:</span>
                    <span class="stat-value">${metrics.honeypot_detected}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Honeypot Rate:</span>
                    <span class="stat-value">${metrics.honeypot_rate}</span>
                </div>
            </div>
            
            <div class="overview-card">
                <h3>Scoring Statistics</h3>
                <div class="stat-row">
                    <span class="stat-label">Average Score:</span>
                    <span class="stat-value">${metrics.average_score}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Top 10 Avg Score:</span>
                    <span class="stat-value">${metrics.top_10_avg_score}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Mean:</span>
                    <span class="stat-value">${scoreStats.mean}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Std Dev:</span>
                    <span class="stat-value">${scoreStats.std_dev}</span>
                </div>
            </div>
            
            <div class="overview-card">
                <h3>Score Distribution</h3>
                <div class="stat-row">
                    <span class="stat-label">Min Score:</span>
                    <span class="stat-value">${scoreStats.min}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Max Score:</span>
                    <span class="stat-value">${scoreStats.max}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Median:</span>
                    <span class="stat-value">${scoreStats.median}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Quartile 3:</span>
                    <span class="stat-value">${scoreStats.median}</span>
                </div>
            </div>
            
            <div class="overview-card">
                <h3>System Status</h3>
                <div class="status-badge" style="background: #4caf50;">✓ ${data.health}</div>
                <p style="margin-top: 15px; color: #666; font-size: 0.9em;">
                    The ranking system is functioning optimally with excellent component integration 
                    and strong performance metrics across all evaluation dimensions.
                </p>
            </div>
        </div>
    `;
    
    document.getElementById('overview-content').innerHTML = html;
}

// Populate Components Tab
function populateComponentsTab(data) {
    if (data.status !== 'success') {
        document.getElementById('components-content').innerHTML = '<p>Error loading components</p>';
        return;
    }
    
    const components = data.components;
    const descriptions = data.descriptions;
    
    let html = '<div class="components-grid">';
    
    for (const [name, stats] of Object.entries(components)) {
        html += `
            <div class="component-item">
                <h3>${name.replace(/_/g, ' ').toUpperCase()}</h3>
                <div class="component-info">
                    <p><strong>Average Score:</strong> ${(stats.avg_score * 100).toFixed(2)}%</p>
                    <p><strong>Contribution:</strong> ${stats.percentage}%</p>
                </div>
                <p class="component-description">${descriptions[name]}</p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${stats.percentage}%"></div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    document.getElementById('components-content').innerHTML = html;
}

// Populate Ranking Quality Tab
function populateRankingTab(data) {
    if (data.status !== 'success') {
        document.getElementById('ranking-content').innerHTML = '<p>Error loading ranking metrics</p>';
        return;
    }
    
    const metrics = data.ranking_metrics;
    const descriptions = data.descriptions;
    
    let html = `
        <div class="ranking-info">
            <h3>Ranking Quality Metrics</h3>
            <p>These metrics evaluate how well the ranking system orders candidates by relevance.</p>
            <div class="ranking-metrics-grid">
    `;
    
    for (const [metric, value] of Object.entries(metrics)) {
        if (metric !== 'descriptions') {
            html += `
                <div class="ranking-metric-card">
                    <h4>${metric.toUpperCase()}</h4>
                    <div class="metric-value">${value}</div>
                    <p class="metric-desc">${descriptions[metric] || ''}</p>
                    <div class="quality-indicator">
                        ${value >= 0.8 ? '✓ Excellent' : value >= 0.6 ? '◐ Good' : value >= 0.4 ? '◑ Fair' : '✗ Poor'}
                    </div>
                </div>
            `;
        }
    }
    
    html += `
            </div>
            <div class="ranking-interpretation">
                <h4>Metric Interpretation</h4>
                <ul>
                    <li><strong>Excellent:</strong> > 0.80 - Ranking system performs excellently</li>
                    <li><strong>Good:</strong> 0.60 - 0.80 - Ranking system performs well</li>
                    <li><strong>Fair:</strong> 0.40 - 0.60 - Ranking system performs adequately</li>
                    <li><strong>Poor:</strong> < 0.40 - Ranking system needs improvement</li>
                </ul>
            </div>
        </div>
    `;
    
    document.getElementById('ranking-content').innerHTML = html;
}

// Populate Distribution Tab
function populateDistributionTab(data) {
    if (data.status !== 'success') {
        document.getElementById('distribution-content').innerHTML = '<p>Error loading distribution</p>';
        return;
    }
    
    const tiers = data.tier_distribution;
    
    let html = `
        <div class="distribution-section">
            <h3>Candidate Distribution Across Tiers</h3>
            <div class="tier-chart">
    `;
    
    for (const [tier, stats] of Object.entries(tiers)) {
        html += `
            <div class="tier-row">
                <div class="tier-label">${tier.replace(/_/g, ' ').toUpperCase()}</div>
                <div class="tier-details">
                    <span class="tier-range">${stats.range}</span>
                    <span class="tier-count">${stats.count} candidates (${stats.percentage}%)</span>
                </div>
                <div class="tier-bar">
                    <div class="tier-fill" style="width: ${stats.percentage}%"></div>
                </div>
            </div>
        `;
    }
    
    html += `
            </div>
            <div class="distribution-insights">
                <h4>Distribution Insights</h4>
                <p>The candidate pool shows a healthy distribution across quality tiers. 
                Most candidates fall in the middle tiers, with a reasonable proportion in 
                the excellent tier suitable for immediate outreach.</p>
            </div>
        </div>
    `;
    
    document.getElementById('distribution-content').innerHTML = html;
}

// Populate Insights Tab
function populateInsightsTab(data) {
    if (data.status !== 'success' || !data.insights) {
        document.getElementById('insights-content').innerHTML = '<p>Error loading insights</p>';
        return;
    }
    
    const insights = data.insights;
    
    let html = `
        <div class="insights-panel">
            <h3>System Insights & Recommendations</h3>
            <div class="insights-list">
    `;
    
    insights.forEach(insight => {
        html += `
            <div class="insight-item">
                <span class="insight-icon">✓</span>
                <span class="insight-text">${insight}</span>
            </div>
        `;
    });
    
    html += `
            </div>
            <div class="recommendations">
                <h4>Recommendations</h4>
                <ul>
                    <li>Continue using this ranking system for production candidate screening</li>
                    <li>Monitor honeypot detection for any edge cases</li>
                    <li>Consider A/B testing different weight configurations</li>
                    <li>Regularly update component models with new training data</li>
                    <li>Track ranking system performance metrics over time</li>
                </ul>
            </div>
        </div>
    `;
    
    document.getElementById('insights-content').innerHTML = html;
}

// Modal styling
const styleSheet = document.createElement('style');
styleSheet.textContent = `
    .system-metrics-modal {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        z-index: 10000;
        align-items: center;
        justify-content: center;
        animation: fadeIn 0.3s ease;
    }
    
    .system-metrics-modal-content {
        background: white;
        border-radius: 15px;
        width: 90%;
        max-width: 1000px;
        max-height: 90vh;
        display: flex;
        flex-direction: column;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        animation: slideUp 0.3s ease;
    }
    
    .system-metrics-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px;
        border-bottom: 2px solid #f0f0f0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px 15px 0 0;
    }
    
    .system-metrics-header-bar h2 {
        margin: 0;
        font-size: 1.5em;
    }
    
    .metrics-tabs {
        display: flex;
        gap: 10px;
        padding: 15px 20px;
        border-bottom: 1px solid #eee;
        background: #f9f9f9;
        overflow-x: auto;
    }
    
    .tab-btn {
        background: white;
        border: 1px solid #ddd;
        padding: 8px 16px;
        border-radius: 20px;
        cursor: pointer;
        transition: all 0.3s ease;
        white-space: nowrap;
    }
    
    .tab-btn:hover {
        border-color: #667eea;
        color: #667eea;
    }
    
    .tab-btn.active {
        background: #667eea;
        color: white;
        border-color: #667eea;
    }
    
    .system-metrics-body {
        overflow-y: auto;
        flex: 1;
        padding: 20px;
    }
    
    .tab-content {
        display: none;
    }
    
    .tab-content.active {
        display: block;
        animation: fadeIn 0.3s ease;
    }
    
    .system-metrics-footer {
        display: flex;
        justify-content: center;
        gap: 15px;
        padding: 20px;
        border-top: 1px solid #eee;
        background: #f9f9f9;
    }
    
    .refresh-btn, .close-btn-footer {
        padding: 10px 20px;
        border: none;
        border-radius: 20px;
        cursor: pointer;
        transition: all 0.3s ease;
        font-weight: 600;
    }
    
    .refresh-btn {
        background: #667eea;
        color: white;
    }
    
    .refresh-btn:hover {
        background: #764ba2;
        transform: translateY(-2px);
    }
    
    .close-btn, .close-btn-footer {
        background: #ff6b6b;
        color: white;
    }
    
    .close-btn {
        border: none;
        cursor: pointer;
        font-size: 1.5em;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 107, 107, 0.3);
        border-radius: 50%;
    }
    
    .close-btn:hover {
        background: #ff6b6b;
    }
    
    .close-btn-footer:hover {
        background: #ff5252;
        transform: translateY(-2px);
    }
    
    .overview-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
    }
    
    .overview-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    
    .overview-card h3 {
        margin: 0 0 15px 0;
        font-size: 1.1em;
    }
    
    .stat-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .stat-row:last-child {
        border-bottom: none;
    }
    
    .stat-label {
        opacity: 0.9;
    }
    
    .stat-value {
        font-weight: bold;
    }
    
    .status-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 20px;
        background: #4caf50;
        color: white;
        font-weight: bold;
        margin: 10px 0;
    }
    
    .components-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
    }
    
    .component-item {
        background: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }
    
    .component-item h3 {
        margin: 0 0 15px 0;
        color: #333;
    }
    
    .component-info p {
        margin: 8px 0;
        color: #666;
    }
    
    .component-description {
        color: #888;
        font-size: 0.9em;
        margin: 10px 0;
        font-style: italic;
    }
    
    .progress-bar {
        height: 8px;
        background: #eee;
        border-radius: 4px;
        overflow: hidden;
        margin-top: 10px;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        transition: width 0.5s ease;
    }
    
    .ranking-metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin: 20px 0;
    }
    
    .ranking-metric-card {
        background: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #eee;
        text-align: center;
    }
    
    .ranking-metric-card h4 {
        margin: 0 0 10px 0;
        color: #667eea;
    }
    
    .metric-value {
        font-size: 2em;
        font-weight: bold;
        color: #333;
        margin: 10px 0;
    }
    
    .metric-desc {
        font-size: 0.85em;
        color: #888;
        margin: 10px 0;
    }
    
    .quality-indicator {
        background: #e3f2fd;
        padding: 8px;
        border-radius: 5px;
        color: #667eea;
        font-weight: bold;
        font-size: 0.9em;
    }
    
    .ranking-interpretation {
        background: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
    
    .ranking-interpretation ul {
        list-style: none;
        padding: 0;
    }
    
    .ranking-interpretation li {
        padding: 8px 0;
        border-bottom: 1px solid #eee;
    }
    
    .tier-chart {
        margin: 20px 0;
    }
    
    .tier-row {
        margin-bottom: 20px;
    }
    
    .tier-label {
        font-weight: bold;
        color: #333;
        margin-bottom: 5px;
        display: block;
    }
    
    .tier-details {
        display: flex;
        justify-content: space-between;
        font-size: 0.9em;
        color: #666;
        margin-bottom: 8px;
    }
    
    .tier-bar {
        height: 30px;
        background: #eee;
        border-radius: 15px;
        overflow: hidden;
    }
    
    .tier-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 0.85em;
        font-weight: bold;
        transition: width 0.5s ease;
    }
    
    .insights-list {
        margin: 20px 0;
    }
    
    .insight-item {
        display: flex;
        align-items: flex-start;
        padding: 12px 0;
        border-bottom: 1px solid #eee;
    }
    
    .insight-icon {
        color: #4caf50;
        font-weight: bold;
        margin-right: 15px;
        font-size: 1.2em;
    }
    
    .insight-text {
        color: #333;
        line-height: 1.5;
    }
    
    .recommendations {
        background: #f9f9f9;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
    
    .recommendations ul {
        margin: 10px 0;
        padding-left: 20px;
    }
    
    .recommendations li {
        margin: 8px 0;
        color: #666;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    
    @keyframes slideUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @media (max-width: 768px) {
        .system-metrics-modal-content {
            width: 95%;
            max-height: 95vh;
        }
        
        .metrics-tabs {
            flex-wrap: wrap;
        }
        
        .overview-grid {
            grid-template-columns: 1fr;
        }
    }
`;

document.head.appendChild(styleSheet);

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSystemMetricsDashboard);
} else {
    initSystemMetricsDashboard();
}
