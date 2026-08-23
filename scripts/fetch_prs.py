#!/usr/bin/env python3
"""Fetch PRs across all configured orgs and merge into cumulative data."""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone

CONFIG_PATH = "config.json"
DATA_PATH = "data/all-prs.json"
LAST_RUN_PATH = "data/last-run.txt"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_existing():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            return json.load(f)
    return []


def get_since_date(org_joined):
    full_backfill = os.environ.get("FULL_BACKFILL", "false") == "true"
    if full_backfill:
        return org_joined

    if os.path.exists(LAST_RUN_PATH):
        with open(LAST_RUN_PATH) as f:
            last = f.read().strip()
            if last:
                d = datetime.strptime(last, "%Y-%m-%d") - timedelta(days=3)
                return d.strftime("%Y-%m-%d")

    return org_joined


def fetch_prs_for_org(author, org_name, since):
    print(f"Fetching PRs from {org_name} since {since}...")
    result = subprocess.run(
        [
            "gh", "search", "prs",
            "--author", author,
            "--owner", org_name,
            f"--created=>={since}",
            "--limit", "500",
            "--json", "repository,title,state,createdAt,closedAt,url,number,labels",
        ],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Error fetching from {org_name}: {result.stderr.strip()}")
        return []

    prs = json.loads(result.stdout)
    for pr in prs:
        pr["org"] = org_name

    print(f"  Found {len(prs)} PRs")
    return prs


def merge_prs(existing, new_prs):
    by_url = {pr["url"]: pr for pr in existing}
    for pr in new_prs:
        by_url[pr["url"]] = pr
    return sorted(by_url.values(), key=lambda p: p["createdAt"], reverse=True)


def main():
    config = load_config()
    author = config["author"]
    existing = load_existing()

    all_new = []
    for org in config["orgs"]:
        since = get_since_date(org["joined"])
        prs = fetch_prs_for_org(author, org["name"], since)
        all_new.extend(prs)

    merged = merge_prs(existing, all_new)

    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(merged, f, indent=2)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(LAST_RUN_PATH, "w") as f:
        f.write(today)

    print(f"Total: {len(merged)} PRs across {len(config['orgs'])} org(s)")


if __name__ == "__main__":
    main()
