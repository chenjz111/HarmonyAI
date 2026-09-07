# -*- coding: utf-8 -*-
"""Git Data API push for 2 new fix commits on feat/s5-v3.1-frontend-closeout.
Base (already on remote): 0cbe43bbb550e7207e5f0e1a555d2869601e18ad
New commits to push:
  192a7ca - fix: align healing intent contract
  e523ac3 - test: add questionnaire manifest consistency checks
"""
import base64
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "chenjz111/HarmonyAI"
API = "https://api.github.com"
REPO_DIR = r"C:/Users/Lenovo/Documents/HarmonyAI"
BRANCH = "feat/s5-v3.1-frontend-closeout"
BASE_SHA = "0cbe43bbb550e7207e5f0e1a555d2869601e18ad"  # last commit already on remote

COMMITS = [
    "192a7ca",  # fix: healing intent
    "e523ac3",  # test: manifest consistency
]


def die(msg):
    print("ABORT:", msg)
    sys.exit(1)


def get_token():
    for line in open(r"C:/Users/Lenovo/.git-credentials", encoding="utf-8"):
        line = line.strip()
        m = re.match(r"https://[^:]+:([^@]+)@github\.com", line)
        if m:
            return m.group(1)
    die("no token found in ~/.git-credentials")


TOKEN = get_token()


def api_call(method, path, body=None):
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "token " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "harmonyai-push-script")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {}


