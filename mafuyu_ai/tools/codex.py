"""Explicitly privileged local execution and Codex bridge tools."""

import json
import subprocess
import time
from pathlib import Path

from mafuyu_ai.settings import (
    CODEX_BRIDGE_DIR,
    CODEX_CMD,
    CODEX_LOG_TAIL_LINES,
    ENABLE_CODEX_TOOLS,
    ENABLE_LOCAL_PYTHON_TOOL,
    LOGS_DIR,
)
from mafuyu_ai.tools.safety import safe_path


def _codex_bridge_paths() -> tuple[Path, Path, Path]:
    """Codex bridge 用の入出力ファイルを sandbox 配下にまとめる。"""
    bridge_dir = CODEX_BRIDGE_DIR
    bridge_dir.mkdir(parents=True, exist_ok=True)
    return (
        bridge_dir,
        bridge_dir / "request.json",
        bridge_dir / "output.log",
    )


# ============ Codex Job Tools ============

# Global job registry
_codex_jobs: dict[str, dict] = {}


def codex_job_start(prompt: str, workdir: str = ".") -> dict:
    """
    Codex CLI を別プロセスで起動し、ログファイルへ出力を流す。

    以前は shell=True で起動していたが、コマンドインジェクション面を減らすため
    いまは shell=False で直接実行している。
    """
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    import uuid

    job_id = uuid.uuid4().hex[:8]
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"codex_{job_id}.log"

    try:
        safe_workdir = safe_path(workdir)
        # Build command with non-interactive mode
        cmd = [CODEX_CMD, "-a", "never", prompt]

        # Open log file
        log_file = open(log_path, "w", encoding="utf-8")

        # Start process
        process = subprocess.Popen(
            cmd,
            cwd=str(safe_workdir),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            shell=False,
            text=True,
        )

        _codex_jobs[job_id] = {
            "process": process,
            "log_file": log_file,
            "log_path": str(log_path),
            "prompt": prompt,
            "workdir": str(safe_workdir),
        }

        return {"job_id": job_id, "log_path": str(log_path), "started": True}
    except Exception as e:
        return {"error": f"codex_job_start failed: {e}"}


def codex_job_status(job_id: str) -> dict:
    """Get status and last N lines of Codex job."""
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    if job_id not in _codex_jobs:
        return {"error": f"Job not found: {job_id}"}

    job = _codex_jobs[job_id]
    process = job["process"]
    log_path = Path(job["log_path"])

    # Check if running
    poll = process.poll()
    state = "running" if poll is None else "done"
    exit_code = poll

    # Read last N lines
    last_lines = []
    if log_path.exists():
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
            last_lines = lines[-CODEX_LOG_TAIL_LINES:]
        except Exception:
            pass

    return {
        "job_id": job_id,
        "state": state,
        "exit_code": exit_code,
        "last_lines": last_lines,
    }


def codex_job_stop(job_id: str) -> dict:
    """Stop Codex job."""
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    if job_id not in _codex_jobs:
        return {"error": f"Job not found: {job_id}"}

    job = _codex_jobs[job_id]
    process = job["process"]

    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

    # Close log file
    try:
        job["log_file"].close()
    except Exception:
        pass

    return {"job_id": job_id, "stopped": True}


def run_python_code(code: str) -> dict:
    """
    Execute a snippet of Python code and capture the output.
    Useful for calculations, logic verification, or data processing.
    """
    if not ENABLE_LOCAL_PYTHON_TOOL:
        return {
            "success": False,
            "output": "run_python_code is disabled by default.",
            "exit_code": -1,
        }

    try:
        # Run safely? Well, it's local execution.
        print(f"[Python] Executing code:\n{code[:80]}...")

        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=30,  # Safety timeout
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"

        success = result.returncode == 0

        return {"success": success, "output": output, "exit_code": result.returncode}
    except Exception as e:
        return {
            "success": False,
            "output": f"Python execution failed: {e}",
            "exit_code": -1,
        }


