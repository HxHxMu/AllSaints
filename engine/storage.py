"""Store rendered episodes as GitHub Release assets (public URLs Instagram can fetch)."""
import mimetypes
from pathlib import Path
from common import env, http, log

API = "https://api.github.com"


def _h():
    return {"Authorization": f"Bearer {env('GITHUB_TOKEN', required=True)}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def repo():
    return env("GITHUB_REPOSITORY", required=True)


def get_or_create_release(tag, name=None, body=""):
    r = http.get(f"{API}/repos/{repo()}/releases/tags/{tag}", headers=_h(), timeout=30)
    if r.status_code == 200:
        return r.json()
    r = http.post(f"{API}/repos/{repo()}/releases", headers=_h(), timeout=30,
                  json={"tag_name": tag, "name": name or tag, "body": body, "prerelease": True})
    r.raise_for_status()
    return r.json()


def upload(tag, files, name=None, body=""):
    """files: {asset_name: path}. Returns {asset_name: browser_download_url}."""
    rel = get_or_create_release(tag, name, body)
    existing = {a["name"]: a for a in rel.get("assets", [])}
    urls = {}
    for asset_name, path in files.items():
        if asset_name in existing:
            http.delete(existing[asset_name]["url"], headers=_h(), timeout=30)
        ctype = mimetypes.guess_type(asset_name)[0] or "application/octet-stream"
        up = rel["upload_url"].split("{")[0]
        with open(path, "rb") as f:
            r = http.post(up, params={"name": asset_name}, headers={**_h(), "Content-Type": ctype}, data=f, timeout=600)
        r.raise_for_status()
        urls[asset_name] = r.json()["browser_download_url"]
        log("Uploaded", asset_name)
    return urls


def download(url, dest: Path):
    with http.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return dest


def resolve_direct(url):
    """Follow GitHub's redirect to the direct object URL (some fetchers don't follow redirects)."""
    r = http.head(url, allow_redirects=True, timeout=30)
    return r.url


def dispatch_workflow(workflow_file, inputs=None, ref="main"):
    r = http.post(f"{API}/repos/{repo()}/actions/workflows/{workflow_file}/dispatches", headers=_h(), timeout=30,
                  json={"ref": ref, "inputs": inputs or {}})
    if r.status_code >= 300:
        log("dispatch failed", r.status_code, r.text[:200])
    return r.status_code < 300
