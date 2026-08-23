#!/usr/bin/env python3
"""Build a self-contained HTML dashboard from PR data."""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

DATA_PATH = "data/all-prs.json"
CONFIG_PATH = "config.json"
OUTPUT_PATH = "docs/index.html"


def load_data():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH) as f:
        return json.load(f)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def normalize_state(pr):
    s = pr.get("state", "").lower()
    if s == "merged":
        return "merged"
    if s == "open":
        return "open"
    return "closed"


def build_heatmap_data(prs, earliest_join):
    by_day = defaultdict(int)
    for pr in prs:
        by_day[pr["createdAt"][:10]] += 1

    today = datetime.now(timezone.utc).date()
    join = datetime.strptime(earliest_join, "%Y-%m-%d").date()
    start = join - timedelta(days=join.isoweekday() % 7)
    min_weeks = 12
    if (today - start).days < min_weeks * 7:
        start = today - timedelta(weeks=min_weeks) - timedelta(days=today.isoweekday() % 7)

    weeks = []
    current = start
    while current <= today:
        week = []
        for d in range(7):
            day = current + timedelta(days=d)
            day_str = day.strftime("%Y-%m-%d")
            count = by_day.get(day_str, 0)
            week.append({
                "date": day_str,
                "count": count,
                "future": day > today,
                "preJoin": day < join,
            })
        weeks.append(week)
        current += timedelta(weeks=1)

    return weeks


def main():
    prs = load_data()
    config = load_config()

    earliest_join = min(o["joined"] for o in config["orgs"]) if config["orgs"] else "2026-01-01"
    heatmap = build_heatmap_data(prs, earliest_join)

    total = len(prs)
    merged = sum(1 for p in prs if normalize_state(p) == "merged")
    open_count = sum(1 for p in prs if normalize_state(p) == "open")
    closed_count = total - merged - open_count
    repos = len(set(pr["repository"]["name"] for pr in prs)) if prs else 0

    first_date = prs[-1]["createdAt"][:10] if prs else "—"
    last_date = prs[0]["createdAt"][:10] if prs else "—"

    org_labels = {o["name"]: o.get("label", o["name"]) for o in config["orgs"]}
    repo_url = f"https://github.com/{config['author']}/pr-tracker"
    now_str = datetime.now(timezone.utc).strftime("%b %d, %Y")

    # Pre-build settings org list (avoids nested f-string quote issues)
    settings_orgs_html = ""
    for o in config["orgs"]:
        label = org_labels.get(o["name"], o["name"])
        settings_orgs_html += (
            f'<div class="sp-org"><div>'
            f'<div class="name">{label}</div>'
            f'<div class="joined">Joined {o["joined"]} &middot; {o["name"]}</div>'
            f'</div></div>'
        )

    org_pills_html = ""
    for o in config["orgs"]:
        label = org_labels.get(o["name"], o["name"])
        org_pills_html += f'<div class="pill" data-org="{o["name"]}">{label}</div>'

    pr_json = json.dumps([
        {
            "repo": pr["repository"]["name"],
            "org": pr.get("org", ""),
            "title": pr["title"],
            "number": pr["number"],
            "state": normalize_state(pr),
            "created": pr["createdAt"][:10],
            "month": pr["createdAt"][:7],
            "url": pr["url"],
        }
        for pr in prs
    ])

    repo_list = sorted(
        set(pr["repository"]["name"] for pr in prs),
        key=lambda r: -sum(1 for p in prs if p["repository"]["name"] == r)
    ) if prs else []

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{config["dashboard"]["title"]}</title>
<style>
@font-face{{font-family:'Geist';src:url('fonts/Geist-Variable.woff2') format('woff2');font-weight:100 900;font-style:normal;font-display:swap}}
@font-face{{font-family:'Geist Mono';src:url('fonts/GeistMono-Variable.woff2') format('woff2');font-weight:100 900;font-style:normal;font-display:swap}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --font-sans:'Geist',-apple-system,BlinkMacSystemFont,sans-serif;
  --font-mono:'Geist Mono',ui-monospace,SFMono-Regular,monospace;
  --bg:#1c1917;--surface:#231f1c;--surface-2:#2a2522;--border:rgba(245,240,235,.1);
  --border-strong:rgba(245,240,235,.2);
  --text:#f5f0eb;--text-muted:#a8a29e;--text-dim:#57534e;
  --accent:#f5f0eb;
  --teal:#6ec6a5;--teal-muted:rgba(110,198,165,.12);
  --amber:#d4a843;--amber-muted:rgba(212,168,67,.12);
  --stone:#a8a29e;--stone-muted:rgba(168,162,158,.1);
  --hm-0:#231f1c;--hm-1:#302818;--hm-2:#4d3e1c;--hm-3:#7a6224;--hm-4:#d4a843;
  --hm-pre:#171412;
  --radius:6px;
}}
body{{font-family:var(--font-sans);background:var(--bg);color:var(--text);
  line-height:1.6;min-height:100vh;font-size:15px;-webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility}}

