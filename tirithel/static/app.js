/**
 * Tirithel - Frontend Application
 */

const API = '/api/v1';

// --- Tab Navigation ---
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');

        // Load data for the active tab
        const tabName = tab.dataset.tab;
        if (tabName === 'sessions') loadSessions();
        if (tabName === 'knowledge') loadKnowledge();
        if (tabName === 'profiles') loadProfiles();
    });
});

// --- Utility ---
async function apiCall(url, options = {}) {
    const resp = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || 'API error');
    }
    if (resp.status === 204) return null;
    return resp.json();
}

function statusBadge(status) {
    const cls = {
        recording: 'badge-recording',
        processing: 'badge-processing',
        completed: 'badge-completed',
        failed: 'badge-recording',
    }[status] || '';
    return `<span class="badge ${cls}">${status}</span>`;
}

// --- Profiles (shared dropdown loader) ---
async function loadProfileDropdowns() {
    try {
        const profiles = await apiCall(`${API}/profiles`);
        ['guidance-profile', 'session-profile'].forEach(id => {
            const sel = document.getElementById(id);
            if (!sel) return;
            const current = sel.value;
            sel.innerHTML = `<option value="">${id.includes('guidance') ? 'All software' : 'No profile'}</option>`;
            profiles.forEach(p => {
                sel.innerHTML += `<option value="${p.id}">${p.name}</option>`;
            });
            sel.value = current;
        });
    } catch (e) {
        console.error('Failed to load profiles:', e);
    }
}

// --- Guidance Tab ---
let currentQueryId = null;

document.getElementById('guidance-submit').addEventListener('click', async () => {
    const query = document.getElementById('guidance-query').value.trim();
    if (!query) return;

    const profileId = document.getElementById('guidance-profile').value || undefined;
    const btn = document.getElementById('guidance-submit');
    btn.textContent = 'Thinking...';
    btn.disabled = true;

    try {
        const result = await apiCall(`${API}/guidance/query`, {
            method: 'POST',
            body: JSON.stringify({ query, profile_id: profileId }),
        });

        currentQueryId = result.query_id;
        document.getElementById('guidance-text').textContent = result.guidance_text;
        const confPct = Math.round(result.confidence * 100);
        const confEl = document.getElementById('guidance-confidence');
        confEl.textContent = `${confPct}% confident`;
        confEl.className = `badge ${confPct > 70 ? 'badge-completed' : confPct > 40 ? 'badge-processing' : 'badge-recording'}`;
        document.getElementById('guidance-result').classList.remove('hidden');

        // Reset stars
        document.querySelectorAll('#star-rating .star').forEach(s => s.classList.remove('active'));
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        btn.textContent = 'Get Instructions';
        btn.disabled = false;
    }
});

// Star rating
document.querySelectorAll('#star-rating .star').forEach(star => {
    star.addEventListener('click', async () => {
        const rating = parseInt(star.dataset.rating);
        document.querySelectorAll('#star-rating .star').forEach(s => {
            s.classList.toggle('active', parseInt(s.dataset.rating) <= rating);
        });
        if (currentQueryId) {
            try {
                await apiCall(`${API}/guidance/${currentQueryId}/feedback`, {
                    method: 'POST',
                    body: JSON.stringify({ rating }),
                });
            } catch (e) {
                console.error('Failed to submit feedback:', e);
            }
        }
    });
});

// --- Sessions Tab ---
let currentSessionId = null;

document.getElementById('new-session-btn').addEventListener('click', () => {
    document.getElementById('new-session-form').classList.toggle('hidden');
});

document.getElementById('create-session-btn').addEventListener('click', async () => {
    const title = document.getElementById('session-title').value.trim();
    const profileId = document.getElementById('session-profile').value || undefined;

    try {
        const session = await apiCall(`${API}/sessions`, {
            method: 'POST',
            body: JSON.stringify({ title: title || null, profile_id: profileId }),
        });
        document.getElementById('new-session-form').classList.add('hidden');
        document.getElementById('session-title').value = '';
        loadSessions();
        showSessionDetail(session.id);
    } catch (e) {
        alert('Error: ' + e.message);
    }
});

