import os
import subprocess
from pathlib import Path


def _write_mock_git(bin_dir: Path, behavior: str) -> None:
    git_path = bin_dir / "git"
    if behavior == "success":
        body = """#!/bin/bash
set -euo pipefail
if [ \"$1\" = \"clone\" ]; then
  dest=\"${@: -1}\"
  mkdir -p \"$dest\"
  cat > \"$dest/Cargo.toml\" <<'TOML'
[package]
name = \"synapse-engine\"
version = \"0.0.0\"
TOML
  mkdir -p \"$dest/.git\"
  exit 0
fi
exit 1
"""
    elif behavior == "failure":
        body = """#!/bin/bash
exit 1
"""
    else:
        raise ValueError("unknown behavior")
    git_path.write_text(body)
    git_path.chmod(0o755)


def _run_script(tmp_path: Path, path_with_mock_git: str) -> subprocess.CompletedProcess[str]:
    script = Path("scripts/ensure_synapse_engine.sh").resolve()
    env = os.environ.copy()
    env["PATH"] = path_with_mock_git
    env["SYNAPSE_ENGINE_DIR"] = str(tmp_path / "synapse-engine")
    env["SYNAPSE_ENGINE_VENDOR_DIR"] = str(tmp_path / "vendor" / "synapse-engine")
    return subprocess.run(["bash", str(script)], cwd=tmp_path, env=env, text=True, capture_output=True)


def test_uses_existing_checkout_without_git(tmp_path: Path) -> None:
    synapse_dir = tmp_path / "synapse-engine"
    synapse_dir.mkdir()
    (synapse_dir / "Cargo.toml").write_text("[package]\nname='x'\n")

    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    _write_mock_git(mock_bin, "failure")

    result = _run_script(tmp_path, f"{mock_bin}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert "checkout found" in result.stdout


def test_clone_success_updates_vendor_snapshot(tmp_path: Path) -> None:
    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    _write_mock_git(mock_bin, "success")

    result = _run_script(tmp_path, f"{mock_bin}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert (tmp_path / "synapse-engine" / "Cargo.toml").exists()
    assert (tmp_path / "vendor" / "synapse-engine" / "Cargo.toml").exists()
    assert not (tmp_path / "vendor" / "synapse-engine" / ".git").exists()


def test_falls_back_to_vendor_when_clone_fails(tmp_path: Path) -> None:
    vendor_dir = tmp_path / "vendor" / "synapse-engine"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "Cargo.toml").write_text("[package]\nname='fallback'\n")

    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    _write_mock_git(mock_bin, "failure")

    result = _run_script(tmp_path, f"{mock_bin}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert "vendored fallback" in result.stdout
    assert (tmp_path / "synapse-engine" / "Cargo.toml").read_text().find("fallback") != -1


def test_existing_checkout_refreshes_vendor_snapshot(tmp_path: Path) -> None:
    synapse_dir = tmp_path / "synapse-engine"
    synapse_dir.mkdir()
    (synapse_dir / "Cargo.toml").write_text("[package]\nname='fresh'\n")

    vendor_dir = tmp_path / "vendor" / "synapse-engine"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "Cargo.toml").write_text("[package]\nname='stale'\n")

    mock_bin = tmp_path / "bin"
    mock_bin.mkdir()
    _write_mock_git(mock_bin, "failure")

    result = _run_script(tmp_path, f"{mock_bin}:{os.environ['PATH']}")

    assert result.returncode == 0
    assert "Updating vendor fallback" in result.stdout
    assert (vendor_dir / "Cargo.toml").read_text().find("fresh") != -1