.shell{{max-width:1080px;margin:0 auto;padding:32px 24px 80px}}

/* Header */
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:28px}}
.hdr-left h1{{font-size:20px;font-weight:600;letter-spacing:-.02em}}
.hdr-left .sub{{font-size:13px;color:var(--text-muted);margin-top:2px}}
.hdr-right{{display:flex;gap:8px;align-items:center}}
.hdr-btn{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  color:var(--text-muted);padding:5px 10px;font-size:12px;cursor:pointer;display:flex;align-items:center;gap:5px;
  transition:border-color .15s}}
.hdr-btn:hover{{border-color:var(--text-muted)}}
.hdr-btn svg{{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.5}}

/* Stat strip */
.stats{{display:flex;gap:24px;margin-bottom:28px;flex-wrap:wrap}}
.stat{{display:flex;align-items:baseline;gap:6px}}
.stat .n{{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}}
.stat .l{{font-size:12px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em}}
.stat.merged .n{{color:var(--teal)}}
.stat.open .n{{color:var(--amber)}}

/* Filters */
.filters{{display:flex;gap:6px;margin-bottom:24px;flex-wrap:wrap;align-items:center}}
.pill{{padding:3px 10px;border-radius:14px;font-size:12px;cursor:pointer;
  background:transparent;border:1px solid var(--border);color:var(--text-muted);transition:all .15s;
  white-space:nowrap}}
.pill:hover{{border-color:var(--text-muted)}}
.pill.active{{background:var(--amber);color:var(--bg);border-color:var(--amber)}}
.filter-sep{{width:1px;height:16px;background:var(--border);margin:0 4px}}
.filter-select{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  color:var(--text);padding:3px 8px;font-size:12px;cursor:pointer}}

/* Heatmap */
.section{{margin-bottom:28px}}
.section-title{{font-size:13px;font-weight:500;color:var(--text-muted);margin-bottom:10px;
  text-transform:uppercase;letter-spacing:.05em}}
.hm-graph{{display:flex}}
.hm-day-labels{{display:flex;flex-direction:column;gap:3px;padding-top:22px;padding-right:8px;flex-shrink:0}}
.hm-day-labels .hm-dl{{height:16px;font-size:11px;color:var(--text-dim);display:flex;align-items:center;line-height:1}}
.hm-scroll{{overflow-x:auto;padding-bottom:4px;flex:1}}
.hm-month-row{{display:flex;gap:3px;height:18px;margin-bottom:4px}}
.hm-month-slot{{width:16px;flex-shrink:0;font-size:11px;color:var(--text-dim);white-space:nowrap}}
.hm-cells{{display:flex;gap:3px}}
.hm-week{{display:flex;flex-direction:column;gap:3px}}
.hm-cell{{width:16px;height:16px;border-radius:2px;background:var(--hm-0);cursor:pointer;transition:outline-color .1s;
  display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:600;color:transparent;font-variant-numeric:tabular-nums}}
