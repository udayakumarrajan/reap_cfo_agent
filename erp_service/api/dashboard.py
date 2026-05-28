def generate_dashboard_html(transactions, balances, outbox_len, selected_tenant="all", unique_tenants=None) -> str:
    """
    Generates a premium, responsive HTML dashboard using Vanilla CSS.
    Isolated from the router logic for better maintainability.

    Changes:
    - selected_tenant defaults to "all" (show everything)
    - "All" option prepended to tenant selector
    - Ledger Balances filtered by tenant when a specific one is selected
    - Transactions filtered by tenant when a specific one is selected
    - Notes tooltip uses a JS-powered floating popover (no CSS ::after clipping issues)
    """

    # ── tenant selector ──────────────────────────────────────────────────────
    tenant_options = '<option value="all"' + (' selected' if selected_tenant == "all" else '') + '>All Tenants</option>'
    for t in (unique_tenants or ["123"]):
        selected = "selected" if t == selected_tenant else ""
        tenant_options += f'<option value="{t}" {selected}>Tenant {t}</option>'

    # ── filter transactions ───────────────────────────────────────────────────
    if selected_tenant == "all":
        filtered_tx = transactions
    else:
        filtered_tx = {k: v for k, v in transactions.items()
                       if v.get("tenant_id") == selected_tenant}

    # Balances are pre-filtered/aggregated by the router via get_ledger_balances_for_view
    filtered_balances = balances

    display_outbox = outbox_len if isinstance(outbox_len, int) else len(outbox_len)

    # ── build balance cards ───────────────────────────────────────────────────
    balance_cards = ""
    for code, amt in filtered_balances.items():
        balance_cards += f"""
        <div class="balance-card">
            <div class="balance-label">{code}</div>
            <div class="balance-amount">${amt:,.2f}</div>
            <div class="balance-sub">Ledger balance</div>
        </div>
        """

    show_tenant_col = selected_tenant == "all"

    # ── build transaction rows ────────────────────────────────────────────────
    rows = ""
    for tx_id, tx in reversed(list(filtered_tx.items())):
        status_class = tx['status'].lower().replace("_", "-")
        status_label = tx['status'].replace("_", " ").title()
        amount = tx['amount']
        comments_text = tx.get('comments') or '—'
        # Escape for HTML attribute & cell content
        comments_escaped = comments_text.replace('"', '&quot;').replace("'", "&#39;")
        tenant_cell = f'<td class="muted">Tenant {tx.get("tenant_id", "—")}</td>' if show_tenant_col else ""
        resolve_cell = ""
        if tx.get("status") == "NEEDS_REVIEW" and tx.get("workflow_id"):
            resolve_cell = f"""
            <td class="action-cell">
                <form method="post" action="/api/transactions/{tx_id}/resolve" style="display:flex;gap:4px;align-items:center;">
                    <select name="account_code" class="resolve-select">
                        <option value="6100">6100 SaaS</option>
                        <option value="6200" selected>6200 Marketing</option>
                    </select>
                    <button type="submit" class="btn-resolve">Approve</button>
                </form>
            </td>"""
        elif tx.get("status") == "NEEDS_REVIEW":
            resolve_cell = '<td class="action-cell muted">No workflow</td>'
        else:
            resolve_cell = '<td class="action-cell muted">—</td>'

        rows += f"""
        <tr class="tx-row">
            <td><span class="tx-id">{tx_id}</span></td>
            {tenant_cell}
            <td><span class="ext-ref">{(tx.get('external_id') or '—')[:10]}</span></td>
            <td class="merchant">{tx['merchant']}</td>
            <td class="amount-cell">${amount:,.2f}</td>
            <td><span class="badge {status_class}">{status_label}</span></td>
            <td class="muted">{tx.get('account_code') or '—'}</td>
            {resolve_cell}
            <td class="comment-cell" data-notes="{comments_escaped}">{comments_text}</td>
            <td class="muted time-cell">{tx['timestamp'].split('T')[1][:8] if 'T' in str(tx.get('timestamp', '')) else (tx.get('timestamp') or '—')}</td>
        </tr>
        """

    tx_count = len(filtered_tx)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reap CFO · Ledger Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

