/**
 * Government Payment System - County Admin UI
 * Transaction management with void and refund capabilities.
 */

const API_BASE = '/api/v1';
const API_KEY = 'county-admin-key'; // In production, from session/auth

// ─── State ───────────────────────────────────────────────
let currentTransaction = null;
let searchResults = [];

// ─── API Helper ──────────────────────────────────────────
async function api(method, path, body = null) {
    const opts = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY,
        },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${API_BASE}${path}`, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || 'Request failed');
    }
    return res.json();
}

// ─── Search ──────────────────────────────────────────────
async function searchTransactions() {
    const query = document.getElementById('search-query').value.trim();
    const status = document.getElementById('filter-status').value;
    const method = document.getElementById('filter-method').value;
    const dateFrom = document.getElementById('filter-date-from').value;
    const dateTo = document.getElementById('filter-date-to').value;

    const payload = {};
    if (query) {
        // Detect if it's a transaction number or payer name
        if (query.startsWith('GOV-') || query.startsWith('REF-')) {
            // Search by transaction number - will be handled server-side
            payload.payer_name = query; // Fallback: search broadly
        } else {
            payload.payer_name = query;
        }
    }
    if (status) payload.status = status;
    if (method) payload.payment_method = method;
    if (dateFrom) payload.date_from = new Date(dateFrom).toISOString();
    if (dateTo) payload.date_to = new Date(dateTo + 'T23:59:59').toISOString();

    try {
        const data = await api('POST', '/payments/search', payload);
        searchResults = data.transactions || [];
        renderTransactionTable(searchResults);
    } catch (err) {
        showToast('error', `Search failed: ${err.message}`);
    }
}

function renderTransactionTable(transactions) {
    const tbody = document.getElementById('txn-table-body');
    const countEl = document.getElementById('result-count');

    countEl.textContent = `${transactions.length} transaction${transactions.length !== 1 ? 's' : ''} found`;

    if (transactions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                        </svg>
                        <h3>No transactions found</h3>
                        <p>Try adjusting your search criteria</p>
                    </div>
                </td>
            </tr>`;
        return;
    }

    tbody.innerHTML = transactions.map(txn => `
        <tr onclick="openTransaction('${txn.id}')">
            <td><span class="txn-number">${txn.transaction_number}</span></td>
            <td>${txn.payer_name}</td>
            <td>${formatPaymentMethod(txn.payment_method)}</td>
            <td class="amount">$${parseFloat(txn.total_amount).toFixed(2)}</td>
            <td><span class="badge badge-${txn.status}"><span class="badge-dot"></span>${formatStatus(txn.status)}</span></td>
            <td>${txn.erm_reference_id || '—'}</td>
            <td>${formatDate(txn.created_at)}</td>
        </tr>
    `).join('');
}

// ─── Transaction Detail ──────────────────────────────────
async function openTransaction(id) {
    try {
        const txn = await api('GET', `/payments/${id}`);
        currentTransaction = txn;
        renderDetailPanel(txn);
        document.getElementById('detail-panel').classList.add('open');
        document.getElementById('detail-overlay').classList.add('open');
    } catch (err) {
        showToast('error', `Failed to load transaction: ${err.message}`);
    }
}

function closeDetail() {
    document.getElementById('detail-panel').classList.remove('open');
    document.getElementById('detail-overlay').classList.remove('open');
    currentTransaction = null;
}

