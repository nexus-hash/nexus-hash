"""Rebuild the open-source contributions section of README.md.

Finds merged PRs authored by USERNAME in repos the user does not own,
groups them by repo, and writes a table between the OSS markers.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from collections import defaultdict

USERNAME = os.environ.get("GH_USERNAME", "nexus-hash")
TOKEN = os.environ["GITHUB_TOKEN"]
README = "README.md"
START, END = "<!-- OSS-START -->", "<!-- OSS-END -->"
MAX_REPOS = 8
MAX_PRS_PER_REPO = 3


def gh(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def merged_prs():
    q = f"is:pr is:merged author:{USERNAME} -user:{USERNAME}"
    prs, page = [], 1
    while True:
        qs = urllib.parse.urlencode({"q": q, "sort": "updated", "per_page": 100, "page": page})
        batch = gh(f"/search/issues?{qs}")["items"]
        prs += batch
        if len(batch) < 100 or page == 10:
            return prs
        page += 1


def render(prs):
    if not prs:
        return "_First merged PRs incoming — check back soon._ 🚧"

    by_repo = defaultdict(list)
    for pr in prs:
        repo = pr["repository_url"].removeprefix("https://api.github.com/repos/")
        by_repo[repo].append(pr)

    repos = []
    for name, items in by_repo.items():
        meta = gh(f"/repos/{name}")
        repos.append((meta["stargazers_count"], name, meta, items))
    # Rank by number of merged PRs, then by repo popularity.
    repos.sort(key=lambda r: (len(r[3]), r[0]), reverse=True)

    orgs = sorted({name.split("/")[0] for _, name, _, _ in repos})
    lines = [
        f"**{len(prs)}** merged PRs across **{len(repos)}** repos "
        f"in **{len(orgs)}** orgs",
        "",
        "| Repository | ⭐ | Merged PRs | Recent |",
        "|---|---|---|---|",
    ]
    for stars, name, meta, items in repos[:MAX_REPOS]:
        recent = "<br>".join(
            f"[#{pr['number']}]({pr['html_url']}) {pr['title'].replace('|', '/')}"
            for pr in items[:MAX_PRS_PER_REPO]
        )
        all_prs = (
            f"https://github.com/{name}/pulls?q=is%3Apr+is%3Amerged+author%3A{USERNAME}"
        )
        lines.append(
            f"| [{name}]({meta['html_url']}) | {stars:,} | [{len(items)}]({all_prs}) | {recent} |"
        )
    return "\n".join(lines)


def main():
    with open(README) as f:
        readme = f.read()
    section = f"{START}\n{render(merged_prs())}\n{END}"
    updated = re.sub(f"{START}.*?{END}", lambda _: section, readme, flags=re.S)
    with open(README, "w") as f:
        f.write(updated)


if __name__ == "__main__":
    main()