.hm-cell.has-count{{color:var(--bg)}}.hm-cell.l1.has-count,.hm-cell.l2.has-count{{color:var(--text-muted)}}
.hm-cell.future{{background:transparent;cursor:default}}
.hm-cell.pre-join{{background:var(--hm-pre);cursor:default}}
.hm-cell.l1{{background:var(--hm-1)}}.hm-cell.l2{{background:var(--hm-2)}}
.hm-cell.l3{{background:var(--hm-3)}}.hm-cell.l4{{background:var(--hm-4)}}
.hm-cell:not(.future):not(.pre-join):hover{{outline:1.5px solid var(--amber);outline-offset:1px}}
.hm-cell.selected{{outline:2px solid var(--amber);outline-offset:1px}}
.hm-footer{{display:flex;justify-content:space-between;margin-top:8px;font-size:10px;color:var(--text-dim)}}
.hm-legend{{display:flex;gap:3px;align-items:center;font-size:10px;color:var(--text-dim)}}
.hm-legend .sw{{width:12px;height:12px;border-radius:2px}}

/* Day detail popover */
.day-detail{{background:var(--surface);border:1px solid var(--border);border-radius:8px;
  padding:12px 14px;margin-top:10px;display:none;max-height:260px;overflow-y:auto}}
.day-detail.open{{display:block}}
.day-detail .dd-title{{font-size:13px;font-weight:500;margin-bottom:8px;display:flex;
  justify-content:space-between;align-items:center}}
.day-detail .dd-title span{{color:var(--text-dim);font-weight:400}}
.day-detail .dd-close{{cursor:pointer;color:var(--text-dim);font-size:16px;line-height:1}}
.day-detail .dd-close:hover{{color:var(--text)}}
.dd-item{{display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border);
  font-size:13px}}
.dd-item:last-child{{border:none}}
.dd-item .dd-badge{{display:inline-block;width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.dd-item .dd-badge.merged{{background:var(--teal)}}.dd-item .dd-badge.open{{background:var(--amber)}}
.dd-item .dd-badge.closed{{background:var(--stone)}}
.dd-item a{{color:var(--text);text-decoration:none}}.dd-item a:hover{{color:var(--amber)}}
.dd-item .dd-repo{{color:var(--text-dim);font-size:11px;margin-left:auto;flex-shrink:0}}
.dd-empty{{color:var(--text-dim);font-size:13px;padding:4px 0}}

/* Charts row */
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:28px}}
@media(max-width:700px){{.charts{{grid-template-columns:1fr}}}}

.chart-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px}}
.chart-card .section-title{{margin-bottom:8px}}

.bar-chart{{display:flex;flex-direction:column;gap:5px}}
.bar-row{{display:flex;align-items:center;gap:8px;font-size:12px}}
.bar-label{{width:170px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  flex-shrink:0;color:var(--text-muted)}}
.bar-track{{flex:1;height:18px;background:var(--surface-2);border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px;background:var(--amber);opacity:.7;transition:width .3s}}
.bar-count{{width:28px;text-align:right;font-variant-numeric:tabular-nums;color:var(--text-dim);font-size:11px}}

.month-chart{{display:flex;align-items:flex-end;gap:4px;height:110px;min-width:fit-content}}
.month-col{{display:flex;flex-direction:column;align-items:center;flex:1;min-width:32px}}
.month-bar-wrap{{width:20px;display:flex;flex-direction:column;justify-content:flex-end;flex:1}}
.month-bar{{border-radius:3px 3px 0 0;min-height:2px;background:var(--amber);opacity:.7;cursor:default}}
.month-bar:hover{{opacity:1}}
.month-num{{font-size:10px;color:var(--text-dim);margin-top:4px;font-variant-numeric:tabular-nums}}
.month-lbl{{font-size:10px;color:var(--text-dim);margin-top:1px}}