def git(*args, binary=False):
    r = subprocess.run(["git", "-C", REPO_DIR] + list(args), capture_output=True)
    if r.returncode != 0:
        die("git %s failed: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout if binary else r.stdout.decode("utf-8")


def resolve(sha):
    if len(sha) == 40:
        return sha
    return git("rev-parse", sha).strip()


def commit_meta(sha):
    raw = git("cat-file", "commit", sha, binary=True)
    header, _, message = raw.partition(b"\n\n")
    tree = None
    parents = []
    author = committer = None
    for line in header.decode("utf-8").splitlines():
        if line.startswith("tree "):
            tree = line[5:]
        elif line.startswith("parent "):
            parents.append(line[7:])
        elif line.startswith("author "):
            author = line[7:]
        elif line.startswith("committer "):
            committer = line[10:]

    def parse_ident(s):
        m = re.match(r"(.+) <(.+)> (\d+) ([+-]\d{4})", s)
        if not m:
            die("cannot parse ident: %r" % s)
        name, email, ts, tz = m.groups()
        from datetime import datetime, timedelta, timezone
        sign = 1 if tz[0] == "+" else -1
        delta = timedelta(hours=int(tz[1:3]), minutes=int(tz[3:5])) * sign
        iso = datetime.fromtimestamp(int(ts), tz=timezone(delta)).isoformat()
        return {"name": name, "email": email, "date": iso}

    return {
        "tree": tree,
        "parents": parents,
        "author": parse_ident(author),
        "committer": parse_ident(committer),
        "message": message.decode("utf-8"),
    }


def changed_paths(base, new):
    out = git("diff", "--name-status", base, new)
    entries = []
    for line in out.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        entries.append((parts[0], parts[-1]))
    return entries


def tree_entry(commit, path):
    out = git("ls-tree", commit, "--", path).strip()
    if not out:
        return None
    m = re.match(r"(\d+) blob ([0-9a-f]{40})\t(.+)", out)
    if not m:
        die("unexpected ls-tree output: %r" % out)
    return m.group(1), m.group(2)


def blob_exists_remote(sha):
    status, _ = api_call("GET", "/repos/%s/git/blobs/%s" % (REPO, sha))
    return status == 200


def create_blob(blob_sha):
    content = git("cat-file", "blob", blob_sha, binary=True)
    status, payload = api_call(
        "POST", "/repos/%s/git/blobs" % REPO,
        {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
    )
    if status not in (200, 201):
        die("blob create failed for %s: %s %s" % (blob_sha, status, payload))
    if payload.get("sha") != blob_sha:
        die("blob sha mismatch: local %s remote %s" % (blob_sha, payload.get("sha")))
    print("  blob created %s" % blob_sha[:10])


def build_tree(base_tree, commit, entries, label):
    tree = []
    blobs_needed = []
    for status, path in entries:
        ent = tree_entry(commit, path)
        if status.startswith("D") or ent is None:
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            print("  entry DELETE %s" % path)
            continue
        mode, blob_sha = ent
        if not blob_exists_remote(blob_sha):
            blobs_needed.append(blob_sha)
        tree.append({"path": path, "mode": mode, "type": "blob", "sha": blob_sha})
    for sha in blobs_needed:
        create_blob(sha)
    status, payload = api_call(
        "POST", "/repos/%s/git/trees" % REPO, {"base_tree": base_tree, "tree": tree}
    )
    if status not in (200, 201):
        die("tree create failed (%s): %s %s" % (label, status, json.dumps(payload)[:500]))
    print("  tree created %s (%s)" % (payload.get("sha", "?")[:10], label))
    return payload["sha"]


def create_commit(meta, expected_sha, label):
    body = {
        "message": meta["message"],
        "tree": meta["tree"],
        "parents": meta["parents"],
        "author": meta["author"],
        "committer": meta["committer"],
    }
    status, payload = api_call("POST", "/repos/%s/git/commits" % REPO, body)
    if status not in (200, 201):
        die("commit create failed (%s): %s %s" % (label, status, json.dumps(payload)[:500]))
    remote_sha = payload["sha"]
    print("  commit created %s (%s)" % (remote_sha[:10], label))
    if remote_sha != expected_sha:
        die("SHA MISMATCH for %s: expected %s got %s" % (label, expected_sha, remote_sha))
    print("  SHA MATCHES local: %s" % expected_sha)
    return remote_sha


def update_branch_ref(target_sha, branch):
    status, payload = api_call(
        "PATCH",
        "/repos/%s/git/refs/heads/%s" % (REPO, branch),
        {"sha": target_sha, "force": False},
    )
    if status not in (200, 201):
        die("ref update failed: %s %s" % (status, json.dumps(payload)[:500]))
    print("branch ref updated -> %s" % payload.get("object", {}).get("sha"))


def main():
    # Resolve short shas to full
    full_commits = [resolve(c) for c in COMMITS]
    
    # Verify base exists on remote
    status, _ = api_call("GET", "/repos/%s/git/commits/%s" % (REPO, BASE_SHA))
    if status != 200:
        die("base commit not on remote: %s (HTTP %d)" % (BASE_SHA, status))
    print("Base commit verified: %s" % BASE_SHA[:10])

    # Verify commits exist locally
    for sha in full_commits:
        meta = commit_meta(sha)
        print("Local commit %s: %s" % (sha[:10], meta["message"].splitlines()[0][:60]))

    # Process each commit
    prev_tree = None
    for i, sha in enumerate(full_commits):
        label = "commit%d" % (i + 1)
        meta = commit_meta(sha)
        print("\n== %s: %s ==" % (label, meta["message"].splitlines()[0][:60]))
        
        parent = meta["parents"][0]
        if prev_tree is None:
            base_tree = git("rev-parse", BASE_SHA + "^{tree}").strip()
        else:
            base_tree = prev_tree
        
        entries = changed_paths(parent, sha)
        print("  %d changed paths" % len(entries))
        
        tree_sha = build_tree(base_tree, sha, entries, label)
        if tree_sha != meta["tree"]:
            die("tree mismatch for %s: expected %s got %s" % (label, meta["tree"], tree_sha))
        print("  tree MATCHES local: %s" % tree_sha)
        
        create_commit(meta, sha, label)
        prev_tree = tree_sha

    # Update branch ref
    print("\n== Updating branch ref ==")
    update_branch_ref(full_commits[-1], BRANCH)
    print("\n✓ PUSH-VIA-API SUCCESS")
    print(f"Branch {BRANCH} now points to {full_commits[-1][:10]}")


if __name__ == "__main__":
    main()
