import os
import stat
import subprocess
from pathlib import Path


ARTIFACT_NAMES = ("index.html", "index.js", "index.wasm", "index.pck")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _clear_output_artifacts(output_dir: Path) -> None:
    for artifact_name in ARTIFACT_NAMES:
        artifact_path = output_dir / artifact_name
        if artifact_path.exists():
            artifact_path.unlink()


def test_export_script_creates_required_artifacts(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "export_godot_web.sh"
    output_dir = repo_root / "commander-dashboard" / "public" / "godot"
    _clear_output_artifacts(output_dir)

    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir(parents=True)
    fake_godot = fake_bin_dir / "godot"
    _write_executable(
        fake_godot,
        """#!/usr/bin/env bash
set -euo pipefail
output_path="${!#}"
output_dir="$(dirname "$output_path")"
mkdir -p "$output_dir"
touch "$output_path"
touch "${output_dir}/index.js" "${output_dir}/index.wasm" "${output_dir}/index.pck"
""",
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin_dir}:{env['PATH']}"

    subprocess.run([str(script_path)], cwd=repo_root, env=env, check=True)

    assert (output_dir / "index.js").exists()
    assert (output_dir / "index.wasm").exists()
    assert (output_dir / "index.pck").exists()


def test_export_script_fails_without_required_artifacts(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "export_godot_web.sh"
    output_dir = repo_root / "commander-dashboard" / "public" / "godot"
    _clear_output_artifacts(output_dir)

    fake_bin_dir = tmp_path / "bin"
    fake_bin_dir.mkdir(parents=True)
    fake_godot = fake_bin_dir / "godot"
    _write_executable(
        fake_godot,
        """#!/usr/bin/env bash
set -euo pipefail
output_path="${!#}"
output_dir="$(dirname "$output_path")"
mkdir -p "$output_dir"
touch "$output_path"
touch "${output_dir}/index.js" "${output_dir}/index.wasm"
""",
    )

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin_dir}:{env['PATH']}"

    result = subprocess.run([str(script_path)], cwd=repo_root, env=env, check=False, capture_output=True, text=True)

    assert result.returncode != 0
    assert "index.pck" in result.stderr
