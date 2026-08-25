#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI, then run: gh auth login" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login" >&2
  exit 1
fi

OWNER="$(gh api user --jq .login)"
REPO="questrock-spanish-whispy"
ROOT="$(pwd)"

python3 - "$OWNER" "$REPO" "$ROOT" <<'PY'
import json
import pathlib
import re
import sys

owner, repo, root_s = sys.argv[1], sys.argv[2], sys.argv[3]
root = pathlib.Path(root_s)
(root / "docs" / "repo.json").write_text(
    json.dumps({"owner": owner, "repo": repo}, indent=2) + "\n", encoding="utf-8"
)
pkg_path = root / "electron" / "package.json"
pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
pkg["homepage"] = f"https://{owner}.github.io/{repo}/"
pkg["repository"] = {
    "type": "git",
    "url": f"https://github.com/{owner}/{repo}.git",
}
pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
yml_path = root / "electron" / "electron-builder.yml"
yml = yml_path.read_text(encoding="utf-8")
yml = re.sub(r"(?m)^  owner: .*$", f"  owner: {owner}", yml, count=1)
yml = re.sub(r"(?m)^  repo: .*$", f"  repo: {repo}", yml, count=1)
yml_path.write_text(yml, encoding="utf-8")
print(f"{owner}/{repo}")
PY

if gh repo view "${OWNER}/${REPO}" >/dev/null 2>&1; then
  echo "Repo ${OWNER}/${REPO} already exists."
else
  gh repo create "${OWNER}/${REPO}" --public --source=. --remote=origin \
    --description "QuestRock AI Assistant - local Spanish call captions"
fi

echo "Add the origin remote if needed, then enable GitHub Pages: Settings → Pages → Deploy from branch main / docs."
echo "Ship an update with: bump electron/package.json version, commit, git tag vX.Y.Z, git push origin vX.Y.Z"