:root {{
    --bg:             #f8fafc;
    --surface:        #ffffff;
    --surface-2:      #f1f5f9;
    --border:         #e2e8f0;
    --border-2:       #cbd5e1;
    --text:           #0f172a;
    --text-2:         #475569;
    --text-3:         #64748b;
    --accent:         #2563eb;
    --accent-bg:      #eff6ff;

    --green:          #16a34a;
    --green-bg:       #f0fdf4;
    --green-border:   #bbf7d0;

    --amber:          #d97706;
    --amber-bg:       #fffbeb;
    --amber-border:   #fef3c7;

    --blue:           #2563eb;
    --blue-bg:        #eff6ff;
    --blue-border:    #dbeafe;

    --slate:          #475569;
    --slate-bg:       #f8fafc;
    --slate-border:   #e2e8f0;

    --red:            #dc2626;
    --red-bg:         #fef2f2;
    --red-border:     #fee2e2;

    --radius:         8px;
    --radius-lg:      12px;
    --font: 'DM Sans', system-ui, sans-serif;
    --mono: 'DM Mono', monospace;
    --shadow:         0 1px 3px 0 rgba(0,0,0,.05), 0 1px 2px -1px rgba(0,0,0,.05);
    --shadow-md:      0 4px 6px -1px rgba(0,0,0,.03), 0 2px 4px -2px rgba(0,0,0,.03);
    --shadow-pop:     0 8px 24px rgba(0,0,0,.18), 0 2px 6px rgba(0,0,0,.1);
}}

body {{
    font-family: var(--font);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}}

/* ── LAYOUT ── */
.shell {{
    display: grid;
    grid-template-rows: auto 1fr;
    min-height: 100vh;
}}

.topbar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(255,255,255,.85);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    padding: 0 2.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    gap: 1.5rem;
}}

.topbar-left {{
    display: flex;
    align-items: center;
    gap: 1.25rem;
}}

.divider-v {{
    width: 1px;
    height: 20px;
    background: var(--border);
}}

.page-title {{
    font-size: .85rem;
    font-weight: 600;
    color: var(--text-2);
    letter-spacing: .03em;
}}

.topbar-right {{
    display: flex;
    align-items: center;
    gap: 1rem;
}}

.tenant-wrap {{
    display: flex;
    align-items: center;
    gap: .5rem;
}}

.tenant-label {{
    font-size: .75rem;
    color: var(--text-3);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    white-space: nowrap;
}}

select {{
    appearance: none;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border-2);
    padding: .4rem 2rem .4rem .75rem;
    border-radius: var(--radius);
    font-family: var(--font);
    font-size: .825rem;
    font-weight: 500;
    cursor: pointer;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right .6rem center;
    transition: all .15s;
    outline: none;
    box-shadow: var(--shadow);
}}
select:hover {{ border-color: var(--text-3); }}
select:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px rgba(37,99,235,.15); }}


.btn-resolve {{
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid var(--blue-border);
    background: var(--blue-bg);
    color: var(--blue);
    cursor: pointer;
}}
.btn-resolve:hover {{ opacity: 0.85; }}
.resolve-select {{
    font-size: 11px;
    padding: 3px 6px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--surface);
}}
.action-cell {{ min-width: 180px; }}

.btn-refresh {{
    display: inline-flex;
    align-items: center;
    gap: .4rem;
    background: var(--surface);
    color: var(--text-2);
    border: 1px solid var(--border-2);
    padding: .4rem .9rem;
    border-radius: var(--radius);
    font-family: var(--font);
    font-size: .8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all .15s;
    box-shadow: var(--shadow);
}}
.btn-refresh:hover {{ background: var(--slate-bg); color: var(--text); border-color: var(--text-3); }}
.btn-refresh svg {{ flex-shrink: 0; }}

.live-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 0 3px rgba(22,163,74,.15);
    animation: pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
    0%,100% {{ opacity:1; transform:scale(1); }}
    50%      {{ opacity:.6; transform:scale(.95); }}
}}

/* ── MAIN ── */
.main {{
    padding: 2.5rem 2.5rem 4rem;
    max-width: 1400px;
    margin: 0 auto;
    width: 100%;
}}

.section-head {{
    display: flex;
    align-items: center;
    gap: .75rem;
    margin-bottom: 1.25rem;
}}
.section-title {{
    font-size: .75rem;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: .08em;
}}
.section-line {{
    flex: 1;
    height: 1px;
    background: var(--border);
}}

/* ── BALANCE CARDS ── */
.balances-row {{
    display: flex;
    gap: 1.25rem;
    margin-bottom: 3rem;
    flex-wrap: wrap;
}}

.balance-card {{
    flex: 1;
    min-width: 220px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    transition: all .2s;
    box-shadow: var(--shadow-md);
}}
.balance-card:hover {{ border-color: var(--border-2); transform: translateY(-1px); }}

.balance-label {{
    font-size: .75rem;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: .05em;
    margin-bottom: .5rem;
}}

.balance-amount {{
    font-size: 1.75rem;
    font-weight: 500;
    color: var(--text);
    letter-spacing: -.03em;
    font-family: var(--mono);
    line-height: 1.2;
    margin-bottom: .25rem;
}}

.balance-sub {{
    font-size: .75rem;
    color: var(--text-3);
}}