/* Table */
.table-controls{{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center}}
.table-input{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  color:var(--text);padding:5px 10px;font-size:12px;outline:none;flex:1;min-width:180px}}
.table-input:focus{{border-color:var(--amber)}}
.table-input::placeholder{{color:var(--text-dim)}}
.tbl-count{{font-size:11px;color:var(--text-dim);margin-left:auto}}
.table-wrap{{border:1px solid var(--border);border-radius:8px;background:var(--surface);
  max-height:520px;overflow:auto}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
thead{{position:sticky;top:0;background:var(--surface);z-index:1}}
th{{text-align:left;padding:7px 12px;font-weight:500;border-bottom:1px solid var(--border);
  color:var(--text-dim);font-size:11px;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;
  user-select:none;white-space:nowrap}}
th:hover{{color:var(--text-muted)}}
th .sa{{margin-left:3px;font-size:9px}}
td{{padding:6px 12px;border-bottom:1px solid var(--border);vertical-align:middle}}
tr:hover td{{background:var(--surface-2)}}
.badge{{display:inline-block;padding:1px 7px;border-radius:10px;font-size:10px;font-weight:500}}
.badge.merged{{background:var(--teal-muted);color:var(--teal)}}
.badge.open{{background:var(--amber-muted);color:var(--amber)}}
.badge.closed{{background:var(--stone-muted);color:var(--stone)}}
td a{{color:var(--text);text-decoration:none}}
td a:hover{{color:var(--amber)}}
.empty-row{{text-align:center;padding:32px;color:var(--text-dim)}}

/* Settings panel */
.settings-overlay{{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;display:none;
  justify-content:flex-end}}
.settings-overlay.open{{display:flex}}
.settings-panel{{width:360px;max-width:90vw;background:var(--bg);border-left:1px solid var(--border);
  padding:24px;overflow-y:auto;display:flex;flex-direction:column;gap:20px}}
.sp-title{{font-size:16px;font-weight:600;display:flex;justify-content:space-between;align-items:center}}
.sp-close{{cursor:pointer;color:var(--text-dim);font-size:20px}}.sp-close:hover{{color:var(--text)}}
.sp-section{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--text-dim);
  margin-bottom:6px}}
.sp-org{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);
  padding:10px 12px;display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.sp-org .name{{font-size:13px;font-weight:500}}.sp-org .joined{{font-size:11px;color:var(--text-dim)}}
.sp-help{{font-size:12px;color:var(--text-muted);line-height:1.6}}
.sp-help a{{color:var(--amber)}}
.sp-help code{{background:var(--surface);padding:1px 5px;border-radius:3px;font-size:11px}}
.sp-note{{font-size:11px;color:var(--text-dim);line-height:1.5;padding:10px 12px;
  background:var(--surface);border-radius:var(--radius);border:1px solid var(--border)}}

.footer{{text-align:center;font-size:11px;color:var(--text-dim);margin-top:40px;
  padding-top:16px;border-top:1px solid var(--border)}}

@media(max-width:640px){{
  .shell{{padding:20px 16px 60px}}
  .bar-label{{width:100px;font-size:11px}}
  .stats{{gap:16px}}.stat .n{{font-size:18px}}
}}
</style>
</head>
<body>
<div class="shell">

<div class="hdr">
  <div class="hdr-left">
    <h1>{config["dashboard"]["title"]}</h1>
    <div class="sub">@{config["author"]} &middot; {first_date} to {last_date} &middot; Updated {now_str}</div>
  </div>
  <div class="hdr-right">
    <button class="hdr-btn" onclick="openSettings()">
      <svg viewBox="0 0 24 24"><path d="M12.22 2h-.44a2 2 0 00-2 2v.18a2 2 0 01-1 1.73l-.43.25a2 2 0 01-2 0l-.15-.08a2 2 0 00-2.73.73l-.22.38a2 2 0 00.73 2.73l.15.1a2 2 0 011 1.72v.51a2 2 0 01-1 1.74l-.15.09a2 2 0 00-.73 2.73l.22.38a2 2 0 002.73.73l.15-.08a2 2 0 012 0l.43.25a2 2 0 011 1.73V20a2 2 0 002 2h.44a2 2 0 002-2v-.18a2 2 0 011-1.73l.43-.25a2 2 0 012 0l.15.08a2 2 0 002.73-.73l.22-.39a2 2 0 00-.73-2.73l-.15-.08a2 2 0 01-1-1.74v-.5a2 2 0 011-1.74l.15-.09a2 2 0 00.73-2.73l-.22-.38a2 2 0 00-2.73-.73l-.15.08a2 2 0 01-2 0l-.43-.25a2 2 0 01-1-1.73V4a2 2 0 00-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
      Settings
    </button>
  </div>
