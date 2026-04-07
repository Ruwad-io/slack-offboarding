/**
 * OffBoarding — Frontend JS
 */

// ---- Status banner ----

function showStatus(text, detail, progress) {
    const banner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');
    const statusDetail = document.getElementById('status-detail');
    const progressFill = document.getElementById('progress-fill');

    banner.classList.remove('hidden');
    statusText.textContent = text;
    statusDetail.textContent = detail || '';
    progressFill.style.width = (progress || 0) + '%';
}

function hideStatus() {
    document.getElementById('status-banner').classList.add('hidden');
}

// ---- Select all ----

let allSelected = false;

function toggleSelectAll() {
    allSelected = !allSelected;
    document.querySelectorAll('.dm-checkbox').forEach(cb => {
        cb.checked = allSelected;
    });
    document.getElementById('btn-select-all').textContent =
        allSelected ? 'Deselect All' : 'Select All';
}

function getSelectedChannels() {
    return Array.from(document.querySelectorAll('.dm-checkbox:checked'))
        .map(cb => cb.value);
}

// ---- Preview ----

async function previewMessages(channelId) {
    const modal = document.getElementById('preview-modal');
    const body = document.getElementById('preview-body');

    body.innerHTML = '<p>Loading...</p>';
    modal.classList.remove('hidden');

    try {
        const resp = await fetch(`/api/preview/${channelId}`);
        const data = await resp.json();

        if (data.preview.length === 0) {
            body.innerHTML = '<p>No messages found from you in this conversation.</p>';
            return;
        }

        let html = `<p><strong>${data.total}</strong> messages will be deleted. Showing first ${data.preview.length}:</p>`;
        data.preview.forEach(msg => {
            const date = new Date(parseFloat(msg.ts) * 1000).toLocaleString();
            html += `<div class="message"><small>${date}</small><br>${escapeHtml(msg.text)}</div>`;
        });
        body.innerHTML = html;

    } catch (err) {
        body.innerHTML = `<p>Error loading preview: ${err.message}</p>`;
    }
}

function closePreview() {
    document.getElementById('preview-modal').classList.add('hidden');
}

// ---- Single channel delete ----

async function deleteChannel(channelId, dryRun) {
    const action = dryRun ? 'simulate deletion of' : 'permanently delete all your messages in';
    if (!dryRun && !confirm(`Are you sure you want to ${action} this conversation? This cannot be undone.`)) {
        return;
    }

    showStatus(
        dryRun ? 'Simulating...' : 'Deleting messages...',
        'This may take a while depending on the number of messages.',
        0
    );

    try {
        const resp = await fetch(`/api/delete/${channelId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: dryRun }),
        });
        const stats = await resp.json();

        showStatus(
            dryRun ? 'Simulation complete' : 'Deletion complete',
            `${stats.messages_deleted} messages ${dryRun ? 'would be' : ''} deleted, ${stats.messages_failed} failed`,
            100
        );

        const countEl = document.getElementById(`count-${channelId}`);
        if (countEl && !dryRun) {
            countEl.textContent = '0 messages';
        }

        setTimeout(hideStatus, 5000);

    } catch (err) {
        showStatus('Error', err.message, 0);
    }
}

async function deleteSelected(dryRun) {
    const channels = getSelectedChannels();
    if (channels.length === 0) {
        alert('Please select at least one conversation.');
        return;
    }

    const action = dryRun ? 'simulate deletion for' : 'permanently delete your messages in';
    if (!dryRun && !confirm(`Are you sure you want to ${action} ${channels.length} conversation(s)? This cannot be undone.`)) {
        return;
    }

    for (let i = 0; i < channels.length; i++) {
        showStatus(
            dryRun ? 'Simulating...' : 'Deleting...',
            `Processing conversation ${i + 1} of ${channels.length}`,
            Math.round((i / channels.length) * 100)
        );
        await deleteChannelSilent(channels[i], dryRun);
    }

    showStatus(
        dryRun ? 'Simulation complete' : 'All done!',
        `Processed ${channels.length} conversations`,
        100
    );
    setTimeout(hideStatus, 5000);
}

async function deleteChannelSilent(channelId, dryRun) {
    try {
        await fetch(`/api/delete/${channelId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: dryRun }),
        });
    } catch (err) {
        console.error(`Failed to process ${channelId}:`, err);
    }
}