.outbox-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 1.5rem;
    min-width: 220px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: var(--shadow-md);
    transition: all .2s;
}}
.outbox-card:hover {{ border-color: var(--border-2); transform: translateY(-1px); }}

.outbox-count {{
    font-size: 1.75rem;
    font-weight: 500;
    color: var(--amber);
    font-family: var(--mono);
    line-height: 1.2;
    margin-bottom: .25rem;
}}

/* ── TABLE ── */
.table-wrap {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    overflow: hidden;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    font-size: .85rem;
}}

thead tr {{
    background: #fafafa;
    border-bottom: 1px solid var(--border);
}}

th {{
    padding: .85rem 1rem;
    text-align: left;
    font-size: .7rem;
    font-weight: 600;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: .05em;
    white-space: nowrap;
}}

.tx-row {{
    border-bottom: 1px solid var(--border);
    transition: background .1s;
}}
.tx-row:last-child {{ border-bottom: none; }}
.tx-row:hover {{ background: #fafafa; }}

td {{
    padding: .95rem 1rem;
    vertical-align: middle;
}}

.tx-id {{
    font-family: var(--mono);
    font-size: .75rem;
    color: var(--accent);
    font-weight: 500;
    background: var(--accent-bg);
    padding: .15rem .4rem;
    border-radius: 4px;
}}

.ext-ref {{
    font-family: var(--mono);
    font-size: .75rem;
    color: var(--text-3);
}}

.merchant {{ font-weight: 500; color: var(--text); }}
.amount-cell {{ font-family: var(--mono); font-weight: 500; color: var(--text); text-align: right; }}
.muted {{ color: var(--text-3); font-size: .8rem; }}

/* ── NOTES CELL — truncated with JS popover ── */
.comment-cell {{
    color: var(--text-2);
    font-size: .8rem;
    max-width: 220px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: default;
}}
/* show pointer only when overflow present (set via JS) */
.comment-cell.has-overflow {{ cursor: help; }}

.time-cell {{
    font-family: var(--mono);
    font-size: .78rem;
    white-space: nowrap;
}}

/* ── BADGES ── */
.badge {{
    display: inline-flex;
    align-items: center;
    gap: .35rem;
    padding: .25rem .6rem;
    border-radius: 6px;
    font-size: .725rem;
    font-weight: 500;
    white-space: nowrap;
    border: 1px solid transparent;
}}
.badge::before {{
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
}}
.auto-posted    {{ background:var(--green-bg);  color:var(--green);  border-color:var(--green-border);  }}
.auto-posted::before  {{ background:var(--green);  }}
.human-resolved {{ background:var(--blue-bg);   color:var(--blue);   border-color:var(--blue-border);   }}
.human-resolved::before {{ background:var(--blue);   }}
.needs-review   {{ background:var(--amber-bg);  color:var(--amber);  border-color:var(--amber-border);  }}
.needs-review::before {{ background:var(--amber);  }}
.pending        {{ background:var(--slate-bg);  color:var(--slate);  border-color:var(--slate-border);  }}
.pending::before      {{ background:var(--slate);  }}
.failed         {{ background:var(--red-bg);    color:var(--red);    border-color:var(--red-border);    }}
.failed::before       {{ background:var(--red);    }}

/* ── FLOATING NOTES POPOVER ── */
#notes-popover {{
    display: none;
    position: fixed;          /* fixed so it never clips inside overflow:hidden parents */
    z-index: 9999;
    background: #0f172a;
    color: #f8fafc;
    padding: .6rem .85rem;
    border-radius: 7px;
    font-size: .775rem;
    font-family: var(--font);
    line-height: 1.55;
    max-width: 320px;
    white-space: normal;
    word-break: break-word;
    box-shadow: var(--shadow-pop);
    pointer-events: none;
    opacity: 0;
    transition: opacity .12s ease;
}}
#notes-popover.visible {{
    display: block;
    opacity: 1;
}}
/* little arrow */
#notes-popover::after {{
    content: '';
    position: absolute;
    top: 100%;
    left: 14px;
    border: 6px solid transparent;
    border-top-color: #0f172a;
}}

/* ── FOOTER ── */
.footer-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.25rem;
    background: #fafafa;
    border-top: 1px solid var(--border);
    font-size: .75rem;
    color: var(--text-3);
}}
.footer-stat {{ display:flex; align-items:center; gap:.5rem; }}
.footer-live {{ display:flex; align-items:center; gap:.5rem; }}
</style>
</head>
<body>

<!-- Floating popover element (single instance, moved by JS) -->
<div id="notes-popover" role="tooltip"></div>

<div class="shell">