def codex_run_captured(prompt: str, workdir: str = ".") -> dict:
    """
    Start a new task on the Codex Bridge (Interactive Mode).
    Returns immediately after sending the request.
    Use 'codex_read_output' to see progress.
    """
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    _, request_file, _ = _codex_bridge_paths()

    req_data = {"prompt": prompt}

    try:
        with request_file.open("w", encoding="utf-8") as f:
            json.dump(req_data, f, ensure_ascii=False, indent=2)

        # We wait a brief moment to let Bridge pick it up?
        time.sleep(1)
        return {
            "success": True,
            "output": "Task sent to Bridge. Check output with 'codex_read_output'.",
            "exit_code": 0,
        }

    except Exception as e:
        return {"success": False, "output": f"Error sending task: {e}", "exit_code": -1}


def codex_read_output(lines: int = 20) -> dict:
    """
    Read the latest output from the Codex Bridge.
    """
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    _, _, output_file = _codex_bridge_paths()

    if not output_file.exists():
        return {"success": True, "output": "(No output log found yet)", "exit_code": 0}

    try:
        with output_file.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read().splitlines()

        tail = "\n".join(content[-max(1, lines) :])
        return {"success": True, "output": tail, "exit_code": 0}
    except Exception as e:
        return {"success": False, "output": f"Error reading log: {e}", "exit_code": -1}


def codex_send_input(text: str) -> dict:
    """
    Send text input (e.g. 'yes', 'no') to the running Codex task.
    """
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    bridge_dir, _, _ = _codex_bridge_paths()
    input_file = bridge_dir / "input.txt"

    try:
        with input_file.open("w", encoding="utf-8") as f:
            f.write(text)
        return {"success": True, "output": f"Sent input: {text}", "exit_code": 0}
    except Exception as e:
        return {
            "success": False,
            "output": f"Error sending input: {e}",
            "exit_code": -1,
        }


def codex_run_sync(prompt: str, workdir: str = ".") -> dict:
    """
    新しい PowerShell ウィンドウで Codex を起動する。

    prompt はそのままコマンド文字列へ埋め込まず、Base64 で PowerShell 側へ渡して
    復元する。これで quoting 崩れや文字列連結ベースの注入リスクを抑える。

    Args:
        prompt: Task description for Codex
        workdir: Working directory

    Returns:
        {"success": bool, "output": str, "exit_code": int}
    """
    if not ENABLE_CODEX_TOOLS:
        return {
            "success": False,
            "output": "Codex tools are disabled by default.",
            "exit_code": -1,
        }

    try:
        import base64

        safe_workdir = safe_path(workdir)

        # 引数を PowerShell の文字列連結に直接入れないため、Base64 で渡す。
        prompt_b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
        codex_cmd_literal = CODEX_CMD.replace("'", "''")
        ps_script = (
            "$prompt = [System.Text.Encoding]::UTF8.GetString("
            f"[System.Convert]::FromBase64String('{prompt_b64}')); "
            f"$codex = '{codex_cmd_literal}'; "
            "Start-Process -FilePath $codex "
            "-ArgumentList @('-a', 'never', $prompt) "
            "-NoNewWindow -Wait; "
            "Write-Host 'Done! You can close this window.' -ForegroundColor Green"
        )

        print(f"\n{'=' * 50}")
        print(f"[Codex] Spawning new window for task: {prompt[:80]}...")
        print(f"{'=' * 50}\n")

        # shell=False のまま新しいコンソールを開く。
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", ps_script],
            cwd=str(safe_workdir),
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )

        return {
            "success": True,
            "output": "Codexを新しいウィンドウで起動したよ！そっちを確認してね。",
            "exit_code": 0,
        }

    except Exception as e:
        return {"success": False, "output": f"Codex launch error: {e}", "exit_code": -1}