// ---- Nuke (background job + SSE) ----

let activeEventSource = null;

async function startNuke() {
    if (!confirm('This will DELETE ALL your messages in ALL conversations (DMs, group DMs, channels, threads). This CANNOT be undone.\n\nThe process runs in the background — you can close this page and come back later.')) {
        return;
    }

    showNukeProgress({
        status: 'starting',
        conversations_total: 0,
        conversations_done: 0,
        messages_deleted: 0,
        messages_failed: 0,
        current_conversation: '',
    });

    try {
        const resp = await fetch('/api/nuke', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });

        if (resp.status === 409) {
            const data = await resp.json();
            // Already running, reconnect to existing job
            connectSSE(data.job_id);
            return;
        }

        const data = await resp.json();
        connectSSE(data.job_id);

    } catch (err) {
        showStatus('Error', err.message, 0);
    }
}

function connectSSE(jobId) {
    if (activeEventSource) {
        activeEventSource.close();
    }

    const nukePanel = document.getElementById('nuke-progress');
    nukePanel.classList.remove('hidden');

    activeEventSource = new EventSource(`/api/job/${jobId}/stream`);

    activeEventSource.onmessage = (event) => {
        const job = JSON.parse(event.data);
        showNukeProgress(job);

        if (job.status === 'completed' || job.status === 'failed') {
            activeEventSource.close();
            activeEventSource = null;
        }
    };

    activeEventSource.onerror = () => {
        // Reconnect after a short delay
        activeEventSource.close();
        activeEventSource = null;
        setTimeout(() => {
            fetch(`/api/job/${jobId}`)
                .then(r => r.json())
                .then(job => {
                    if (job.status === 'running' || job.status === 'pending') {
                        connectSSE(jobId);
                    } else {
                        showNukeProgress(job);
                    }
                })
                .catch(() => {});
        }, 3000);
    };
}

function showNukeProgress(job) {
    const panel = document.getElementById('nuke-progress');
    const statusEl = document.getElementById('nuke-status');
    const convEl = document.getElementById('nuke-conversations');
    const msgsEl = document.getElementById('nuke-messages');
    const currentEl = document.getElementById('nuke-current');
    const progressEl = document.getElementById('nuke-progress-fill');
    const failedEl = document.getElementById('nuke-failed');

    panel.classList.remove('hidden');

    // Status text
    const statusMap = {
        'pending': 'Starting...',
        'starting': 'Starting...',
        'running': 'Deleting messages...',
        'completed': 'All done!',
        'failed': 'Failed',
    };
    statusEl.textContent = statusMap[job.status] || job.status;
    statusEl.className = 'nuke-status ' + (job.status === 'completed' ? 'success' : job.status === 'failed' ? 'error' : 'running');

    // Progress
    const total = job.conversations_total || 1;
    const pct = Math.round((job.conversations_done / total) * 100);
    progressEl.style.width = pct + '%';

    convEl.textContent = `${job.conversations_done} / ${job.conversations_total} conversations`;
    msgsEl.textContent = `${job.messages_deleted} messages deleted`;

    if (job.messages_failed > 0) {
        failedEl.textContent = `${job.messages_failed} failed`;
        failedEl.classList.remove('hidden');
    }

    if (job.current_conversation && job.status === 'running') {
        currentEl.textContent = `Currently: ${job.current_conversation}`;
        currentEl.classList.remove('hidden');
    } else {
        currentEl.classList.add('hidden');
    }

    // Hide nuke button when running
    const nukeBtn = document.getElementById('btn-nuke');
    if (nukeBtn) {
        nukeBtn.style.display = (job.status === 'running' || job.status === 'pending') ? 'none' : '';
    }
}

// ---- Load message counts on page load ----

async function loadCounts() {
    try {
        const resp = await fetch('/api/conversations');
        const conversations = await resp.json();
        conversations.forEach(conv => {
            const el = document.getElementById(`count-${conv.id}`);
            if (el) {
                el.textContent = `${conv.my_message_count} messages`;
            }
        });
    } catch (err) {
        console.error('Failed to load counts:', err);
    }
}

// ---- Helpers ----

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
    loadCounts();

    // Reconnect to active job if one exists
    const activeJobId = document.body.dataset.activeJobId;
    if (activeJobId) {
        connectSSE(activeJobId);
    }
});
