"""
Apex Logistics - B2B Freight Claim & Refund Decision Engine
Flask REST API & Operational Dashboard Web Server
"""

from flask import Flask, jsonify, request, render_template_string
from flask_cors import CORS
import database
from init_db import init_database

app = Flask(__name__)
CORS(app)


# -----------------------------------------------------------------------------
# REST API ENDPOINTS
# -----------------------------------------------------------------------------

@app.route('/api/claims/submit', methods=['POST'])
def api_submit_claim():
    """
    Ingests a freight claim payload, evaluates it through the decision engine,
    updates database state, and returns decision result.
    """
    payload = request.get_json(force=True, silent=True) or {}
    if not payload.get('client_id'):
        return jsonify({"error": "client_id is required."}), 400
    if 'claim_amount' not in payload:
        return jsonify({"error": "claim_amount is required."}), 400

    try:
        saved_claim = database.submit_claim(payload)
        return jsonify({
            "message": "Claim evaluated and processed successfully.",
            "data": saved_claim
        }), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/api/claims', methods=['GET'])
def api_get_claims():
    """Lists claims with optional status, client_id, and search filters."""
    status = request.args.get('status')
    client_id = request.args.get('client_id')
    search = request.args.get('search')
    limit = int(request.args.get('limit', 100))

    orders = database.get_all_orders(status=status, client_id=client_id, search=search, limit=limit)
    return jsonify({"count": len(orders), "data": orders}), 200


@app.route('/api/claims/<order_id>', methods=['GET'])
def api_get_claim_detail(order_id):
    """Retrieves detailed information for a specific claim."""
    order = database.get_order_by_id(order_id)
    if not order:
        return jsonify({"error": "Claim not found."}), 404
    return jsonify({"data": order}), 200


@app.route('/api/claims/<order_id>/override', methods=['POST'])
def api_override_claim(order_id):
    """Human-in-the-loop override endpoint for auditing claims."""
    payload = request.get_json(force=True, silent=True) or {}
    new_status = payload.get('claim_status')
    agent_note = payload.get('agent_note', 'Manual agent review sign-off.')

    if not new_status:
        return jsonify({"error": "claim_status is required."}), 400

    try:
        updated = database.override_claim_decision(order_id, new_status, agent_note)
        return jsonify({
            "message": f"Claim status overridden to {new_status} successfully.",
            "data": updated
        }), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/clients', methods=['GET'])
def api_get_clients():
    """Lists all registered B2B clients and their 30-day refund velocity."""
    clients = database.get_all_clients()
    return jsonify({"count": len(clients), "data": clients}), 200


