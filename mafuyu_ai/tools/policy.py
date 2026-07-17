"""Model-visible tool policy and runtime allowlists."""

BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
}

SAFE_TOOL_DESCRIPTIONS = {
    "fetch_json": "fetch_json(url) - Fetch JSON from a public HTTP(S) host.",
    "fetch_url": "fetch_url(url) - Fetch text from a public HTTP(S) host.",
    "list_dir": "list_dir(path) - List files inside the sandboxed workspace.",
    "read_text": "read_text(path) - Read a UTF-8 text file inside the sandboxed workspace.",
    "read_url": "read_url(url) - Read a public web page as text.",
    "search_tweets": "search_tweets(query, limit=5) - Search the local tweet memory database.",
    "search_web": "search_web(query) - Search the public web.",
}

PRIVILEGED_TOOL_DESCRIPTIONS = {
    "copy_file": "copy_file(src, dst) - Copy a file or directory inside the sandboxed workspace.",
    "codex_job_start": "codex_job_start(prompt, workdir) - Start a Codex subprocess.",
    "codex_job_status": "codex_job_status(job_id) - Read Codex job status and logs.",
    "codex_job_stop": "codex_job_stop(job_id) - Stop a Codex subprocess.",
    "codex_read_output": "codex_read_output(lines=20) - Read Codex bridge output.",
    "codex_run_captured": "codex_run_captured(prompt, workdir) - Forward a prompt to the Codex bridge.",
    "codex_run_sync": "codex_run_sync(prompt, workdir) - Spawn Codex in a new terminal window.",
    "codex_send_input": "codex_send_input(text) - Send input to the Codex bridge.",
    "delete_dir": "delete_dir(path) - Delete a directory inside the sandboxed workspace.",
    "delete_file": "delete_file(path) - Delete a file inside the sandboxed workspace.",
    "move_file": "move_file(src, dst) - Move a file or directory inside the sandboxed workspace.",
    "run_python_code": "run_python_code(code) - Execute arbitrary local Python code.",
    "write_text": "write_text(path, content) - Write a UTF-8 text file inside the sandboxed workspace.",
}

SAFE_TOOL_NAMES = set(SAFE_TOOL_DESCRIPTIONS.keys())
PRIVILEGED_TOOL_NAMES = set(PRIVILEGED_TOOL_DESCRIPTIONS.keys())

WRITE_TOOL_NAMES = {"write_text"}

DESTRUCTIVE_TOOL_NAMES = {
    "delete_file",
    "delete_dir",
    "move_file",
    "copy_file",
}

CODEX_TOOL_NAMES = {
    "codex_job_start",
    "codex_job_status",
    "codex_job_stop",
    "codex_read_output",
    "codex_run_captured",
    "codex_run_sync",
    "codex_send_input",
}

RCE_TOOL_NAMES = {
    "run_python_code",
}

NEVER_MODEL_CALLABLE_TOOL_NAMES = (
    DESTRUCTIVE_TOOL_NAMES | CODEX_TOOL_NAMES | RCE_TOOL_NAMES
)


def get_allowed_tool_names(
    *,
    allow_tools: bool,
    is_owner: bool = False,
    is_dm: bool = False,
    has_allowed_role: bool = False,
    privileged_confirmed: bool = False,
) -> set[str]:
    if not allow_tools:
        return set()

    allowed = set(SAFE_TOOL_NAMES)

    if is_owner and is_dm and privileged_confirmed:
        allowed |= WRITE_TOOL_NAMES

    allowed -= NEVER_MODEL_CALLABLE_TOOL_NAMES
    return allowed


def describe_available_tools(include_privileged: bool = False) -> str:
    """モデルに見せるツール一覧を説明文付きで返す。"""
    descriptions = dict(SAFE_TOOL_DESCRIPTIONS)
    if include_privileged:
        descriptions.update(PRIVILEGED_TOOL_DESCRIPTIONS)
    return "\n".join(f"- {value}" for _, value in sorted(descriptions.items()))
