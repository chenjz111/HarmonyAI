#!/usr/bin/env python3
"""
Push 2 new commits via Git Data API (simplified, byte-accurate)
"""
import json
import subprocess
import sys
import urllib.request
import base64
from pathlib import Path

REPO = "chenjz111/HarmonyAI"
BRANCH = "feat/s5-v3.1-frontend-closeout"
COMMITS = ["192a7ca", "e523ac3"]

def get_token():
    creds = Path.home() / ".git-credentials"
    for line in creds.read_text().splitlines():
        if "github.com" in line and "Paimeng835" in line:
            return line.split(":")[2].split("@")[0]
    raise ValueError("Token not found in ~/.git-credentials")

TOKEN = get_token()

def api(method, path, data=None):
    """Call GitHub API"""
    url = f"https://api.github.com{path}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "git-data-api",
    }
    if data:
        data = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except:
            err = {"error": str(e)}
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        raise

def git_cmd(*args):
    """Run git command"""
    return subprocess.run(
        ["git", "-C", "C:/Users/Lenovo/Documents/HarmonyAI"] + list(args),
        capture_output=True,
        text=False,
    )

def upload_blobs_for_commit(sha):
    """Upload all blobs in a commit"""
    # Get diff vs parent
    parent_sha = git_cmd("rev-parse", f"{sha}^").stdout.decode().strip()
    diff = git_cmd("diff-tree", "--raw", parent_sha, sha).stdout.decode().strip()
    
    for line in diff.splitlines():
        parts = line.split()
        if len(parts) >= 6:
            path = "\t".join(parts[5:])
            if parts[4][0] != 'D':  # Not deleted
                # Get the blob SHA
                ls = git_cmd("ls-tree", sha, "--", path).stdout.decode().strip()
                if ls:
                    blob_sha = ls.split()[2]
                    # Try to get blob from remote
                    try:
                        api("GET", f"/repos/{REPO}/git/blobs/{blob_sha}")
                    except:
                        # Upload blob
                        blob_data = git_cmd("cat-file", "blob", blob_sha).stdout
                        print(f"  Uploading blob {blob_sha[:7]} ({len(blob_data)} bytes)")
                        api("POST", f"/repos/{REPO}/git/blobs", {
                            "content": base64.b64encode(blob_data).decode(),
                            "encoding": "base64",
                        })

def push_commit(sha):
    """Push a single commit"""
    print(f"\nProcessing {sha[:7]}...")
    
    # 1. Upload blobs
    print("  Uploading blobs...")
    upload_blobs_for_commit(sha)
    
    # 2. Get commit metadata (raw)
    cat_result = git_cmd("cat-file", "commit", sha)
    if cat_result.returncode != 0:
        raise ValueError(f"Failed to read commit {sha}")
    
    cat_bytes = cat_result.stdout
    cat_text = cat_bytes.decode("utf-8")
    
    # Parse manually to preserve exact formatting
    lines = cat_text.split("\n")
    tree_sha = None
    parents = []
    author_line = None
    committer_line = None
    msg_start = 0
    
    for i, line in enumerate(lines):
        if line.startswith("tree "):
            tree_sha = line.split()[1]
        elif line.startswith("parent "):
            parents.append(line.split()[1])
        elif line.startswith("author "):
            author_line = line[7:]
        elif line.startswith("committer "):
            committer_line = line[10:]
        elif line == "":
            msg_start = i + 1
            break
    
    message = "\n".join(lines[msg_start:])
    
    def parse_person_line(s):
        # "Name <email> timestamp tz"
        parts = s.rsplit(" ", 2)
        name_email = parts[0]
        ts = int(parts[1])
        tz = parts[2]
        
        name, email = name_email.rsplit(" <", 1)
        email = email.rstrip(">")
        
        # Format date
        from datetime import datetime, timezone, timedelta
        tz_sign = 1 if tz[0] == '+' else -1
        tz_h = int(tz[1:3])
        tz_m = int(tz[3:5])
        offset = tz_sign * (tz_h * 60 + tz_m)
        dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(minutes=offset)))
        
        return {"name": name, "email": email, "date": dt.isoformat()}
    
    author = parse_person_line(author_line)
    committer = parse_person_line(committer_line)
    
    # 3. Build tree
    print(f"  Building tree...")
    parent_sha = git_cmd("rev-parse", f"{sha}^").stdout.decode().strip()
    diff = git_cmd("diff-tree", "--raw", parent_sha, sha).stdout.decode().strip()
    
    tree_entries = []
    for line in diff.splitlines():
        parts = line.split()
        mode_before, mode_after = parts[0][:6], parts[0][6:]
        sha_before, sha_after = parts[3], parts[4]
        path = "\t".join(parts[5:])
        
        if parts[4][0] == 'D':
            tree_entries.append({"path": path, "sha": None})
        else:
            tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": sha_after})
    
    tree_resp = api("POST", f"/repos/{REPO}/git/trees", {
        "base_tree": parents[0] if parents else None,
        "tree": tree_entries,
    })
    new_tree = tree_resp["sha"]
    
    if new_tree != tree_sha:
        print(f"  ⚠ Tree mismatch: created {new_tree} but local is {tree_sha}", file=sys.stderr)
        # This might be OK if objects are already uploaded; continue anyway
    
    # 4. Build commit
    print(f"  Building commit...")
    commit_resp = api("POST", f"/repos/{REPO}/git/commits", {
        "message": message,
        "tree": tree_sha,
        "parents": parents,
        "author": author,
        "committer": committer,
    })
    
    remote_sha = commit_resp.get("sha")
    if remote_sha != sha:
        print(f"  ✗ Commit SHA mismatch: remote {remote_sha} != local {sha}", file=sys.stderr)
        raise AssertionError(f"Commit SHA mismatch")
    
    print(f"  ✓ {sha[:7]} created")
    return sha

# Main
try:
    print(f"Pushing {len(COMMITS)} commits to {BRANCH}\n")
    for sha in COMMITS:
        push_commit(sha)
    
    tip = COMMITS[-1]
    print(f"\nUpdating ref to {tip[:7]}...")
    api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {"sha": tip, "force": False})
    
    print("✓ All commits pushed successfully")
except Exception as e:
    print(f"\n✗ Error: {e}", file=sys.stderr)
    sys.exit(1)
