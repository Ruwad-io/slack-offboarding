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

// ---- Delete ----

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

        // Update count display
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

async function deleteAll(dryRun) {
    if (!dryRun && !confirm('⚠️ This will DELETE ALL your messages in ALL DM conversations. This CANNOT be undone. Are you absolutely sure?')) {
        return;
    }

    showStatus(
        dryRun ? 'Simulating full cleanup...' : 'Deleting all DMs...',
        'This may take a long time. Please keep this tab open.',
        10
    );

    try {
        const resp = await fetch('/api/delete-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dry_run: dryRun }),
        });
        const stats = await resp.json();

        showStatus(
            dryRun ? 'Simulation complete' : 'Full cleanup complete!',
            `${stats.conversations_scanned} conversations scanned, ${stats.messages_deleted} messages ${dryRun ? 'would be' : ''} deleted`,
            100
        );

    } catch (err) {
        showStatus('Error', err.message, 0);
    }
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
document.addEventListener('DOMContentLoaded', loadCounts);