</div>

<div class="stats">
  <div class="stat"><span class="n" id="sTotal">{total}</span><span class="l">PRs</span></div>
  <div class="stat merged"><span class="n" id="sMerged">{merged}</span><span class="l">merged</span></div>
  <div class="stat open"><span class="n" id="sOpen">{open_count}</span><span class="l">open</span></div>
  <div class="stat"><span class="n" id="sRepos">{repos}</span><span class="l">repos</span></div>
</div>

<div class="filters" id="filters">
  <div class="pill active" data-org="all">All orgs</div>
  {org_pills_html}
  <div class="filter-sep"></div>
  <select class="filter-select" id="yearFilter"><option value="all">All years</option></select>
  <select class="filter-select" id="monthFilter"><option value="all">All months</option></select>
</div>

<div class="section">
  <div class="section-title">Contributions</div>
  <div class="hm-graph">
    <div class="hm-day-labels">
      <div class="hm-dl"></div>
      <div class="hm-dl">Mon</div>
      <div class="hm-dl"></div>
      <div class="hm-dl">Wed</div>
      <div class="hm-dl"></div>
      <div class="hm-dl">Fri</div>
      <div class="hm-dl"></div>
    </div>
    <div class="hm-scroll">
      <div class="hm-month-row" id="heatmapMonths"></div>
      <div class="hm-cells" id="heatmap"></div>
    </div>
  </div>
  <div class="hm-footer">
    <span>Joined {earliest_join}</span>
    <div class="hm-legend">
      <span>Less</span>
      <div class="sw" style="background:var(--hm-0)"></div>
      <div class="sw" style="background:var(--hm-1)"></div>
      <div class="sw" style="background:var(--hm-2)"></div>
      <div class="sw" style="background:var(--hm-3)"></div>
      <div class="sw" style="background:var(--hm-4)"></div>
      <span>More</span>
    </div>
  </div>
  <div class="day-detail" id="dayDetail">
    <div class="dd-title">
      <span id="ddDate"></span>
      <span class="dd-close" id="ddClose">&times;</span>
    </div>
    <div id="ddBody"></div>
  </div>
</div>

<div class="charts">
  <div class="chart-card">
    <div class="section-title">Repositories <span id="repoCount" style="font-weight:400"></span></div>
    <div class="bar-chart" id="repoChart"></div>
  </div>
  <div class="chart-card">
    <div class="section-title">Monthly</div>
    <div class="month-chart" id="monthChart"></div>
  </div>
</div>

<div class="section">
  <div class="section-title">All Pull Requests <span id="tblCount" style="font-weight:400"></span></div>
  <div class="table-controls">
    <input type="text" class="table-input" id="searchInput" placeholder="Search by title or repo...">
    <select class="filter-select" id="stateFilter">
      <option value="all">All states</option>
      <option value="merged">Merged</option>
      <option value="open">Open</option>
      <option value="closed">Closed</option>
    </select>
    <select class="filter-select" id="repoFilter">
      <option value="all">All repos</option>
      {''.join(f'<option value="{r}">{r}</option>' for r in repo_list)}
    </select>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th data-sort="created">Date <span class="sa">&#9660;</span></th>
        <th data-sort="repo">Repo</th>
        <th data-sort="title">Title</th>
        <th data-sort="state">State</th>
      </tr></thead>
      <tbody id="tblBody"></tbody>
    </table>
  </div>
</div>

<div class="footer">
  Auto-updated weekly &middot; <a href="{repo_url}" style="color:var(--text-dim)">Source</a>
