// Redrob AI Candidate Ranking Dashboard - JavaScript Client

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const dropzone = document.getElementById("dropzone");
    const fileInput = document.getElementById("file-input");
    const fileList = document.getElementById("file-list");
    const fileListContainer = document.getElementById("file-list-container");
    const progressContainer = document.getElementById("upload-progress-container");
    const progressBarFill = document.getElementById("progress-bar-fill");
    const progressStatus = document.getElementById("progress-status");
    const progressPercent = document.getElementById("progress-percent");
    
    const topNSlider = document.getElementById("top-n-slider");
    const topNInput = document.getElementById("top-n-input");
    const topCandidatesDisplay = document.getElementById("top-candidates-display");
    
    const rankBtn = document.getElementById("rank-btn");
    const exportBtn = document.getElementById("export-btn");
    const clearBtn = document.getElementById("clear-btn");
    
    const statTotal = document.getElementById("stat-total-candidates");
    const statValid = document.getElementById("stat-valid-candidates");
    const statTotalHoneypots = document.getElementById("stat-total-honeypots");
    const statTop100Honeypots = document.getElementById("stat-top-100-honeypots");
    const resultsCount = document.getElementById("results-count");
    
    const searchBar = document.getElementById("search-bar");
    const tableBody = document.getElementById("table-body");
    
    const detailsModal = document.getElementById("details-modal");
    const modalClose = document.getElementById("modal-close");
    
    // Global state
    let loadedCandidates = [];
    let currentRankings = [];
    let isUploading = false;
    let maxCandidates = 0;

    function escapeHTML(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // --- Drag and Drop File Handlers ---
    dropzone.addEventListener("click", () => {
        if (!isUploading) fileInput.click();
    });

    dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        if (!isUploading) dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        if (isUploading) return;
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    // --- Upload Files via XHR for Progress Monitoring ---
    function handleFileUpload(file) {
        isUploading = true;
        progressContainer.style.style = "block";
        progressContainer.style.display = "block";
        progressBarFill.style.width = "0%";
        progressPercent.textContent = "0%";
        progressStatus.textContent = "Uploading & parsing candidate file...";
        fileList.innerHTML = "";
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="table-placeholder">
                    <div class="placeholder-content">
                        <p>Replacing the existing dataset with the newly uploaded file...</p>
                    </div>
                </td>
            </tr>
        `;
        resultsCount.textContent = "0 candidates";
        loadedCandidates = [];
        currentRankings = [];
        renderTop100Honeypots([], []);
        
        const formData = new FormData();
        formData.append("files", file);
        addFileToList(file);

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload", true);

        // Track upload progress
        xhr.upload.addEventListener("progress", (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 90); // cap upload part to 90%
                progressBarFill.style.width = percent + "%";
                progressPercent.textContent = percent + "%";
            }
        });

        xhr.onreadystatechange = () => {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                isUploading = false;
                if (xhr.status === 200) {
                    progressBarFill.style.width = "100%";
                    progressPercent.textContent = "100%";
                    progressStatus.textContent = "Processing complete!";
                    
                    const response = JSON.parse(xhr.responseText);
                    updateStats(response);
                    updateHoneypotSummary(response);
                    renderTop100Honeypots([], []);
                    
                    // Enable buttons
                    rankBtn.classList.remove("disabled");
                    rankBtn.disabled = false;
                    exportBtn.classList.remove("disabled");
                    exportBtn.disabled = false;
                    
                    // Honeypots remain scorable after penalty, so ranking can span the full pool.
                    maxCandidates = response.total_candidates;
                    if (maxCandidates > 0) {
                        topNSlider.min = Math.min(10, maxCandidates);
                        topNSlider.max = maxCandidates;
                        topNInput.min = 1;
                        topNInput.max = maxCandidates;
                        if (parseInt(topNInput.value) > maxCandidates) {
                            topNInput.value = maxCandidates;
                            topNSlider.value = maxCandidates;
                        }
                    } else {
                        topNSlider.min = 10;
                        topNSlider.max = 100;
                        topNInput.min = 1;
                        topNInput.max = 100;
                    }
                    syncTopCandidatesDisplay();
                    
                    // Auto-trigger initial ranking load (will poll for progress)
                    rankBtn.click();
                } else {
                    progressStatus.textContent = "Upload failed.";
                    let message = "Error uploading files. Ensure they are valid JSON/JSONL/PDF/DOCX formats.";
                    try {
                        const response = JSON.parse(xhr.responseText);
                        const details = response.errors && response.errors.length
                            ? response.errors.join("\n")
                            : response.error;
                        if (details) message = details;
                    } catch (e) {
                        // Keep the generic fallback when the backend response is not JSON.
                    }
                    alert(message);
                }
                
                // Hide progress bar after 2 seconds
                setTimeout(() => {
                    progressContainer.style.display = "none";
                }, 2000);
            }
        };

        xhr.send(formData);
    }

    function addFileToList(file) {
        fileListContainer.style.display = "block";
        const li = document.createElement("li");
        li.className = "file-item";
        
        const sizeKB = (file.size / 1024).toFixed(1);
        li.innerHTML = `
            <span class="file-name" title="${file.name}">${file.name}</span>
            <span class="file-size">${sizeKB} KB</span>
        `;
        fileList.appendChild(li);
    }

    function updateStats(data) {
        const total = data.total_candidates || 0;
        const valid = data.total_valid_candidates ?? data.total_valid ?? data.valid_candidates ?? 0;
        statTotal.textContent = total.toLocaleString();
        statValid.textContent = valid.toLocaleString();
    }

    // --- Slider & Numeric Input Synchronization ---
    function syncTopCandidatesDisplay() {
        if (topCandidatesDisplay) {
            topCandidatesDisplay.textContent = (parseInt(topNInput.value, 10) || 100).toLocaleString();
        }
    }

    syncTopCandidatesDisplay();

    topNSlider.addEventListener("input", (e) => {
        topNInput.value = e.target.value;
        syncTopCandidatesDisplay();
        // Fetch rankings immediately on slider releases for quick response
    });

    topNSlider.addEventListener("change", () => {
        fetchRankings();
    });

    topNInput.addEventListener("change", (e) => {
        let val = parseInt(e.target.value);
        if (isNaN(val) || val < 1) val = 100;
        if (maxCandidates > 0 && val > maxCandidates) val = maxCandidates;
        
        topNInput.value = val;
        topNSlider.value = val;
        syncTopCandidatesDisplay();
        fetchRankings();
    });

    // --- Execute Ranker Event ---
    rankBtn.addEventListener("click", () => {
        fetchRankings();
    });

    // --- Clear Dashboard ---
    clearBtn.addEventListener("click", () => {
        fetch("/api/clear", { method: "POST" })
            .then(res => res.json())
            .then(() => {
                // Reset stats and UI state
                lastResultsCount = 0;
                statTotal.textContent = "0";
                statValid.textContent = "0";
                statTotalHoneypots.textContent = "0";
                statTop100Honeypots.textContent = "0";
                resultsCount.textContent = "0 candidates";
                fileList.innerHTML = "";
                fileListContainer.style.display = "none";
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="8" class="table-placeholder">
                            <div class="placeholder-content">
                                <p>No candidates loaded yet. Drag and drop a dataset (JSON/JSONL) or resumes (PDF/DOCX) on the left side to get started.</p>
                            </div>
                        </td>
                    </tr>
                `;
                rankBtn.classList.add("disabled");
                rankBtn.disabled = true;
                exportBtn.classList.add("disabled");
                exportBtn.disabled = true;
                topNSlider.value = 100;
                topNInput.value = 100;
                loadedCandidates = [];
                currentRankings = [];
                updateHoneypotSummary({ total_honeypots: 0, honeypots_in_top_100: 0 });
                renderTop100Honeypots([], []);
            });
    });

    // --- Fetch Rankings API with Countdown Timer and Partial Results ---
    let statusPollingInterval = null;
    let lastResultsCount = 0;  // Track when results update
    
    function checkRankingStatus() {
        /**Poll the backend to check if scoring is complete, display countdown timer and partial results.*/
        if (statusPollingInterval) clearInterval(statusPollingInterval);
        
        const pollStatus = () => {
            fetch("/api/ranking-status")
                .then(res => res.json())
                .then(status => {
                    const btnTextEl = rankBtn.querySelector(".btn-text");
                    
                    if (status.results_ready) {
                        // We have results available! Fetch them immediately
                        if (lastResultsCount !== status.partial_results_count) {
                            lastResultsCount = status.partial_results_count;
                            fetchPartialRankings();
                        }
                        
                        if (!status.is_scoring) {
                            // Scoring complete
                            if (statusPollingInterval) clearInterval(statusPollingInterval);
                            if (btnTextEl) btnTextEl.textContent = "Execute Ranker";
                        } else {
                            // Still scoring but have results, show countdown
                            const remainingTime = Math.max(0, Math.ceil(status.estimated_time_remaining || 10));
                            const percent = status.total_candidates > 0 
                                ? Math.round((status.candidates_scored / status.total_candidates) * 100)
                                : 0;
                            
                            if (btnTextEl) {
                                btnTextEl.textContent = `Ranking in ${remainingTime}s...`;
                            }
                            
                            // Show update indicator
                            resultsCount.textContent = `${status.partial_results_count} candidates ranked (${percent}% complete, updating...)`;
                        }
                    } else if (status.is_scoring) {
                        // Still scoring, no results yet
                        const remainingTime = Math.max(0, Math.ceil(status.estimated_time_remaining || 60));
                        const percent = status.total_candidates > 0 
                            ? Math.round((status.candidates_scored / status.total_candidates) * 100)
                            : 0;
                        
                        if (btnTextEl) {
                            btnTextEl.textContent = `Ranking in ${remainingTime}s...`;
                        }
                        
                        tableBody.innerHTML = `
                            <tr>
                                <td colspan="8" class="table-placeholder">
                                    <div class="placeholder-content">
                                        <div class="loading-spinner"></div>
                                        <p style="margin-top: 1rem; font-size: 1.1rem; font-weight: 500;">⏳ Scoring candidates...</p>
                                        <p style="font-size: 0.9rem; color: var(--text-muted); margin-top: 0.5rem;">
                                            Progress: <strong>${percent}%</strong> (${status.candidates_scored} / ${status.total_candidates})
                                        </p>
                                        <p style="font-size: 1rem; color: #2196F3; font-weight: bold; margin-top: 1rem;">
                                            ⏱️ Estimated time: ${remainingTime}s remaining
                                        </p>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }
                })
                .catch(err => {
                    console.error("Status check error:", err);
                    if (statusPollingInterval) clearInterval(statusPollingInterval);
                    resultsCount.textContent = "Unable to contact backend. Please start the server and refresh.";
                    if (btnTextEl) btnTextEl.textContent = "Execute Ranker";
                });
        };
        
        // Poll every 500ms for faster updates during batch processing
        statusPollingInterval = setInterval(pollStatus, 500);
        pollStatus(); // Check immediately
    }
    
    function fetchPartialRankings() {
        /**Fetch partial rankings while scoring is in progress."""
        const topN = parseInt(topNInput.value) || 100;
        
        fetch("/api/rank", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ top_n: topN })
        })
        .then(res => res.json())
            .then(data => {
                currentRankings = data.results;
                renderTable(currentRankings);
                updateHoneypotSummary(data);
                renderTop100Honeypots(data.top_100_honeypots || [], data.sample_honeypots || []);
        })
        .catch(err => {
            console.error(err);
        });
    }
    
    function fetchActualRankings() {
        /**Fetch rankings after scoring is complete.*/
        const topN = parseInt(topNInput.value) || 100;
        
        fetch("/api/rank", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ top_n: topN })
        })
        .then(res => res.json())
        .then(data => {
            currentRankings = data.results;
            resultsCount.textContent = `${data.results.length} ranked candidates`;
            renderTable(currentRankings);
            updateHoneypotSummary(data);
            renderTop100Honeypots(data.top_100_honeypots || [], data.sample_honeypots || []);
            if (data.validation_report && data.validation_report.reference && data.validation_report.top && !data.validation_report.error) {
                document.getElementById("validation-report-container").style.display = "block";
                renderValidationReport(data.validation_report);
            }
        })
        .catch(err => {
            console.error(err);
            tableBody.innerHTML = `<tr><td colspan="8" class="table-placeholder alert-text">Failed to retrieve rankings.</td></tr>`;
        })
        .finally(() => {
            // Re-enable ranking button
            rankBtn.classList.remove("disabled");
            rankBtn.disabled = false;
            exportBtn.classList.remove("disabled");
            exportBtn.disabled = false;
            const btnTextEl = rankBtn.querySelector(".btn-text");
            if (btnTextEl) btnTextEl.textContent = "Execute Ranker";
        });
    }
    
    function fetchRankings() {
        // Disable ranking button during execution
        rankBtn.classList.add("disabled");
        rankBtn.disabled = true;
        exportBtn.classList.add("disabled");
        exportBtn.disabled = true;
        
        const btnTextEl = rankBtn.querySelector(".btn-text");
        const origText = btnTextEl ? btnTextEl.textContent : "Execute Ranker";
        if (btnTextEl) btnTextEl.textContent = "Checking scoring status...";
        
        // Start polling for status with countdown
        lastResultsCount = 0;
        checkRankingStatus();
    }

    // --- Render Results Table ---
    function renderTable(results) {
        if (results.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="table-placeholder">
                        <p>No valid candidates found matching criteria.</p>
                    </td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = "";
        
        results.forEach((cand, idx) => {
            const tr = document.createElement("tr");
            
            // Determine rank badge class
            let rankClass = "rank-other";
            if (cand.rank === 1) rankClass = "rank-top1";
            else if (cand.rank === 2) rankClass = "rank-top2";
            else if (cand.rank === 3) rankClass = "rank-top3";
            
            // Determine score indicator class
            const scoreVal = parseFloat(cand.score);
            let scoreClass = "score-low";
            if (scoreVal >= 0.75) scoreClass = "score-high";
            else if (scoreVal >= 0.45) scoreClass = "score-med";
            
            // Calculate score difference from previous candidate
            let scoreDiffHtml = '';
            if (idx > 0) {
                const prevScore = parseFloat(results[idx - 1].score);
                const currScore = parseFloat(cand.score);
                const diff = prevScore - currScore;
                scoreDiffHtml = `<small class="score-diff">
                    ▼ ${diff.toFixed(3)}
                </small>`;
            }
            tr.innerHTML = `
                <td class="col-rank">
                    <span class="rank-badge ${rankClass}">${cand.rank}</span>
                </td>
                <td class="col-id">
                    <div class="candidate-cell">
                        <div>
                            <strong>${escapeHTML(cand.name)}</strong>
                            <span>${escapeHTML(cand.current_title)}</span>
                            <small>${escapeHTML(cand.candidate_id)}</small>
                        </div>
                    </div>
                </td>
                <td class="col-name">${escapeHTML(cand.name)}</td>
                <td class="col-title">${cand.current_title}</td>
                <td class="col-location">${cand.location}</td>
                <td class="col-yoe" style="text-align:center;">${cand.yoe.toFixed(1)}</td>
                <td class="col-score" style="text-align:right;">
                    <span class="score-text ${scoreClass}" title="Exact: ${cand.score}">${cand.score}</span>
                    ${scoreDiffHtml}
                </td>
                <td class="col-action">
                    <button class="btn btn-secondary btn-sm inspect-btn" data-id="${cand.candidate_id}">Inspect</button>
                </td>
            `;
            
            tableBody.appendChild(tr);
        });

        // Add inspect event listeners
        document.querySelectorAll(".inspect-btn").forEach(btn => {
            btn.addEventListener("click", function (e) {
                const cid = this.getAttribute("data-id");
                const candidate = results.find(r => r.candidate_id === cid);
                if (candidate) {
                    showDetailsModal(candidate);
                }
            });
        });
    }

    function updateHoneypotSummary(data) {
        const totalCandidates = data.total_candidates || parseInt(statTotal?.textContent?.replace(/,/g, ""), 10) || 0;
        const validCandidates = data.total_valid_candidates ?? data.total_valid ?? data.valid_candidates ?? parseInt(statValid?.textContent?.replace(/,/g, ""), 10) ?? 0;
        const derivedDatasetHoneypots = Math.max(0, totalCandidates - validCandidates);
        const explicitDatasetHoneypots = data.total_honeypots ?? data.honeypots;
        const total = Math.max(explicitDatasetHoneypots || 0, derivedDatasetHoneypots);
        const top100 = data.honeypots_in_top_n ?? data.honeypots_in_top_100 ?? 0;
        if (statTotalHoneypots) statTotalHoneypots.textContent = total.toLocaleString();
        if (statTop100Honeypots) statTop100Honeypots.textContent = top100.toLocaleString();
    }

    function renderTop100Honeypots(honeypots, sampleHoneypots = []) {
        const card = document.getElementById("top-100-honeypots-card");
        const list = document.getElementById("top-100-honeypots-list");
        const count = document.getElementById("top-100-honeypots-count");
        if (!card || !list || !count) return;

        if (!honeypots.length && !sampleHoneypots.length) {
            card.style.display = "none";
            list.innerHTML = "";
            count.textContent = "0 candidates";
            return;
        }

        card.style.display = "block";
        const candidatesToRender = honeypots.length ? honeypots : sampleHoneypots;
        count.textContent = honeypots.length
            ? `${honeypots.length} Top 100 candidate${honeypots.length === 1 ? "" : "s"}`
            : `0 Top 100, ${sampleHoneypots.length} dataset sample${sampleHoneypots.length === 1 ? "" : "s"}`;

        const intro = honeypots.length ? `
            <div class="top100-honeypot-message has-risk">
                Honeypot candidates found within the Top 100 are listed below with Explainable AI reasoning.
            </div>
        ` : `
            <div class="top100-honeypot-message">
                No honeypot candidates appear in the Top 100. Sample honeypot candidates from the full dataset are shown below for audit visibility.
            </div>
        `;

        list.innerHTML = intro + candidatesToRender.map(candidate => {
            const reasons = candidate.honeypot_reasons || [];
            const reasoning = candidate.xai_reasoning || candidate.reasoning || "Honeypot rule threshold was met after scoring.";
            const baseScore = candidate.base_score_before_honeypot_penalty ?? candidate.details?.base_score_before_honeypot_penalty ?? "n/a";
            const penalty = candidate.honeypot_penalty ?? candidate.details?.honeypot?.penalty ?? "n/a";
            const hpScore = candidate.honeypot_score ?? candidate.details?.honeypot?.score ?? 0;
            const rankLabel = candidate.sample_source === "dataset"
                ? `Dataset sample from row #${candidate.dataset_position || candidate.rank}`
                : candidate.rank > 100 ? `Dataset rank #${candidate.rank}` : `Top 100 rank #${candidate.rank}`;

            return `
                <article class="top100-honeypot-item">
                    <div class="top100-honeypot-header">
                        <div>
                            <span class="rank-badge rank-other">#${escapeHTML(candidate.rank)}</span>
                            <strong>${escapeHTML(candidate.name)}</strong>
                            <span class="top100-honeypot-id">${escapeHTML(candidate.candidate_id)}</span>
                        </div>
                        <div class="top100-honeypot-score">${escapeHTML(rankLabel)} | Score ${escapeHTML(candidate.score)}</div>
                    </div>
                    <div class="top100-honeypot-meta">
                        <span>${escapeHTML(candidate.current_title)}</span>
                        <span>${escapeHTML(candidate.location)}</span>
                        <span>${escapeHTML(Number(candidate.yoe || 0).toFixed(1))} YoE</span>
                        <span>red_flag_score ${escapeHTML(hpScore)}</span>
                        <span>Penalty ${escapeHTML(penalty)}</span>
                        <span>Base ${escapeHTML(baseScore)}</span>
                    </div>
                    <p class="top100-honeypot-reasoning">${escapeHTML(reasoning)}</p>
                    <div class="top100-honeypot-reasons">
                        ${reasons.map(reason => `<span>${escapeHTML(reason)}</span>`).join("")}
                    </div>
                </article>
            `;
        }).join("");
    }

    // --- Client side Search Filter ---
    searchBar.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) {
            renderTable(currentRankings);
            return;
        }
        
        const filtered = currentRankings.filter(cand => 
            cand.name.toLowerCase().includes(query) ||
            cand.candidate_id.toLowerCase().includes(query) ||
            cand.current_title.toLowerCase().includes(query) ||
            (cand.details && JSON.stringify(cand.details).toLowerCase().includes(query))
        );
        
        renderTable(filtered);
    });

    // --- Export XLSX Handler ---
    exportBtn.addEventListener("click", () => {
        const topN = parseInt(topNInput.value) || 100;
        
        exportBtn.classList.add("disabled");
        exportBtn.disabled = true;
        
        fetch("/api/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ top_n: topN })
        })
        .then(response => {
            if (response.status === 200) {
                return response.blob();
            }
            throw new Error("Failed to generate XLSX export");
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `submission_top_${topN}.xlsx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            
            exportBtn.classList.remove("disabled");
            exportBtn.disabled = false;
        })
        .catch(err => {
            console.error(err);
            alert("Error downloading XLSX file");
            exportBtn.classList.remove("disabled");
            exportBtn.disabled = false;
        });
    });

    // --- JD Skill Donut Rendering ---
    function renderSkillDonutGraph(visualizationData, candidateName) {
        const svg = document.getElementById("bipartite-graph");
        const container = document.getElementById("bipartite-graph-container");
        if (!svg || !container) return;

        const svgNS = "http://www.w3.org/2000/svg";
        const width = Math.max(container.clientWidth, 520);
        const height = 320;
        const centerX = Math.min(190, width * 0.38);
        const centerY = height / 2 + 12;
        const radius = 96;
        const strokeWidth = 32;

        const categories = visualizationData.categories || {};
        const rows = [
            { key: "must_have", label: "Must-have Skills", color: "#ff16dd" },
            { key: "nice_to_have", label: "Nice-to-have Skills", color: "#8b2bff" },
        ].map((item) => {
            const data = categories[item.key] || {};
            const matched = data.matched_count || 0;
            const total = data.total || 0;
            return {
                ...item,
                matched,
                total,
                pct: total ? Math.min(100, Math.round((matched / total) * 100)) : 0,
            };
        });
        const matchedTotal = rows.reduce((sum, row) => sum + row.matched, 0);
        const requiredTotal = rows.reduce((sum, row) => sum + row.total, 0);
        const overallPct = requiredTotal ? Math.round((matchedTotal / requiredTotal) * 100) : (visualizationData.overall_coverage || 0);
        const circumference = 2 * Math.PI * radius;
        const segmentTotal = Math.max(1, rows.reduce((sum, row) => sum + Math.max(row.matched, 0), 0));

        container.style.minHeight = `${height}px`;
        svg.setAttribute("width", width);
        svg.setAttribute("height", height);
        svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
        svg.innerHTML = "";

        const title = document.createElementNS(svgNS, "text");
        title.setAttribute("x", 22);
        title.setAttribute("y", 32);
        title.setAttribute("text-anchor", "start");
        title.setAttribute("font-size", "13px");
        title.setAttribute("font-weight", "700");
        title.setAttribute("fill", "#f7f8ff");
        title.textContent = "Skill Coverage Breakdown";
        svg.appendChild(title);

        const baseCircle = document.createElementNS(svgNS, "circle");
        baseCircle.setAttribute("cx", centerX);
        baseCircle.setAttribute("cy", centerY);
        baseCircle.setAttribute("r", radius);
        baseCircle.setAttribute("fill", "none");
        baseCircle.setAttribute("stroke", "rgba(255,255,255,0.08)");
        baseCircle.setAttribute("stroke-width", strokeWidth);
        svg.appendChild(baseCircle);

        const glowCircle = document.createElementNS(svgNS, "circle");
        glowCircle.setAttribute("cx", centerX);
        glowCircle.setAttribute("cy", centerY);
        glowCircle.setAttribute("r", radius);
        glowCircle.setAttribute("fill", "none");
        glowCircle.setAttribute("stroke", "rgba(255,22,221,0.18)");
        glowCircle.setAttribute("stroke-width", strokeWidth + 7);
        glowCircle.setAttribute("filter", "blur(5px)");
        svg.appendChild(glowCircle);

        let usedLength = 0;
        const gap = 14;
        rows.forEach((row) => {
            const share = Math.max(row.matched, 0) / segmentTotal;
            const segmentLength = Math.max(0, (circumference - gap * rows.length) * share);
            const segment = document.createElementNS(svgNS, "circle");
            segment.setAttribute("cx", centerX);
            segment.setAttribute("cy", centerY);
            segment.setAttribute("r", radius);
            segment.setAttribute("fill", "none");
            segment.setAttribute("stroke", row.color);
            segment.setAttribute("stroke-width", strokeWidth);
            segment.setAttribute("stroke-linecap", "butt");
            segment.setAttribute("stroke-dasharray", `${segmentLength} ${circumference - segmentLength}`);
            segment.setAttribute("stroke-dashoffset", `${-(usedLength + gap / 2)}`);
            segment.setAttribute("transform", `rotate(-72 ${centerX} ${centerY})`);
            segment.style.filter = `drop-shadow(0 0 9px ${row.color})`;
            svg.appendChild(segment);
            usedLength += segmentLength + gap;
        });

        const centerGroup = document.createElementNS(svgNS, "g");
        centerGroup.setAttribute("transform", `translate(${centerX}, ${centerY})`);
        svg.appendChild(centerGroup);

        const centerDisk = document.createElementNS(svgNS, "circle");
        centerDisk.setAttribute("r", radius - strokeWidth - 9);
        centerDisk.setAttribute("fill", "#121a30");
        centerDisk.setAttribute("stroke", "rgba(255,255,255,0.04)");
        centerGroup.appendChild(centerDisk);

        const centerCaption = document.createElementNS(svgNS, "text");
        centerCaption.setAttribute("text-anchor", "middle");
        centerCaption.setAttribute("dy", "-0.25em");
        centerCaption.setAttribute("font-size", "11px");
        centerCaption.setAttribute("fill", "#9ca6c6");
        centerCaption.textContent = "Skill Match";
        centerGroup.appendChild(centerCaption);

        const centerValue = document.createElementNS(svgNS, "text");
        centerValue.setAttribute("text-anchor", "middle");
        centerValue.setAttribute("dy", "1.15em");
        centerValue.setAttribute("font-size", "22px");
        centerValue.setAttribute("font-weight", "800");
        centerValue.setAttribute("fill", "#fff");
        centerValue.textContent = `${overallPct}%`;
        centerGroup.appendChild(centerValue);

        const legendX = Math.max(centerX + radius + 70, width * 0.66);
        rows.forEach((row, idx) => {
            const y = centerY + idx * 56 - 24;
            const dotOuter = document.createElementNS(svgNS, "circle");
            dotOuter.setAttribute("cx", legendX);
            dotOuter.setAttribute("cy", y);
            dotOuter.setAttribute("r", 11);
            dotOuter.setAttribute("fill", "transparent");
            dotOuter.setAttribute("stroke", row.color);
            dotOuter.setAttribute("stroke-width", "3");
            svg.appendChild(dotOuter);

            const pctText = document.createElementNS(svgNS, "text");
            pctText.setAttribute("x", legendX + 24);
            pctText.setAttribute("y", y - 3);
            pctText.setAttribute("font-size", "13px");
            pctText.setAttribute("font-weight", "800");
            pctText.setAttribute("fill", "#f7f8ff");
            pctText.textContent = `${row.pct}%`;
            svg.appendChild(pctText);

            const label = document.createElementNS(svgNS, "text");
            label.setAttribute("x", legendX + 24);
            label.setAttribute("y", y + 14);
            label.setAttribute("font-size", "11px");
            label.setAttribute("fill", "#9ca6c6");
            label.textContent = `${row.label} (${row.matched}/${row.total})`;
            svg.appendChild(label);
        });
    }

    // --- Details Modal Display Logic ---
    function showDetailsModal(candidate) {
        document.getElementById("modal-candidate-name").textContent = candidate.name;
        document.getElementById("modal-candidate-id").textContent = candidate.candidate_id;
        document.getElementById("modal-title").textContent = candidate.current_title;
        document.getElementById("modal-location").textContent = candidate.location;
        document.getElementById("modal-yoe").textContent = `${candidate.yoe.toFixed(1)} Years`;
        
        const details = candidate.details || {};
        const honeypotDetails = details.honeypot || {};
        const hpScore = honeypotDetails.score || 0;
        const hpReasons = candidate.honeypot_reasons || honeypotDetails.reasons || [];
        const riskLevel = candidate.is_honeypot || hpScore >= 2 ? "High" : hpScore === 1 ? "Medium" : "Low";
        const riskTitle = hpReasons.length > 0 ? hpReasons.join(" | ") : "No honeypot risk signals detected";
        const riskElement = document.getElementById("modal-honeypot-risk");
        const riskHeaderElement = document.getElementById("modal-honeypot-risk-header");
        if (riskElement) {
            riskElement.textContent = `${riskLevel} (${hpScore})`;
            riskElement.className = `risk-badge ${riskLevel.toLowerCase()}`;
            riskElement.title = riskTitle;
        }
        if (riskHeaderElement) {
            riskHeaderElement.textContent = `Honeypot Risk: ${riskLevel} (${hpScore})`;
            riskHeaderElement.className = `risk-badge risk-badge-large ${riskLevel.toLowerCase()}`;
            riskHeaderElement.title = riskTitle;
        }
        
        // Display score with full precision
        const scoreElement = document.getElementById("modal-overall-score");
        scoreElement.textContent = candidate.score;
        scoreElement.title = `Raw score: ${candidate.score} (Rank: ${candidate.rank})`;
        
        // Candidate summary metrics
        const graphSummary = document.getElementById("modal-graph-summary");
        graphSummary.innerHTML = "";
        
        const lastActive = details.behavioral?.days_since_active;
        const noticeDays = details.location?.notice_period_days;
        const openToWork = details.behavioral?.open_to_work;
        const locationFit = details.location?.geo_score;
        
        const summaryItems = [
            { label: "Rank", value: `#${candidate.rank}` },
            { label: "Experience", value: `${candidate.yoe.toFixed(1)} yrs` },
            { label: "Last active", value: lastActive !== undefined ? `${lastActive} days ago` : "Unknown" },
            { label: "Notice period", value: noticeDays !== undefined ? `${noticeDays} days` : "Unknown" },
            { label: "Location fit", value: locationFit !== undefined ? `${Math.round(locationFit * 100)}%` : "Unknown" },
            { label: "Open to work", value: openToWork ? "Yes" : "No" },
        ];
        
        summaryItems.forEach(item => {
            const card = document.createElement("div");
            card.className = "graph-metric-card";
            card.innerHTML = `<span>${item.label}</span><strong>${item.value}</strong>`;
            graphSummary.appendChild(card);
        });

        renderHoneypotXAI(candidate, hpScore, hpReasons, riskLevel);
        
        document.getElementById("modal-reasoning").textContent = candidate.reasoning;
        
        const chartContainer = document.getElementById("modal-graph-container");
        if (chartContainer) {
            chartContainer.innerHTML = "";
        } else {
            console.warn("Missing modal graph container; skipping component chart render.");
        }
        
        const componentScores = details.component_scores || {};
        const behaviorDetails = details.behavioral || {};
        const locationDetails = details.location || {};
        const skillDetails = details.skills || {};
        const titleDetails = details.title_career || {};
        
        const chartComponents = [
            {
                key: "fit_score",
                label: "Hiring Fit Score",
                value: Math.round(((componentScores.title_career || 0) + (componentScores.skills || 0) + (componentScores.experience || 0) + (componentScores.location || 0) + (componentScores.behavioral || 0)) / 5 * 100),
                detail: "Overall fit across career, skills, experience, location, and availability. Useful as a quick decision anchor."
            },
            {
                key: "skill_validation",
                label: "Skill Validation",
                value: Math.round(((skillDetails.must_have_groups ? Object.keys(skillDetails.must_have_groups).length : 0) / 4) * 100),
                detail: `Shows how many key skill groups are validated by both resume and career history. Higher means less risk of keyword stuffing.`
            },
            {
                key: "availability",
                label: "Availability Signals",
                value: Math.round((Math.min(1, (behaviorDetails.open_to_work ? 0.3 : 0) + (behaviorDetails.days_since_active !== undefined ? Math.max(0, 1 - behaviorDetails.days_since_active / 90) * 0.7 : 0))) * 100),
                detail: "Combines open-to-work status and recency of activity to surface candidate readiness for outreach."
            },
            {
                key: "logistics",
                label: "Logistics Risk",
                value: Math.round((locationDetails.geo_score || 0) * 100),
                detail: "Indicates geographic and relocation readiness based on preferred locations, notice period, and work mode alignment."
            }
        ];
        
        chartComponents.forEach(item => {
            const percent = Math.max(0, Math.min(item.value, 100));
            const severity = percent >= 75 ? "high" : percent >= 45 ? "medium" : "low";
            const barCard = document.createElement("div");
            barCard.className = "decision-bar-card";
            barCard.innerHTML = `
                <div class="decision-bar-header">
                    <div class="decision-bar-title">${item.label}</div>
                    <div class="decision-bar-value">${percent}%</div>
                </div>
                <div class="decision-progress-wrap">
                    <div class="decision-progress">
                        <div class="decision-progress-fill ${severity}" style="width: ${percent}%;"></div>
                    </div>
                </div>
                <div class="decision-bar-explanation">
                    ${item.detail}
                </div>
            `;
            barCard.addEventListener("click", () => barCard.classList.toggle("open"));
            if (chartContainer) {
                chartContainer.appendChild(barCard);
            }
        });

        const decisionGrid = document.getElementById("modal-decision-grid");
        decisionGrid.innerHTML = "";

        const validatedMustHaves = skillDetails.must_have_groups ? Object.entries(skillDetails.must_have_groups).filter(([_, status]) => status === "validated").length : 0;
        const totalMustHaves = skillDetails.must_have_groups ? Object.keys(skillDetails.must_have_groups).length : 0;
        const responseRate = behaviorDetails.recruiter_response_rate || 0;
        const notice = locationDetails.notice_period_days !== undefined ? locationDetails.notice_period_days : "n/a";
        const workMode = locationDetails.preferred_work_mode || "unknown";
        const openWorkText = behaviorDetails.open_to_work ? "Yes" : "No";

        const decisionItems = [
            {
                title: "Career vs Title Fit",
                value: `${titleDetails.current_tier || "unknown"}`,
                note: `Current title tier: ${titleDetails.current_tier || "unknown"}, best historical tier: ${titleDetails.best_historical_tier || "unknown"}. Title hopping flag: ${titleDetails.title_hopper_flag ? "Yes" : "No"}.`,
            },
            {
                title: "Skill Credibility",
                value: `${validatedMustHaves}/${totalMustHaves} key groups validated`,
                note: `Skill trust: ${skillDetails.avg_trust || 0}. Nice-to-have groups matched: ${skillDetails.nice_to_have_groups ? Object.keys(skillDetails.nice_to_have_groups).length : 0}.`,
            },
            {
                title: "Availability Readiness",
                value: `${openWorkText}, ${behaviorDetails.days_since_active || "n/a"}d inactive`,
                note: `Response rate: ${Math.round(responseRate * 100)}%. Avg response time: ${behaviorDetails.avg_response_time_hours || "n/a"} hrs.`,
            },
            {
                title: "Logistics Risk",
                value: `${notice} day notice`,
                note: `Location match: ${Math.round((locationDetails.geo_score || 0) * 100)}%. Work mode: ${workMode}. Relocation willing: ${locationDetails.willing_to_relocate ? "Yes" : "No"}.`,
            }
        ];

        decisionItems.forEach(item => {
            const tile = document.createElement("div");
            tile.className = "decision-bar-card";
            tile.innerHTML = `
                <div class="decision-bar-header">
                    <div class="decision-bar-title">${item.title}</div>
                    <div class="decision-bar-value">${item.value}</div>
                </div>
                <div class="decision-bar-explanation">${item.note}</div>
            `;
            tile.addEventListener("click", () => tile.classList.toggle("open"));
            decisionGrid.appendChild(tile);
        });

        // Add a recruiter-friendly score explanation.
        const compositeScore = details.composite_before_modifier || 0;
        const modifier = details.modifier !== undefined ? details.modifier : 1.0;
        const baseFitPercent = Math.round(compositeScore * 100);
        const finalFitPercent = Math.round(parseFloat(candidate.score) * 100);
        const engagementPercent = Math.round(Math.abs(modifier - 1) * 100);
        const engagementLabel = modifier >= 1 ? "added a small boost" : "slightly reduced the score";
        const engagementTone = modifier >= 1 ? "Positive engagement signals helped this profile." : "Engagement signals made this profile a little less ready.";
        
        let scoreNoteHtml = `
            <div class="score-explainer">
                <div class="score-explainer-title">How to read this score</div>
                <div class="score-step">
                    <span class="score-step-number">1</span>
                    <div>
                        <strong>Base role fit: ${baseFitPercent}%</strong>
                        <small>Built from the candidate's title, skills, experience, location fit, and availability signals.</small>
                    </div>
                </div>
                <div class="score-step">
                    <span class="score-step-number">2</span>
                    <div>
                        <strong>Engagement adjustment: ${engagementLabel}${engagementPercent ? ` of about ${engagementPercent}%` : ""}</strong>
                        <small>${engagementTone}</small>
                    </div>
                </div>
                <div class="score-step final">
                    <span class="score-step-number">3</span>
                    <div>
                        <strong>Final match score: ${finalFitPercent}%</strong>
                        <small>The exact ranking value is ${candidate.score}. Higher means a stronger overall match for this role.</small>
                    </div>
                </div>
            </div>
        `;
        
        if (currentRankings.length > 1) {
            const nextCandidate = currentRankings[candidate.rank];
            const prevCandidate = currentRankings[candidate.rank - 2];
            
            if (prevCandidate) {
                const scoreDiff = parseFloat(prevCandidate.score) - parseFloat(candidate.score);
                scoreNoteHtml += `<div class="score-rank-note behind">
                    This candidate is ${Math.abs(scoreDiff * 100).toFixed(2)} percentage points behind rank ${candidate.rank - 1}.
                </div>`;
            }
            if (nextCandidate) {
                const scoreDiff = parseFloat(candidate.score) - parseFloat(nextCandidate.score);
                scoreNoteHtml += `<div class="score-rank-note ahead">
                    This candidate is ${Math.abs(scoreDiff * 100).toFixed(2)} percentage points ahead of rank ${candidate.rank + 1}.
                </div>`;
            }
        }
        
        scoreElement.innerHTML += scoreNoteHtml;
        
        // Render donut graph for semantic JD skill coverage
        const bipartiteContainer = document.getElementById("bipartite-graph-container");
        if (bipartiteContainer) {
            // Show loading
            const svg = document.getElementById("bipartite-graph");
            if (svg) {
                try {
                    const svgNS = 'http://www.w3.org/2000/svg';
                    svg.innerHTML = '';
                    const textEl = document.createElementNS(svgNS, 'text');
                    textEl.setAttribute('x', '50%');
                    textEl.setAttribute('y', '50%');
                    textEl.setAttribute('text-anchor', 'middle');
                    textEl.setAttribute('dy', '0.3em');
                    textEl.setAttribute('fill', '#888');
                    textEl.textContent = 'Loading skill mapping...';
                    svg.appendChild(textEl);
                } catch (e) {
                    console.warn('Could not render loading text for bipartite graph', e);
                }
            }
            
            // Fetch visualization data
            fetch("/api/match-skills-visualization", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ candidate_id: candidate.candidate_id })
            })
            .then(res => res.json())
            .then(vizData => {
                if (vizData.error) {
                    console.error("Visualization error:", vizData.error);
                    return;
                }
                renderSkillDonutGraph(vizData, candidate.name);
            })
            .catch(err => {
                console.error("Error fetching visualization data:", err);
            });
        }
        
        // Show modal
        detailsModal.style.display = "flex";
    }

    function renderHoneypotXAI(candidate, hpScore, hpReasons, riskLevel) {
        const section = document.getElementById("modal-honeypot-xai-section");
        const content = document.getElementById("modal-honeypot-xai");
        if (!section || !content) return;

        const isRisk = candidate.is_honeypot || hpScore >= 2;
        if (!isRisk) {
            section.style.display = "none";
            content.innerHTML = "";
            return;
        }

        const hp = candidate.details?.honeypot || {};
        const penalty = hp.penalty !== undefined ? hp.penalty : "n/a";
        const baseScore = candidate.details?.base_score_before_honeypot_penalty;
        const reasons = hpReasons.length > 0 ? hpReasons : ["Honeypot score exceeded the configured threshold."];

        section.style.display = "block";
        content.innerHTML = `
            <div class="honeypot-xai-summary">
                <div>
                    <span>Risk Level</span>
                    <strong>${riskLevel}</strong>
                </div>
                <div>
                    <span>Honeypot Score</span>
                    <strong>${hpScore}</strong>
                </div>
                <div>
                    <span>Penalty Weight</span>
                    <strong>${penalty}</strong>
                </div>
                <div>
                    <span>Base Score</span>
                    <strong>${baseScore !== undefined ? baseScore : "n/a"}</strong>
                </div>
            </div>
            <div class="honeypot-xai-reasons">
                ${reasons.map(reason => `
                    <div class="honeypot-xai-reason">
                        <span class="honeypot-xai-dot"></span>
                        <p>${reason}</p>
                    </div>
                `).join("")}
            </div>
            <p class="honeypot-xai-note">
                This candidate remains ranked, but the final score was reduced by the honeypot penalty so recruiters can inspect the explanation instead of losing the record silently.
            </p>
        `;
    }

    // --- Close Modal Event Handlers ---
    modalClose.addEventListener("click", () => {
        detailsModal.style.display = "none";
    });

    window.addEventListener("click", (e) => {
        if (e.target === detailsModal) {
            detailsModal.style.display = "none";
        }
    });

    function renderValidationReport(report) {
        if (!report || report.error) return;

        const sumBody = document.getElementById("custom-summary-table-body");
        const detailStats = document.getElementById("custom-detailed-stats");

        if (sumBody && report.reference && report.top) {
            if (report.reference_has_data === false) {
                sumBody.innerHTML = `
                    <tr>
                        <td colspan="5" style="padding: 1rem 0.5rem; color: #fbbf24;">
                            Reference dataset statistics are unavailable. Check that ProjectObjective/sample_candidates.json exists and contains candidate records.
                        </td>
                    </tr>
                `;
                if (detailStats) {
                    detailStats.innerHTML = `<div class="validation-source-note">Reference source checked: ${escapeHTML(report.reference_source || "unknown")}</div>`;
                }
                return;
            }

            const s = report.reference;
            const t = report.top;
            const rankedCount = report.ranked_count || t.yoe.count || 0;
            const referenceNote = `
                <div class="validation-source-note">
                    <strong>Reference:</strong> ${escapeHTML(report.reference_file || "ProjectObjective/sample_candidates.json")} (${report.reference_count || 0} candidates)
                    <strong>| Ranked:</strong> ${escapeHTML(report.ranked_basis || "Ranked Top 100 candidates")} compared: ${rankedCount}
                </div>
            `;

            const formatSigned = (value, suffix = "") => `${value >= 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
            const pctDiff = (model, reference) => reference ? ((model - reference) / reference) * 100 : 0;
            const alignment = (percent) => {
                const abs = Math.abs(percent);
                if (abs <= 10) return { label: "Similar" };
                if (abs <= 25) return { label: "Moderate" };
                return { label: "Large Gap" };
            };
            const rowHtml = (label, refValue, modelValue, suffix, percentMultiplier = 1) => {
                const diff = modelValue - refValue;
                const percent = pctDiff(modelValue, refValue);
                const status = alignment(percent);
                const refDisplay = `${(refValue * percentMultiplier).toFixed(2)}${suffix}`;
                const modelDisplay = `${(modelValue * percentMultiplier).toFixed(2)}${suffix}`;
                const diffDisplay = `${formatSigned(diff * percentMultiplier, suffix)} (${formatSigned(percent, "%")})`;
                return `
                    <tr>
                        <td>${label}</td>
                        <td>${refDisplay}</td>
                        <td>${modelDisplay}</td>
                        <td class="${diff >= 0 ? "positive-diff" : "negative-diff"}">${diffDisplay}</td>
                        <td>
                            <span class="alignment-pill">${status.label}</span>
                        </td>
                    </tr>
                `;
            };
            const metricCard = (accentClass, title, refText, modelText, note) => `
                <article class="distribution-info-card ${accentClass}">
                    <h4>${title}</h4>
                    <ul>
                        <li><strong>Reference Dataset:</strong> ${refText}</li>
                        <li><strong>Model Ranked:</strong> ${modelText}</li>
                    </ul>
                    <p>${note}</p>
                </article>
            `;
            const pointsToPolyline = (values, maxValue, width = 300, height = 190) => {
                const safeMax = Math.max(maxValue, 1);
                return values.map((value, idx) => {
                    const x = 28 + idx * ((width - 52) / Math.max(values.length - 1, 1));
                    const y = height - 28 - ((value / safeMax) * (height - 58));
                    return `${x.toFixed(1)},${y.toFixed(1)}`;
                }).join(" ");
            };
            const lineChart = (title, className, refStats, modelStats, suffix, multiplier = 1) => {
                const labels = ["Min", "Median", "Mean", "Max"];
                const refValues = [refStats.min, refStats.median, refStats.mean, refStats.max].map(v => v * multiplier);
                const modelValues = [modelStats.min, modelStats.median, modelStats.mean, modelStats.max].map(v => v * multiplier);
                const maxValue = Math.max(...refValues, ...modelValues, 1);
                return `
                    <article class="distribution-chart ${className}">
                        <h4>${title}</h4>
                        <svg viewBox="0 0 320 220" role="img" aria-label="${title}">
                            <g class="chart-grid">
                                ${[0, 1, 2, 3, 4].map(i => `<line x1="28" y1="${32 + i * 38}" x2="300" y2="${32 + i * 38}"></line>`).join("")}
                            </g>
                            <polyline class="reference-line" points="${pointsToPolyline(refValues, maxValue)}"></polyline>
                            <polyline class="model-line" points="${pointsToPolyline(modelValues, maxValue)}"></polyline>
                            ${refValues.map((value, idx) => {
                                const x = 28 + idx * ((300 - 52) / 3);
                                const y = 190 - ((value / maxValue) * 132);
                                return `<circle class="reference-point" cx="${x}" cy="${y}" r="5"><title>Reference ${labels[idx]}: ${value.toFixed(2)}${suffix}</title></circle>`;
                            }).join("")}
                            ${modelValues.map((value, idx) => {
                                const x = 28 + idx * ((300 - 52) / 3);
                                const y = 190 - ((value / maxValue) * 132);
                                return `<circle class="model-point" cx="${x}" cy="${y}" r="5"><title>Model ${labels[idx]}: ${value.toFixed(2)}${suffix}</title></circle>`;
                            }).join("")}
                            ${labels.map((label, idx) => `<text x="${28 + idx * ((300 - 52) / 3)}" y="210">${label}</text>`).join("")}
                        </svg>
                    </article>
                `;
            };
            const barChart = (title, refStats, modelStats) => {
                const labels = ["Min", "Median", "Mean", "Max"];
                const refValues = [refStats.min, refStats.median, refStats.mean, refStats.max];
                const modelValues = [modelStats.min, modelStats.median, modelStats.mean, modelStats.max];
                const maxValue = Math.max(...refValues, ...modelValues, 1);
                return `
                    <article class="distribution-chart skills-chart">
                        <h4>${title}</h4>
                        <div class="chart-legend-inline"><span class="ref-key"></span>Reference <span class="model-key"></span>Model Ranked</div>
                        <svg viewBox="0 0 320 220" role="img" aria-label="${title}">
                            <g class="chart-grid">
                                ${[0, 1, 2, 3, 4].map(i => `<line x1="28" y1="${32 + i * 38}" x2="300" y2="${32 + i * 38}"></line>`).join("")}
                            </g>
                            ${labels.map((label, idx) => {
                                const groupX = 44 + idx * 64;
                                const refHeight = (refValues[idx] / maxValue) * 140;
                                const modelHeight = (modelValues[idx] / maxValue) * 140;
                                return `
                                    <rect class="reference-bar" x="${groupX}" y="${188 - refHeight}" width="22" height="${refHeight}"><title>Reference ${label}: ${refValues[idx].toFixed(2)} skills</title></rect>
                                    <rect class="model-bar" x="${groupX + 25}" y="${188 - modelHeight}" width="22" height="${modelHeight}"><title>Model ${label}: ${modelValues[idx].toFixed(2)} skills</title></rect>
                                    <text x="${groupX + 22}" y="210">${label}</text>
                                `;
                            }).join("")}
                        </svg>
                    </article>
                `;
            };

            sumBody.innerHTML = `
                ${rowHtml("Average Years of Experience (YoE)", s.yoe.mean, t.yoe.mean, " years")}
                ${rowHtml("Average Number of Skills", s.skills.mean, t.skills.mean, " skills")}
                ${rowHtml("Average Recruiter Response Rate (RRR)", s.rrr.mean, t.rrr.mean, "%", 100)}
            `;

            detailStats.innerHTML = referenceNote + `
                <div class="distribution-info-grid">
                    ${metricCard("cyan-accent", "1. Years of Experience (YoE)", `Median = ${s.yoe.median.toFixed(2)} years, Range = [${s.yoe.min.toFixed(1)}, ${s.yoe.max.toFixed(1)}] years`, `Median = ${t.yoe.median.toFixed(2)} years, Range = [${t.yoe.min.toFixed(1)}, ${t.yoe.max.toFixed(1)}] years`, "Compares experience distribution in sample_candidates.json against the current ranked output")}
                    ${metricCard("purple-accent", "2. Number of Skills", `Median = ${s.skills.median.toFixed(1)} skills, Range = [${s.skills.min}, ${s.skills.max}] skills`, `Median = ${t.skills.median.toFixed(1)} skills, Range = [${t.skills.min}, ${t.skills.max}] skills`, "Compares average and median skill-set size between the reference dataset and ranked candidates")}
                    ${metricCard("pink-accent", "3. Recruiter Response Rate (RRR)", `Median = ${(s.rrr.median * 100).toFixed(1)}%, Range = [${(s.rrr.min * 100).toFixed(1)}%, ${(s.rrr.max * 100).toFixed(1)}%]`, `Median = ${(t.rrr.median * 100).toFixed(1)}%, Range = [${(t.rrr.min * 100).toFixed(1)}%, ${(t.rrr.max * 100).toFixed(1)}%]`, "Compares recruiter response rate quality between the reference dataset and ranked candidates")}
                </div>
                <div class="distribution-chart-grid">
                    ${lineChart("Experience Distribution", "experience-chart", s.yoe, t.yoe, " years")}
                    ${barChart("Skills Distribution", s.skills, t.skills)}
                    ${lineChart("RRR Distribution", "rrr-chart", s.rrr, t.rrr, "%", 100)}
                </div>
            `;
        }
    }
});