<header class="topbar">
    <div class="topbar-left">
        <img src="https://cdn.prod.website-files.com/680aece1e09d2fc748dc309c/681c848f50600b5c77d17a09_logo.svg"
             alt="Reap" style="height:24px;width:auto;display:block;filter:brightness(0) saturate(100%);opacity:.85;">
        <div class="divider-v"></div>
        <span class="page-title">CFO Ledger</span>
    </div>
    <div class="topbar-right">
        <div class="tenant-wrap">
            <span class="tenant-label">Tenant</span>
            <select id="tenantSelect" onchange="switchTenant()">
                {tenant_options}
            </select>
        </div>
        <button class="btn-refresh" onclick="location.reload()">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
                <path d="M21 3v5h-5"/>
                <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
                <path d="M8 16H3v5"/>
            </svg>
            Refresh
        </button>
        <div class="live-dot" title="Live data"></div>
    </div>
</header>

<main class="main">

    <div class="section-head">
        <span class="section-title">Ledger Balances</span>
        <div class="section-line"></div>
    </div>

    <div class="balances-row">
        {balance_cards}
        <div class="outbox-card">
            <div class="balance-label">Outbox Queue</div>
            <div class="outbox-count">{display_outbox}</div>
            <div class="balance-sub">Pending sync</div>
        </div>
    </div>

    <div class="section-head">
        <span class="section-title">Transactions</span>
        <div class="section-line"></div>
    </div>

    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>TX ID</th>
                    {('<th>Tenant</th>' if show_tenant_col else '')}
                    <th>Ext. Ref</th>
                    <th>Merchant</th>
                    <th style="text-align:right">Amount</th>
                    <th>Status</th>
                    <th>Account Code</th>
                    <th>Action</th>
                    <th>Notes</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        <div class="footer-bar">
            <div class="footer-stat">
                <span>{tx_count} transaction{'s' if tx_count != 1 else ''}</span>
            </div>
            <div class="footer-live">
                <div class="live-dot"></div>
                <span>Real-time · auto-refreshes every 5s</span>
            </div>
        </div>
    </div>

</main>
</div>

<script>
/* ── tenant switcher ── */
function switchTenant() {{
    var val = document.getElementById('tenantSelect').value;
    var url = new URL(window.location.href);
    url.searchParams.set('tenant_id', val);
    window.location.href = url.toString();
}}

/* ── auto-refresh (pause when dropdown focused) ── */
setTimeout(function() {{
    if (document.activeElement !== document.getElementById('tenantSelect')) {{
        location.reload();
    }}
}}, 5000);

/* ── notes popover (JS-powered, fixed positioning — avoids all clipping) ── */
(function() {{
    var pop   = document.getElementById('notes-popover');
    var GAP   = 8;   // px gap between cell top and popover bottom
    var hideTimer;

    function showPopover(cell) {{
        clearTimeout(hideTimer);
        var text = cell.getAttribute('data-notes') || '';
        if (!text || text === '—') return;

        pop.textContent = text;
        pop.classList.add('visible');

        /* Position: above the cell, arrow at left edge */
        var rect = cell.getBoundingClientRect();

        /* Tentative left: align to cell left */
        var left = rect.left;
        /* Make sure it doesn't overflow the viewport on the right */
        var popW = Math.min(320, window.innerWidth - 20);
        if (left + popW > window.innerWidth - 8) {{
            left = window.innerWidth - popW - 8;
        }}
        if (left < 8) left = 8;

        /* Position above the row */
        var top = rect.top + window.scrollY - pop.offsetHeight - GAP;
        if (top < window.scrollY + 8) {{
            /* Not enough room above — show below instead */
            top = rect.bottom + window.scrollY + GAP;
            pop.style.setProperty('--arrow-top', '1');
        }} else {{
            pop.style.removeProperty('--arrow-top');
        }}

        pop.style.left = left + 'px';
        pop.style.top  = top  + 'px';
    }}

    function hidePopover() {{
        hideTimer = setTimeout(function() {{
            pop.classList.remove('visible');
        }}, 80);
    }}

    /* Mark cells that are actually overflowing */
    document.querySelectorAll('.comment-cell').forEach(function(cell) {{
        if (cell.scrollWidth > cell.clientWidth) {{
            cell.classList.add('has-overflow');
        }}
        cell.addEventListener('mouseenter', function() {{ showPopover(cell); }});
        cell.addEventListener('mouseleave', hidePopover);
        cell.addEventListener('mousemove', function(e) {{
            /* Keep popover anchored to cell, no need to follow cursor */
        }});
    }});

    /* Always show popover on hover (even if not truncated — full text is helpful) */
    document.querySelectorAll('.comment-cell').forEach(function(cell) {{
        cell.addEventListener('mouseenter', function() {{ showPopover(cell); }});
        cell.addEventListener('mouseleave', hidePopover);
    }});
}})();
</script>
</body>
</html>"""