</div>

</div><!-- .shell -->

<!-- Settings panel -->
<div class="settings-overlay" id="settingsOverlay">
  <div class="settings-panel">
    <div class="sp-title">Settings <span class="sp-close" onclick="closeSettings()">&times;</span></div>

    <div>
      <div class="sp-section">Tracked Organizations</div>
      {settings_orgs_html}
    </div>

    <div>
      <div class="sp-section">Add an Organization</div>
      <div class="sp-help">
        <p>Option 1: Run the <a href="{repo_url}/actions/workflows/manage-orgs.yml" target="_blank">Manage Orgs</a> workflow from GitHub Actions. Fill in the org name, label, and join date.</p>
        <br>
        <p>Option 2: Edit <a href="{repo_url}/edit/main/config.json" target="_blank">config.json</a> directly on GitHub. Add a new entry to the <code>orgs</code> array.</p>
        <br>
        <p>After adding, run the <a href="{repo_url}/actions/workflows/track-prs.yml" target="_blank">Track PRs</a> workflow with <code>full_backfill: true</code> to fetch historical data.</p>
      </div>
    </div>

    <div>
      <div class="sp-section">If removed from an org</div>
      <div class="sp-note">
        All previously fetched data stays in the repo forever. Future fetches will return empty for that org, but your historical record is preserved. No data is ever deleted.
      </div>
    </div>

    <div>
      <div class="sp-section">PAT Token</div>
      <div class="sp-help">
        The <code>ORG_PAT</code> secret in <a href="{repo_url}/settings/secrets/actions" target="_blank">repo settings</a> needs read access to the org's repos. Update it if you add a new org or rotate tokens.
      </div>
    </div>
  </div>
</div>

<script>
const ALL_PRS = {pr_json};
const HEATMAP = {json.dumps(heatmap)};

let currentOrg = 'all';
let currentYear = 'all';
let currentMonth = 'all';
let currentSort = {{key:'created',dir:-1}};
let selectedDay = null;

function filtered() {{
  return ALL_PRS.filter(p => {{
    if (currentOrg !== 'all' && p.org !== currentOrg) return false;
    if (currentYear !== 'all' && p.created.slice(0,4) !== currentYear) return false;
    if (currentMonth !== 'all' && p.month !== currentMonth) return false;
    return true;
  }});
}}

function updateStats() {{
  const prs = filtered();
  document.getElementById('sTotal').textContent = prs.length;
  document.getElementById('sMerged').textContent = prs.filter(p => p.state==='merged').length;
  document.getElementById('sOpen').textContent = prs.filter(p => p.state==='open').length;
  document.getElementById('sRepos').textContent = new Set(prs.map(p => p.repo)).size;
}}

function populateYearMonth() {{
  const years = [...new Set(ALL_PRS.map(p => p.created.slice(0,4)))].sort();
  const ys = document.getElementById('yearFilter');
  ys.innerHTML = '<option value="all">All years</option>';
  years.forEach(y => {{ ys.innerHTML += '<option value="'+y+'">'+y+'</option>'; }});

  updateMonthOptions();
}}

function updateMonthOptions() {{
  const ms = document.getElementById('monthFilter');
  const prev = ms.value;
  let months;
  if (currentYear !== 'all') {{
    months = [...new Set(ALL_PRS.filter(p => p.created.slice(0,4)===currentYear).map(p => p.month))].sort();
  }} else {{
    months = [...new Set(ALL_PRS.map(p => p.month))].sort();
  }}
  const names = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  ms.innerHTML = '<option value="all">All months</option>';
  months.forEach(m => {{
    const mi = parseInt(m.slice(5));
    ms.innerHTML += '<option value="'+m+'">'+names[mi]+' '+m.slice(0,4)+'</option>';
  }});
  if (months.includes(prev)) ms.value = prev;
  else {{ ms.value = 'all'; currentMonth = 'all'; }}
}}