function renderDetailPanel(txn) {
    const panel = document.getElementById('detail-body');
    const canVoid = ['authorized', 'captured'].includes(txn.status);
    const canRefund = ['captured', 'settled', 'partially_refunded'].includes(txn.status);
    const refundable = parseFloat(txn.subtotal) - parseFloat(txn.refunded_amount);

    document.getElementById('detail-txn-number').textContent = txn.transaction_number;
    document.getElementById('detail-status-badge').className = `badge badge-${txn.status}`;
    document.getElementById('detail-status-badge').innerHTML = `<span class="badge-dot"></span>${formatStatus(txn.status)}`;

    panel.innerHTML = `
        <!-- Payment Info -->
        <div class="detail-section">
            <h3>Payment Information</h3>
            <div class="detail-grid">
                <div class="detail-field">
                    <label>Payer Name</label>
                    <div class="value">${txn.payer_name}</div>
                </div>
                <div class="detail-field">
                    <label>Payment Method</label>
                    <div class="value">${formatPaymentMethod(txn.payment_method)}${txn.card_last_four ? ` ****${txn.card_last_four}` : ''}</div>
                </div>
                <div class="detail-field">
                    <label>Email</label>
                    <div class="value">${txn.payer_email || '—'}</div>
                </div>
                <div class="detail-field">
                    <label>Date</label>
                    <div class="value">${formatDateTime(txn.created_at)}</div>
                </div>
            </div>
        </div>

        <!-- ERM Reference -->
        ${txn.erm_reference_id ? `
        <div class="detail-section">
            <h3>ERM Reference</h3>
            <div class="detail-grid">
                <div class="detail-field">
                    <label>Reference ID</label>
                    <div class="value mono">${txn.erm_reference_id}</div>
                </div>
                <div class="detail-field">
                    <label>Document Type</label>
                    <div class="value">${txn.erm_document_type || '—'}</div>
                </div>
            </div>
        </div>` : ''}

        <!-- Amount Breakdown -->
        <div class="detail-section">
            <h3>Amount Breakdown</h3>
            <div class="amount-breakdown">
                <div class="amount-row">
                    <span>Subtotal</span>
                    <span class="amount">$${parseFloat(txn.subtotal).toFixed(2)}</span>
                </div>
                <div class="amount-row">
                    <span>Convenience Fee</span>
                    <span class="amount">$${parseFloat(txn.fee_amount).toFixed(2)}</span>
                </div>
                <div class="amount-row total">
                    <span>Total Charged</span>
                    <span class="amount">$${parseFloat(txn.total_amount).toFixed(2)}</span>
                </div>
                ${parseFloat(txn.refunded_amount) > 0 ? `
                <div class="amount-row refunded">
                    <span>Refunded</span>
                    <span class="amount">-$${parseFloat(txn.refunded_amount).toFixed(2)}</span>
                </div>` : ''}
            </div>
        </div>

        <!-- Gateway Info -->
        <div class="detail-section">
            <h3>Gateway Details</h3>
            <div class="detail-grid">
                <div class="detail-field">
                    <label>Provider</label>
                    <div class="value">${formatGateway(txn.gateway_provider)}</div>
                </div>
                <div class="detail-field">
                    <label>Gateway Transaction ID</label>
                    <div class="value mono">${txn.gateway_transaction_id || '—'}</div>
                </div>
            </div>
        </div>

        <!-- Refund History -->
        ${txn.refunds && txn.refunds.length > 0 ? `
        <div class="detail-section">
            <h3>Refund History</h3>
            <div class="refund-list">
                ${txn.refunds.map(r => `
                    <div class="refund-item">
                        <div class="refund-header">
                            <span class="txn-number">${r.refund_number}</span>
                            <span class="amount" style="color: var(--danger)">-$${parseFloat(r.amount).toFixed(2)}</span>
                        </div>
                        <div class="refund-meta">
                            ${r.reason} &middot; by ${r.requested_by} &middot; ${formatDate(r.created_at)}
                            <span class="badge badge-${r.status}" style="margin-left:4px">${r.status}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>` : ''}
    `;

    // Action buttons
    const actionsEl = document.getElementById('detail-actions');
    actionsEl.innerHTML = '';

    if (canVoid) {
        actionsEl.innerHTML += `
            <button class="btn btn-outline" onclick="openVoidModal()" style="border-color: var(--gray-400)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>
                </svg>
                Void Transaction
            </button>`;
    }

    if (canRefund) {
        actionsEl.innerHTML += `
            <button class="btn btn-warning" onclick="openRefundModal()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 10h10a5 5 0 0 1 0 10H9M3 10l4-4M3 10l4 4"/>
                </svg>
                Refund ${refundable < parseFloat(txn.subtotal) ? '(Partial)' : ''}
            </button>`;
    }

    if (!canVoid && !canRefund) {
        actionsEl.innerHTML = `
            <div class="alert alert-info" style="margin:0;flex:1">
                <span class="alert-icon">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
                    </svg>
                </span>
                This transaction cannot be voided or refunded in its current status.
            </div>`;
    }
}

// ─── Void Modal ──────────────────────────────────────────
function openVoidModal() {
    if (!currentTransaction) return;
    const modal = document.getElementById('void-modal');

    document.getElementById('void-txn-number').textContent = currentTransaction.transaction_number;
    document.getElementById('void-amount').textContent = `$${parseFloat(currentTransaction.total_amount).toFixed(2)}`;
    document.getElementById('void-payer').textContent = currentTransaction.payer_name;
    document.getElementById('void-reason').value = '';

    modal.classList.add('open');
}

function closeVoidModal() {
    document.getElementById('void-modal').classList.remove('open');
}

async function confirmVoid() {
    const reason = document.getElementById('void-reason').value.trim();
    if (!reason) {
        showToast('error', 'Please provide a reason for voiding this transaction.');
        return;
    }

    const btn = document.getElementById('void-confirm-btn');
    btn.disabled = true;
    btn.textContent = 'Processing...';

    try {
        await api('POST', `/payments/${currentTransaction.id}/void`, { reason });
        showToast('success', `Transaction ${currentTransaction.transaction_number} has been voided.`);
        closeVoidModal();
        closeDetail();
        searchTransactions(); // Refresh results
    } catch (err) {
        showToast('error', `Void failed: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Void Transaction';
    }
}

