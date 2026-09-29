"""웹사이트(무료 도구·랜딩페이지) 자동 배포: workspace/site → GitHub Pages 저장소에 push."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _git(cwd: Path, *args) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 실패: {p.stderr.strip()[-300:]}")
    return p.stdout.strip()


def deploy(site_dir: Path, repo_url: str, branch: str, checkout_dir: Path, message: str) -> str:
    if not repo_url:
        raise RuntimeError("site_repo_url 미설정 (data/config.json)")
    if not (site_dir / "index.html").exists():
        raise RuntimeError("workspace/site/index.html 이 없음")
    if not (checkout_dir / ".git").exists():
        checkout_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "-b", branch, repo_url, str(checkout_dir)], check=True)
    else:
        _git(checkout_dir, "pull", "-q", "origin", branch)
    for p in checkout_dir.iterdir():            # .git 외 전부 교체
        if p.name == ".git":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    shutil.copytree(site_dir, checkout_dir, dirs_exist_ok=True)
    _git(checkout_dir, "add", "-A")
    if not _git(checkout_dir, "status", "--porcelain"):
        return "변경 없음"
    _git(checkout_dir, "-c", "user.name=survival-agent", "-c", "user.email=agent@localhost",
         "commit", "-q", "-m", message)
    _git(checkout_dir, "push", "-q", "origin", branch)
    return _git(checkout_dir, "rev-parse", "--short", "HEAD")