function renderHeatmap() {{
  const cellsEl = document.getElementById('heatmap');
  const monthsEl = document.getElementById('heatmapMonths');
  cellsEl.innerHTML = '';
  monthsEl.innerHTML = '';
  const prs = filtered();
  const byDay = {{}};
  prs.forEach(p => {{ byDay[p.created] = (byDay[p.created] || 0) + 1; }});

  const mNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let prevMonth = null;

  HEATMAP.forEach((week, wi) => {{
    const firstDate = week[0].date;
    const mi = parseInt(firstDate.slice(5,7)) - 1;
    const ms = document.createElement('div');
    ms.className = 'hm-month-slot';
    if (mi !== prevMonth) {{
      ms.textContent = mNames[mi];
      prevMonth = mi;
    }}
    monthsEl.appendChild(ms);

    const col = document.createElement('div');
    col.className = 'hm-week';
    week.forEach(day => {{
      const d = document.createElement('div');
      const count = byDay[day.date] || 0;
      let cls = 'hm-cell';
      if (day.future) cls += ' future';
      else if (day.preJoin) cls += ' pre-join';
      else if (count === 0) {{}}
      else if (count === 1) cls += ' l1';
      else if (count === 2) cls += ' l2';
      else if (count <= 4) cls += ' l3';
      else cls += ' l4';
      if (count > 0) cls += ' has-count';
      if (selectedDay === day.date) cls += ' selected';
      d.className = cls;
      if (count > 0) d.textContent = count;
      d.dataset.date = day.date;
      d.dataset.count = count;
      d.title = count + ' PR' + (count !== 1 ? 's':'') + ' on ' + day.date;
      if (!day.future && !day.preJoin) {{
        d.addEventListener('click', () => showDayDetail(day.date, byDay[day.date] || 0));
      }}
      col.appendChild(d);
    }});
    cellsEl.appendChild(col);
  }});
}}

function showDayDetail(date, count) {{
  selectedDay = date;
  renderHeatmap();
  const panel = document.getElementById('dayDetail');
  const body = document.getElementById('ddBody');
  document.getElementById('ddDate').textContent = date + ' — ' + count + ' PR' + (count !== 1 ? 's':'');

  const dayPrs = filtered().filter(p => p.created === date);
  if (!dayPrs.length) {{
    body.innerHTML = '<div class="dd-empty">No PRs on this day</div>';
  }} else {{
    body.innerHTML = dayPrs.map(p =>
      '<div class="dd-item">' +
        '<span class="dd-badge ' + p.state + '"></span>' +
        '<a href="' + p.url + '" target="_blank" rel="noopener">' + esc(p.title) + '</a>' +
        '<span class="dd-repo">' + p.repo + '</span>' +
      '</div>'
    ).join('');
  }}
  panel.classList.add('open');
}}

document.getElementById('ddClose').addEventListener('click', () => {{
  document.getElementById('dayDetail').classList.remove('open');
  selectedDay = null;
  renderHeatmap();
}});

function renderRepoChart() {{
  const el = document.getElementById('repoChart');
  el.innerHTML = '';
  const prs = filtered();
  const byRepo = {{}};
  prs.forEach(p => {{ if (!byRepo[p.repo]) byRepo[p.repo]=0; byRepo[p.repo]++; }});
  const sorted = Object.entries(byRepo).sort((a,b) => b[1]-a[1]);
  const max = sorted.length ? sorted[0][1] : 1;
  document.getElementById('repoCount').textContent = '(' + sorted.length + ')';
  sorted.forEach(([repo,count]) => {{
    const row = document.createElement('div');
    row.className = 'bar-row';
    row.innerHTML =
      '<span class="bar-label">' + repo + '</span>' +
      '<div class="bar-track"><div class="bar-fill" style="width:' + (count/max*100) + '%"></div></div>' +
      '<span class="bar-count">' + count + '</span>';
    el.appendChild(row);
  }});
}}