// ─── Refund Modal ────────────────────────────────────────
function openRefundModal() {
    if (!currentTransaction) return;
    const modal = document.getElementById('refund-modal');
    const maxRefund = parseFloat(currentTransaction.subtotal) - parseFloat(currentTransaction.refunded_amount);

    document.getElementById('refund-txn-number').textContent = currentTransaction.transaction_number;
    document.getElementById('refund-max-amount').textContent = `$${maxRefund.toFixed(2)}`;
    document.getElementById('refund-original-amount').textContent = `$${parseFloat(currentTransaction.subtotal).toFixed(2)}`;
    document.getElementById('refund-already-refunded').textContent = `$${parseFloat(currentTransaction.refunded_amount).toFixed(2)}`;
    document.getElementById('refund-amount').value = maxRefund.toFixed(2);
    document.getElementById('refund-amount').max = maxRefund;
    document.getElementById('refund-reason').value = '';
    document.getElementById('refund-fees-toggle').checked = false;

    // Show/hide already refunded row
    const alreadyRow = document.getElementById('refund-already-row');
    alreadyRow.style.display = parseFloat(currentTransaction.refunded_amount) > 0 ? 'flex' : 'none';

    // Full refund button
    document.getElementById('refund-full-btn').onclick = () => {
        document.getElementById('refund-amount').value = maxRefund.toFixed(2);
        updateRefundSummary();
    };

    updateRefundSummary();
    modal.classList.add('open');
}

function closeRefundModal() {
    document.getElementById('refund-modal').classList.remove('open');
}

function updateRefundSummary() {
    const amount = parseFloat(document.getElementById('refund-amount').value) || 0;
    const refundFees = document.getElementById('refund-fees-toggle').checked;
    const originalFee = parseFloat(currentTransaction.fee_amount);
    const originalSubtotal = parseFloat(currentTransaction.subtotal);

    let feeRefund = 0;
    if (refundFees && originalSubtotal > 0) {
        feeRefund = (originalFee * (amount / originalSubtotal));
    }

    document.getElementById('refund-summary-amount').textContent = `$${amount.toFixed(2)}`;
    document.getElementById('refund-summary-fee').textContent = `$${feeRefund.toFixed(2)}`;
    document.getElementById('refund-summary-total').textContent = `$${(amount + feeRefund).toFixed(2)}`;

    const feeRow = document.getElementById('refund-fee-row');
    feeRow.style.display = refundFees ? 'flex' : 'none';
}

async function confirmRefund() {
    const amount = parseFloat(document.getElementById('refund-amount').value);
    const reason = document.getElementById('refund-reason').value.trim();
    const refundFees = document.getElementById('refund-fees-toggle').checked;

    if (!amount || amount <= 0) {
        showToast('error', 'Please enter a valid refund amount.');
        return;
    }
    if (!reason) {
        showToast('error', 'Please provide a reason for this refund.');
        return;
    }

    const btn = document.getElementById('refund-confirm-btn');
    btn.disabled = true;
    btn.textContent = 'Processing...';

    try {
        const result = await api('POST', `/payments/${currentTransaction.id}/refund`, {
            amount: amount,
            reason: reason,
            refund_fees: refundFees,
        });
        showToast('success', `Refund ${result.refund_number} processed: $${parseFloat(result.total_refund).toFixed(2)}`);
        closeRefundModal();
        // Refresh detail panel
        await openTransaction(currentTransaction.id);
        searchTransactions(); // Refresh table
    } catch (err) {
        showToast('error', `Refund failed: ${err.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Process Refund';
    }
}

// ─── Toast Notifications ─────────────────────────────────
function showToast(type, message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success'
        ? '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>'
        : '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/></svg>';

    toast.innerHTML = `${icon}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// ─── Formatting Helpers ──────────────────────────────────
function formatStatus(status) {
    const labels = {
        pending: 'Pending',
        authorized: 'Authorized',
        captured: 'Captured',
        settled: 'Settled',
        voided: 'Voided',
        refunded: 'Refunded',
        partially_refunded: 'Partial Refund',
        declined: 'Declined',
        failed: 'Failed',
    };
    return labels[status] || status;
}

function formatPaymentMethod(method) {
    const labels = {
        credit_card: 'Credit Card',
        debit_card: 'Debit Card',
        ach: 'ACH',
        echeck: 'eCheck',
        cash: 'Cash',
        check: 'Check',
        money_order: 'Money Order',
    };
    return labels[method] || method;
}

function formatGateway(gw) {
    const labels = { stripe: 'Stripe', authorize_net: 'Authorize.Net' };
    return labels[gw] || gw;
}

function formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit', hour12: true,
    });
}

// ─── Event Listeners ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Search on Enter
    document.getElementById('search-query').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') searchTransactions();
    });

    // Escape to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeVoidModal();
            closeRefundModal();
            closeDetail();
        }
    });

    // Refund amount change
    const refundAmountEl = document.getElementById('refund-amount');
    if (refundAmountEl) {
        refundAmountEl.addEventListener('input', updateRefundSummary);
    }

    // Refund fees toggle
    const feesToggle = document.getElementById('refund-fees-toggle');
    if (feesToggle) {
        feesToggle.addEventListener('change', updateRefundSummary);
    }
});
