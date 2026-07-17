"""Tool registry and centralized execution boundary."""

import json
from typing import Optional

from mafuyu_ai.tools.codex import (
    codex_job_start,
    codex_job_status,
    codex_job_stop,
    codex_read_output,
    codex_run_captured,
    codex_run_sync,
    codex_send_input,
    run_python_code,
)
from mafuyu_ai.tools.filesystem import (
    copy_file,
    delete_dir,
    delete_file,
    list_dir,
    move_file,
    read_text,
    write_text,
)
from mafuyu_ai.tools.policy import SAFE_TOOL_NAMES
from mafuyu_ai.tools.web import (
    fetch_json,
    fetch_url,
    read_url,
    search_tweets,
    search_web,
)

SAFE_TOOLS = {
    "list_dir": list_dir,
    "read_text": read_text,
    "fetch_url": fetch_url,
    "fetch_json": fetch_json,
    "read_url": read_url,
    "search_web": search_web,
    "search_tweets": search_tweets,
}

PRIVILEGED_TOOLS = {
    "write_text": write_text,
    "delete_file": delete_file,
    "delete_dir": delete_dir,
    "move_file": move_file,
    "copy_file": copy_file,
    "codex_job_start": codex_job_start,
    "codex_job_status": codex_job_status,
    "codex_job_stop": codex_job_stop,
    "codex_run_sync": codex_run_sync,
    "codex_run_captured": codex_run_captured,
    "codex_read_output": codex_read_output,
    "codex_send_input": codex_send_input,
    "run_python_code": run_python_code,
}

ALL_TOOLS = {**SAFE_TOOLS, **PRIVILEGED_TOOLS}
TOOLS = SAFE_TOOLS


def execute_tool(
    tool_name: str,
    args: dict,
    allow_privileged: bool = False,
    allowed_tool_names: Optional[set[str]] = None,
) -> str:
    """
    ツールを実行し、その結果を JSON 文字列で返す。

    通常のチャット経路では safe tools だけを公開し、privileged tools は
    明示的に許可された経路でしか使えないようにしている。
    """
    effective_allowed_tool_names = (
        set(SAFE_TOOL_NAMES) if allowed_tool_names is None else set(allowed_tool_names)
    )

    if tool_name not in effective_allowed_tool_names:
        return json.dumps({"error": f"Tool not allowed in this context: {tool_name}"})

    registry = ALL_TOOLS
    if tool_name not in registry:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = registry[tool_name](**args)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError as e:
        return json.dumps({"error": f"Invalid arguments for {tool_name}: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Tool execution failed: {e}"})