function renderMonthChart() {{
  const el = document.getElementById('monthChart');
  el.innerHTML = '';
  const prs = filtered();
  const byMonth = {{}};
  prs.forEach(p => {{ const m=p.month; if(!byMonth[m])byMonth[m]=0; byMonth[m]++; }});
  const months = Object.keys(byMonth).sort();
  const max = Math.max(...Object.values(byMonth),1);
  const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  months.forEach(m => {{
    const count = byMonth[m];
    const col = document.createElement('div');
    col.className = 'month-col';
    const mi = parseInt(m.slice(5))-1;
    col.innerHTML =
      '<div class="month-bar-wrap">' +
        '<div class="month-bar" style="height:' + (count/max*100) + '%" title="' + names[mi]+' '+m.slice(0,4)+': '+count+' PRs"></div>' +
      '</div>' +
      '<div class="month-num">' + count + '</div>' +
      '<div class="month-lbl">' + names[mi] + '</div>';
    el.appendChild(col);
  }});
}}

function renderTable() {{
  const tbody = document.getElementById('tblBody');
  const search = document.getElementById('searchInput').value.toLowerCase();
  const stateF = document.getElementById('stateFilter').value;
  const repoF = document.getElementById('repoFilter').value;
  let prs = filtered().filter(p => {{
    if (stateF !== 'all' && p.state !== stateF) return false;
    if (repoF !== 'all' && p.repo !== repoF) return false;
    if (search && !p.title.toLowerCase().includes(search) && !p.repo.toLowerCase().includes(search)) return false;
    return true;
  }});
  prs.sort((a,b) => {{
    const av = a[currentSort.key]||'', bv = b[currentSort.key]||'';
    return av < bv ? -currentSort.dir : av > bv ? currentSort.dir : 0;
  }});
  document.getElementById('tblCount').textContent = '(' + prs.length + ')';
  tbody.innerHTML = prs.slice(0,300).map(p =>
    '<tr>' +
      '<td style="white-space:nowrap;font-variant-numeric:tabular-nums;color:var(--text-muted)">' + p.created + '</td>' +
      '<td style="color:var(--text-dim)">' + p.repo + '</td>' +
      '<td><a href="' + p.url + '" target="_blank" rel="noopener">' + esc(p.title) + '</a> <span style="color:var(--text-dim)">#' + p.number + '</span></td>' +
      '<td><span class="badge ' + p.state + '">' + p.state + '</span></td>' +
    '</tr>'
  ).join('');
  if (!prs.length) tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No matching PRs</td></tr>';
}}

function esc(s) {{ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }}

function refresh() {{ updateStats(); renderHeatmap(); renderRepoChart(); renderMonthChart(); renderTable(); }}

document.querySelectorAll('.pill[data-org]').forEach(pill => {{
  pill.addEventListener('click', () => {{
    document.querySelectorAll('.pill[data-org]').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    currentOrg = pill.dataset.org;
    refresh();
  }});
}});

document.getElementById('yearFilter').addEventListener('change', e => {{
  currentYear = e.target.value;
  updateMonthOptions();
  refresh();
}});
document.getElementById('monthFilter').addEventListener('change', e => {{
  currentMonth = e.target.value;
  refresh();
}});

document.querySelectorAll('th[data-sort]').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.sort;
    if (currentSort.key === key) currentSort.dir *= -1;
    else currentSort = {{key, dir: -1}};
    document.querySelectorAll('th .sa').forEach(a => a.textContent = '');
    th.querySelector('.sa').textContent = currentSort.dir === -1 ? '\\u25BC' : '\\u25B2';
    renderTable();
  }});
}});

document.getElementById('searchInput').addEventListener('input', renderTable);
document.getElementById('stateFilter').addEventListener('change', renderTable);
document.getElementById('repoFilter').addEventListener('change', renderTable);

function openSettings() {{ document.getElementById('settingsOverlay').classList.add('open'); }}
function closeSettings() {{ document.getElementById('settingsOverlay').classList.remove('open'); }}
document.getElementById('settingsOverlay').addEventListener('click', e => {{
  if (e.target === e.currentTarget) closeSettings();
}});

populateYearMonth();
refresh();
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    print(f"Dashboard written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