async function loadSessions() {
    try {
        const sessions = await apiCall(`${API}/sessions`);
        const list = document.getElementById('sessions-list');
        if (!sessions.length) {
            list.innerHTML = '<p style="padding: 1rem; color: var(--text-muted)">No sessions yet. Start a new one!</p>';
            return;
        }
        list.innerHTML = sessions.map(s => `
            <div class="list-item" onclick="showSessionDetail('${s.id}')">
                <div class="list-item-content">
                    <h4>${s.title || 'Untitled Session'}</h4>
                    <p>${new Date(s.started_at).toLocaleString()}</p>
                </div>
                ${statusBadge(s.status)}
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load sessions:', e);
    }
}

async function showSessionDetail(sessionId) {
    currentSessionId = sessionId;
    try {
        const s = await apiCall(`${API}/sessions/${sessionId}`);
        document.getElementById('session-detail-title').textContent = s.title || 'Untitled Session';
        document.getElementById('session-detail-status').innerHTML = statusBadge(s.status).replace(/<[^>]*>/g, '') ;
        document.getElementById('session-detail-status').className = `badge ${s.status === 'completed' ? 'badge-completed' : s.status === 'recording' ? 'badge-recording' : 'badge-processing'}`;
        document.getElementById('session-detail-status').textContent = s.status;

        document.getElementById('session-stats').innerHTML = `
            <div class="stat-box"><div class="stat-value">${s.screenshot_count}</div><div class="stat-label">Screenshots</div></div>
            <div class="stat-box"><div class="stat-value">${s.conversation_segment_count}</div><div class="stat-label">Segments</div></div>
            <div class="stat-box"><div class="stat-value">${s.ui_action_count}</div><div class="stat-label">UI Actions</div></div>
            <div class="stat-box"><div class="stat-value">${s.navigation_path_count}</div><div class="stat-label">Paths Learned</div></div>
        `;

        const isRecording = s.status === 'recording';
        document.querySelector('.session-actions').style.display = isRecording ? 'block' : 'none';
        document.getElementById('session-detail').classList.remove('hidden');
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// Upload screenshot
document.getElementById('upload-screenshot-btn').addEventListener('click', async () => {
    const fileInput = document.getElementById('screenshot-upload');
    if (!fileInput.files.length || !currentSessionId) return;

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
        await fetch(`${API}/sessions/${currentSessionId}/screenshots`, {
            method: 'POST',
            body: formData,
        });
        fileInput.value = '';
        showSessionDetail(currentSessionId);
    } catch (e) {
        alert('Upload failed: ' + e.message);
    }
});

// Upload transcript
document.getElementById('upload-transcript-btn').addEventListener('click', async () => {
    const text = document.getElementById('transcript-input').value.trim();
    if (!text || !currentSessionId) return;

    try {
        await apiCall(`${API}/sessions/${currentSessionId}/transcript`, {
            method: 'POST',
            body: JSON.stringify({ transcript: text, use_llm: true }),
        });
        document.getElementById('transcript-input').value = '';
        showSessionDetail(currentSessionId);
    } catch (e) {
        alert('Error: ' + e.message);
    }
});

// Complete session
document.getElementById('complete-session-btn').addEventListener('click', async () => {
    if (!currentSessionId) return;
    const btn = document.getElementById('complete-session-btn');
    btn.textContent = 'Processing...';
    btn.disabled = true;

    try {
        await apiCall(`${API}/sessions/${currentSessionId}/complete`, { method: 'POST' });
        showSessionDetail(currentSessionId);
        loadSessions();
    } catch (e) {
        alert('Error: ' + e.message);
    } finally {
        btn.textContent = 'Complete & Process Session';
        btn.disabled = false;
    }
});

// --- Knowledge Tab ---
async function loadKnowledge() {
    try {
        const [paths, stats] = await Promise.all([
            apiCall(`${API}/knowledge/paths`),
            apiCall(`${API}/knowledge/stats`),
        ]);

        document.getElementById('knowledge-stats').innerHTML = `
            <span>${stats.total_paths} paths</span>
            <span>${stats.verified_paths} verified</span>
            <span>Avg confidence: ${stats.average_confidence}</span>
            <span>${stats.total_queries} queries served</span>
        `;

        const list = document.getElementById('knowledge-list');
        if (!paths.length) {
            list.innerHTML = '<p style="padding: 1rem; color: var(--text-muted)">No navigation paths learned yet. Record some support sessions!</p>';
            return;
        }
        list.innerHTML = paths.map(p => `
            <div class="list-item">
                <div class="list-item-content">
                    <h4>${p.issue_summary}</h4>
                    <p>${p.steps.length} steps &bull; ${p.entry_point || '?'} &rarr; ${p.destination || '?'} &bull; Used ${p.use_count}x ${p.is_verified ? '&bull; Verified' : ''}</p>
                </div>
                <span class="badge ${p.confidence_score > 0.8 ? 'badge-completed' : 'badge-processing'}">${Math.round((p.confidence_score || 0) * 100)}%</span>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load knowledge:', e);
    }
}

document.getElementById('knowledge-search-btn').addEventListener('click', async () => {
    const query = document.getElementById('knowledge-search').value.trim();
    if (!query) { loadKnowledge(); return; }

    try {
        const results = await apiCall(`${API}/knowledge/search`, {
            method: 'POST',
            body: JSON.stringify({ query, top_k: 10 }),
        });

        const list = document.getElementById('knowledge-list');
        if (!results.length) {
            list.innerHTML = '<p style="padding: 1rem; color: var(--text-muted)">No matching paths found.</p>';
            return;
        }
        list.innerHTML = results.map(r => `
            <div class="list-item">
                <div class="list-item-content">
                    <h4>${r.path.issue_summary}</h4>
                    <p>Similarity: ${Math.round(r.similarity_score * 100)}% &bull; ${r.path.steps.length} steps</p>
                </div>
            </div>
        `).join('');
    } catch (e) {
        alert('Search failed: ' + e.message);
    }
});

// --- Profiles Tab ---
document.getElementById('new-profile-btn').addEventListener('click', () => {
    document.getElementById('new-profile-form').classList.toggle('hidden');
});

document.getElementById('create-profile-btn').addEventListener('click', async () => {
    const name = document.getElementById('profile-name').value.trim();
    if (!name) return;
    const desc = document.getElementById('profile-description').value.trim();

    try {
        await apiCall(`${API}/profiles`, {
            method: 'POST',
            body: JSON.stringify({ name, description: desc }),
        });
        document.getElementById('new-profile-form').classList.add('hidden');
        document.getElementById('profile-name').value = '';
        document.getElementById('profile-description').value = '';
        loadProfiles();
        loadProfileDropdowns();
    } catch (e) {
        alert('Error: ' + e.message);
    }
});

async function loadProfiles() {
    try {
        const profiles = await apiCall(`${API}/profiles`);
        const list = document.getElementById('profiles-list');
        if (!profiles.length) {
            list.innerHTML = '<p style="padding: 1rem; color: var(--text-muted)">No software profiles yet. Create one to start learning!</p>';
            return;
        }
        list.innerHTML = profiles.map(p => `
            <div class="list-item">
                <div class="list-item-content">
                    <h4>${p.name}</h4>
                    <p>${p.description || 'No description'}</p>
                </div>
                <button class="btn" onclick="event.stopPropagation(); deleteProfile('${p.id}')">Delete</button>
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load profiles:', e);
    }
}

async function deleteProfile(id) {
    if (!confirm('Delete this profile?')) return;
    try {
        await apiCall(`${API}/profiles/${id}`, { method: 'DELETE' });
        loadProfiles();
        loadProfileDropdowns();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// --- Init ---
loadProfileDropdowns();