@app.route('/api/clients', methods=['POST'])
def api_create_client():
    """Registers a new client profile."""
    payload = request.get_json(force=True, silent=True) or {}
    if not payload.get('company_name') or not payload.get('client_id'):
        return jsonify({"error": "client_id and company_name are required."}), 400

    try:
        new_client = database.create_client(payload)
        return jsonify({"message": "Client created successfully.", "data": new_client}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/dashboard/stats', methods=['GET'])
def api_dashboard_stats():
    """Returns real-time SLA metrics and executive decision statistics."""
    stats = database.get_dashboard_analytics()
    return jsonify({"data": stats}), 200


@app.route('/api/seed/reset', methods=['POST'])
def api_reset_seed():
    """Resets the database to default seed records."""
    try:
        init_database()
        return jsonify({"message": "Database reset to seed data successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------------------------------------------------------------
# FRONTEND DASHBOARD HTML TEMPLATE
# -----------------------------------------------------------------------------
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Apex Logistics - B2B Claim & Refund Decision Engine</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        brand: {
                            50: '#f0f6ff',
                            500: '#2563eb',
                            600: '#1d4ed8',
                            900: '#0f172a'
                        },
                        approve: '#10b981',
                        audit: '#f59e0b',
                        reject: '#ef4444'
                    }
                }
            }
        }
    </script>
    <!-- Font Awesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- Google Fonts Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #e2e8f0; }
        .glass-panel { background: rgba(17, 24, 39, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }
        .glass-card { background: rgba(30, 41, 59, 0.6); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.05); }
        .pulse-glow { box-shadow: 0 0 25px rgba(37, 99, 235, 0.25); }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Header / Navbar -->
    <header class="glass-panel sticky top-0 z-50 border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-blue-500/30">
                <i class="fa-solid fa-truck-fast"></i>
            </div>
            <div>
                <h1 class="text-xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-blue-400">
                    Apex Logistics
                </h1>
                <p class="text-xs text-slate-400 font-medium">B2B Freight Claim & Refund Decision Engine</p>
            </div>
        </div>

        <div class="flex items-center gap-4">
            <span class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
                <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> SLA Active Engine
            </span>
            <button onclick="resetDatabase()" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition border border-slate-700 flex items-center gap-2">
                <i class="fa-solid fa-rotate"></i> Reset Seed Data
            </button>
        </div>
    </header>

    <!-- Main Workspace -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-8">

        <!-- Top Metric Cards -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4" id="kpi-container">
            <div class="glass-card p-5 rounded-2xl">
                <div class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Total Claims Processed</div>
                <div class="text-2xl font-bold text-white mt-1" id="kpi-total">-</div>
                <div class="text-xs text-slate-500 mt-2 flex items-center gap-1"><i class="fa-solid fa-bolt text-blue-400"></i> Real-time ingestion</div>
            </div>
            <div class="glass-card p-5 rounded-2xl border-l-4 border-l-emerald-500">
                <div class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Auto-Approval Rate</div>
                <div class="text-2xl font-bold text-emerald-400 mt-1" id="kpi-auto-rate">-</div>
                <div class="text-xs text-slate-400 mt-2"><span id="kpi-auto-cnt">-</span> claims instant approved</div>
            </div>
            <div class="glass-card p-5 rounded-2xl border-l-4 border-l-amber-500">
                <div class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Pending Audit Queue</div>
                <div class="text-2xl font-bold text-amber-400 mt-1" id="kpi-audit-cnt">-</div>
                <div class="text-xs text-slate-400 mt-2"><span id="kpi-audit-val">$0</span> value in review</div>
            </div>
            <div class="glass-card p-5 rounded-2xl border-l-4 border-l-rose-500">
                <div class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Rejected Claims</div>
                <div class="text-2xl font-bold text-rose-400 mt-1" id="kpi-reject-rate">-</div>
                <div class="text-xs text-slate-400 mt-2"><span id="kpi-reject-cnt">-</span> non-qualifying claims</div>
            </div>
            <div class="glass-card p-5 rounded-2xl border-l-4 border-l-indigo-500">
                <div class="text-slate-400 text-xs font-semibold uppercase tracking-wider">SLA Processing Saved</div>
                <div class="text-2xl font-bold text-indigo-400 mt-1" id="kpi-sla-saved">-</div>
                <div class="text-xs text-slate-400 mt-2">Hours manual effort saved</div>
            </div>
        </div>

        <!-- Middle Section: Claim Simulator & Client Directory -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            <!-- Claim Simulator Form -->
            <div class="lg:col-span-1 glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <h2 class="text-lg font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-wand-magic-sparkles text-blue-400"></i> Decision Engine Simulator
                    </h2>
                    <span class="text-xs bg-blue-500/10 text-blue-400 px-2.5 py-0.5 rounded-full border border-blue-500/20 font-medium">Interactive Payload</span>
                </div>

                <form id="simulator-form" onsubmit="handleClaimSubmit(event)" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Select Client Account</label>
                        <select id="sim-client" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                            <!-- Populated via JS -->
                        </select>
                    </div>

                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Claim Amount ($)</label>
                            <input type="number" step="0.01" id="sim-amount" value="1450.00" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" placeholder="1450.00">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Declared Value ($)</label>
                            <input type="number" step="0.01" id="sim-declared" value="12500.00" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" placeholder="12500.00">
                        </div>
                    </div>

                    <div>
                        <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Delay / Exception Cause</label>
                        <select id="sim-cause" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                            <option value="CARRIER_FAULT">CARRIER_FAULT (Hub sorting delay / Missing dispatch)</option>
                            <option value="CUSTOMS_HOLD">CUSTOMS_HOLD (Border tariff audit / Doc hold)</option>
                            <option value="WEATHER_FORCE_MAJEURE">WEATHER_FORCE_MAJEURE (Storm / Act of God)</option>
                        </select>
                    </div>

                    <div>
                        <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Tracking Number</label>
                        <input type="text" id="sim-tracking" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500" placeholder="APX-TRK-99001122">
                    </div>

                    <button type="submit" class="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-sm shadow-lg shadow-blue-600/30 transition flex items-center justify-center gap-2">
                        <i class="fa-solid fa-microchip"></i> Evaluate Claim Payload
                    </button>
                </form>
            </div>

            <!-- Client Directory & Velocity Monitor -->
            <div class="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
                <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                    <h2 class="text-lg font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-users-gear text-indigo-400"></i> B2B Client Tier & Refund Velocity
                    </h2>
                    <span class="text-xs text-slate-400 font-medium">30-Day Rolling Window</span>
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-slate-300">
                        <thead class="bg-slate-900/60 text-slate-400 uppercase text-xs font-semibold border-b border-slate-800">
                            <tr>
                                <th class="py-3 px-4">Client ID</th>
                                <th class="py-3 px-4">Company Name</th>
                                <th class="py-3 px-4">Tier</th>
                                <th class="py-3 px-4 text-center">30d Refund Count</th>
                                <th class="py-3 px-4">Account Status</th>
                            </tr>
                        </thead>
                        <tbody id="client-table-body" class="divide-y divide-slate-800">
                            <!-- Populated via JS -->
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- Operational Audit Queue & Claims Table -->
        <div class="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4">
            <div class="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                <div>
                    <h2 class="text-lg font-bold text-white flex items-center gap-2">
                        <i class="fa-solid fa-list-check text-emerald-400"></i> Operational Audit & Claims Stream
                    </h2>
                    <p class="text-xs text-slate-400">Review automated decision outcomes & perform human-in-the-loop audit sign-offs</p>
                </div>

                <!-- Filters -->
                <div class="flex flex-wrap items-center gap-3">
                    <input type="text" id="filter-search" oninput="fetchClaims()" placeholder="Search tracking or order..." class="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500 w-48">
                    
                    <select id="filter-status" onchange="fetchClaims()" class="bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
                        <option value="">All Decision Statuses</option>
                        <option value="AUTO_APPROVE">AUTO_APPROVE Only</option>
                        <option value="FLAG_FOR_AUDIT">FLAG_FOR_AUDIT Only</option>
                        <option value="REJECT">REJECT Only</option>
                    </select>
                </div>
            </div>

            <!-- Table -->
            <div class="overflow-x-auto">
                <table class="w-full text-left text-sm text-slate-300">
                    <thead class="bg-slate-900/60 text-slate-400 uppercase text-xs font-semibold border-b border-slate-800">
                        <tr>
                            <th class="py-3 px-4">Order / Tracking</th>
                            <th class="py-3 px-4">Client</th>
                            <th class="py-3 px-4">Claim Amount</th>
                            <th class="py-3 px-4">Delay Cause</th>
                            <th class="py-3 px-4">Decision Outcome</th>
                            <th class="py-3 px-4">AI Reasoning & Justification</th>
                            <th class="py-3 px-4 text-right">Audit Action</th>
                        </tr>
                    </thead>
                    <tbody id="claims-table-body" class="divide-y divide-slate-800">
                        <!-- Populated via JS -->
                    </tbody>
                </table>
            </div>
        </div>

    </main>

    <!-- Modal for Human Override -->
    <div id="override-modal" class="fixed inset-0 bg-black/70 backdrop-blur-sm hidden items-center justify-center z-50 p-4">
        <div class="glass-panel max-w-lg w-full p-6 rounded-2xl border border-slate-700 space-y-4 shadow-2xl">
            <div class="flex items-center justify-between pb-3 border-b border-slate-800">
                <h3 class="text-base font-bold text-white">Human Agent Decision Override</h3>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            
            <p class="text-xs text-slate-300">You are manually overriding the automated decision state for <span id="modal-order-id" class="font-bold text-blue-400"></span>.</p>
            
            <div>
                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">New Target Decision</label>
                <select id="modal-status" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500">
                    <option value="AUTO_APPROVE">AUTO_APPROVE (Approve Refund)</option>
                    <option value="REJECT">REJECT (Decline Claim)</option>
                    <option value="FLAG_FOR_AUDIT">FLAG_FOR_AUDIT (Escalate)</option>
                </select>
            </div>

            <div>
                <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">Agent Audit Justification Note</label>
                <textarea id="modal-note" rows="3" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 text-xs" placeholder="Verified physical cargo manifest with carrier ops..."></textarea>
            </div>

            <div class="flex justify-end gap-3 pt-2">
                <button onclick="closeModal()" class="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700">Cancel</button>
                <button onclick="submitOverride()" class="px-4 py-2 rounded-xl bg-blue-600 text-white text-xs font-bold hover:bg-blue-500 shadow-md shadow-blue-600/30">Save Audit Override</button>
            </div>
        </div>
    </div>

    <!-- Toast Notification -->
    <div id="toast" class="fixed bottom-6 right-6 bg-slate-900 border border-blue-500 text-white px-5 py-3 rounded-xl text-xs font-semibold shadow-2xl transition transform translate-y-20 opacity-0 z-50 flex items-center gap-2">
        <i class="fa-solid fa-circle-check text-emerald-400 text-base"></i> <span id="toast-msg">Action completed.</span>
    </div>

    <!-- JS Logic -->
    <script>
        let clientsList = [];
        let activeOverrideOrderId = null;

        document.addEventListener('DOMContentLoaded', () => {
            initApp();
        });

        async function initApp() {
            await fetchDashboardStats();
            await fetchClients();
            await fetchClaims();
        }

        function showToast(msg) {
            const toast = document.getElementById('toast');
            document.getElementById('toast-msg').innerText = msg;
            toast.classList.remove('translate-y-20', 'opacity-0');
            setTimeout(() => {
                toast.classList.add('translate-y-20', 'opacity-0');
            }, 3500);
        }

        async function fetchDashboardStats() {
            try {
                const res = await fetch('/api/dashboard/stats');
                const json = await res.json();
                const s = json.data;

                document.getElementById('kpi-total').innerText = s.total_claims;
                document.getElementById('kpi-auto-rate').innerText = s.auto_approval_rate_pct + '%';
                document.getElementById('kpi-auto-cnt').innerText = s.auto_approved_count;
                document.getElementById('kpi-audit-cnt').innerText = s.flagged_audit_count;
                document.getElementById('kpi-audit-val').innerText = '$' + s.pending_audit_value_usd.toLocaleString();
                document.getElementById('kpi-reject-rate').innerText = s.rejection_rate_pct + '%';
                document.getElementById('kpi-reject-cnt').innerText = s.rejected_count;
                document.getElementById('kpi-sla-saved').innerText = s.sla_hours_saved + ' hrs';
            } catch (err) {
                console.error("Error fetching stats:", err);
            }
        }

        async function fetchClients() {
            try {
                const res = await fetch('/api/clients');
                const json = await res.json();
                clientsList = json.data;

                // Populate Simulator dropdown
                const select = document.getElementById('sim-client');
                select.innerHTML = clientsList.map(c => `
                    <option value="${c.client_id}">
                        ${c.company_name} (${c.tier} | 30d Refunds: ${c.refund_count_30d})
                    </option>
                `).join('');

                // Populate Client Table
                const tbody = document.getElementById('client-table-body');
                tbody.innerHTML = clientsList.map(c => `
                    <tr class="hover:bg-slate-800/40">
                        <td class="py-3 px-4 font-mono text-xs font-bold text-blue-400">${c.client_id}</td>
                        <td class="py-3 px-4 font-semibold text-white">${c.company_name}</td>
                        <td class="py-3 px-4">
                            <span class="px-2.5 py-0.5 rounded-full text-xs font-bold ${c.tier === 'ENTERPRISE_VIP' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'bg-slate-700 text-slate-300'}">
                                ${c.tier}
                            </span>
                        </td>
                        <td class="py-3 px-4 text-center font-bold ${c.refund_count_30d >= 5 ? 'text-amber-400' : 'text-slate-300'}">
                            ${c.refund_count_30d}
                        </td>
                        <td class="py-3 px-4">
                            <span class="px-2 py-0.5 rounded text-xs font-semibold ${c.account_status === 'ACTIVE' ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'}">
                                ${c.account_status}
                            </span>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error("Error fetching clients:", err);
            }
        }

        async function fetchClaims() {
            const status = document.getElementById('filter-status').value;
            const search = document.getElementById('filter-search').value;

            let url = `/api/claims?limit=50`;
            if (status) url += `&status=${status}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;

            try {
                const res = await fetch(url);
                const json = await res.json();
                const claims = json.data;

                const tbody = document.getElementById('claims-table-body');
                if (claims.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-500 text-xs">No matching claims found.</td></tr>`;
                    return;
                }

                tbody.innerHTML = claims.map(o => {
                    let badgeClass = "bg-slate-700 text-slate-300";
                    if (o.claim_status === 'AUTO_APPROVE') badgeClass = "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
                    if (o.claim_status === 'FLAG_FOR_AUDIT') badgeClass = "bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse";
                    if (o.claim_status === 'REJECT') badgeClass = "bg-rose-500/20 text-rose-300 border border-rose-500/40";

                    return `
                        <tr class="hover:bg-slate-800/50 transition">
                            <td class="py-3 px-4">
                                <div class="font-bold text-white text-xs">${o.order_id}</div>
                                <div class="text-[11px] font-mono text-slate-400">${o.tracking_number}</div>
                            </td>
                            <td class="py-3 px-4">
                                <div class="font-medium text-slate-200">${o.company_name}</div>
                                <div class="text-[10px] text-slate-400 font-bold">${o.client_tier}</div>
                            </td>
                            <td class="py-3 px-4 font-bold text-white">
                                $${o.claim_amount.toLocaleString(undefined, {minimumFractionDigits: 2})}
                                <div class="text-[10px] text-slate-400 font-normal">Val: $${o.declared_value.toLocaleString()}</div>
                            </td>
                            <td class="py-3 px-4 text-xs font-mono text-slate-300">${o.delay_cause}</td>
                            <td class="py-3 px-4">
                                <span class="px-2.5 py-1 rounded-lg text-xs font-extrabold ${badgeClass}">
                                    ${o.claim_status}
                                </span>
                            </td>
                            <td class="py-3 px-4 text-xs text-slate-300 max-w-xs">
                                <p class="line-clamp-2 hover:line-clamp-none transition-all cursor-pointer" title="${o.ai_justification}">
                                    ${o.ai_justification}
                                </p>
                            </td>
                            <td class="py-3 px-4 text-right">
                                <button onclick="openOverrideModal('${o.order_id}', '${o.claim_status}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-blue-400 border border-slate-700 text-xs font-semibold transition">
                                    <i class="fa-solid fa-pen-to-square"></i> Audit
                                </button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error("Error fetching claims:", err);
            }
        }

        async function handleClaimSubmit(event) {
            event.preventDefault();
            const client_id = document.getElementById('sim-client').value;
            const claim_amount = parseFloat(document.getElementById('sim-amount').value);
            const declared_value = parseFloat(document.getElementById('sim-declared').value);
            const delay_cause = document.getElementById('sim-cause').value;
            const tracking_number = document.getElementById('sim-tracking').value || undefined;

            const payload = { client_id, claim_amount, declared_value, delay_cause, tracking_number };

            try {
                const res = await fetch('/api/claims/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const json = await res.json();
                if (res.ok) {
                    showToast(`Claim Evaluated: ${json.data.claim_status}`);
                    await initApp();
                } else {
                    alert('Error: ' + json.error);
                }
            } catch (err) {
                alert('Submission failed: ' + err.message);
            }
        }

        function openOverrideModal(order_id, current_status) {
            activeOverrideOrderId = order_id;
            document.getElementById('modal-order-id').innerText = order_id;
            document.getElementById('modal-status').value = current_status;
            document.getElementById('override-modal').classList.remove('hidden');
            document.getElementById('override-modal').classList.add('flex');
        }

        function closeModal() {
            document.getElementById('override-modal').classList.add('hidden');
            document.getElementById('override-modal').classList.remove('flex');
            activeOverrideOrderId = null;
        }

        async function submitOverride() {
            if (!activeOverrideOrderId) return;
            const new_status = document.getElementById('modal-status').value;
            const agent_note = document.getElementById('modal-note').value;

            try {
                const res = await fetch(`/api/claims/${activeOverrideOrderId}/override`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ claim_status: new_status, agent_note })
                });
                if (res.ok) {
                    closeModal();
                    showToast('Audit override recorded successfully.');
                    await initApp();
                } else {
                    const json = await res.json();
                    alert('Override failed: ' + json.error);
                }
            } catch (err) {
                alert('Error submitting override: ' + err.message);
            }
        }

        async function resetDatabase() {
            if (!confirm('Are you sure you want to reset the database to sample seed data?')) return;
            try {
                const res = await fetch('/api/seed/reset', { method: 'POST' });
                if (res.ok) {
                    showToast('Database reset to seed data.');
                    await initApp();
                }
            } catch (err) {
                alert('Reset failed: ' + err.message);
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serves the Single-Page Operational Dashboard."""
    return render_template_string(HTML_LAYOUT)


if __name__ == '__main__':
    print("Starting Apex Logistics Decision Engine Web Server on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
