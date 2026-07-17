"""Ollama HTTP client and role-specific model calls."""

from typing import Optional

import requests

from mafuyu_ai.settings import (
    OLLAMA_HEAVY_CTX,
    OLLAMA_HEAVY_KEEP_ALIVE,
    OLLAMA_HEAVY_MODEL,
    OLLAMA_HEAVY_PREDICT,
    OLLAMA_MAIN_CTX,
    OLLAMA_MAIN_KEEP_ALIVE,
    OLLAMA_MAIN_MODEL,
    OLLAMA_MAIN_PREDICT,
    OLLAMA_ROUTER_CTX,
    OLLAMA_ROUTER_KEEP_ALIVE,
    OLLAMA_ROUTER_MODEL,
    OLLAMA_ROUTER_PREDICT,
    OLLAMA_URL,
)


def call_ollama_model(
    messages: list[dict],
    model: str,
    *,
    num_ctx: int,
    num_predict: int,
    temperature: float = 0.7,
    top_p: float = 0.9,
    format: Optional[str] = None,
    keep_alive: str = "5m",
    timeout: int = 120,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
            "top_p": top_p,
        },
    }

    if format:
        payload["format"] = format

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "").strip()
    except requests.RequestException as e:
        raise RuntimeError(f"Ollama API error: {e}")


def call_router(messages: list[dict]) -> str:
    return call_ollama_model(
        messages,
        OLLAMA_ROUTER_MODEL,
        num_ctx=OLLAMA_ROUTER_CTX,
        num_predict=OLLAMA_ROUTER_PREDICT,
        temperature=0.1,
        top_p=0.8,
        format="json",
        keep_alive=OLLAMA_ROUTER_KEEP_ALIVE,
        timeout=60,
    )


def call_main(messages: list[dict], *, max_tokens: int | None = None) -> str:
    return call_ollama_model(
        messages,
        OLLAMA_MAIN_MODEL,
        num_ctx=OLLAMA_MAIN_CTX,
        num_predict=max_tokens or OLLAMA_MAIN_PREDICT,
        temperature=0.7,
        top_p=0.9,
        keep_alive=OLLAMA_MAIN_KEEP_ALIVE,
        timeout=120,
    )


def call_heavy(messages: list[dict], *, max_tokens: int | None = None) -> str:
    return call_ollama_model(
        messages,
        OLLAMA_HEAVY_MODEL,
        num_ctx=OLLAMA_HEAVY_CTX,
        num_predict=max_tokens or OLLAMA_HEAVY_PREDICT,
        temperature=0.4,
        top_p=0.9,
        keep_alive=OLLAMA_HEAVY_KEEP_ALIVE,
        timeout=180,
    )


def call_ollama(messages: list[dict], stream: bool = False) -> str:
    return call_main(messages)


def chat(
    user_input: str, history: list[dict], system_prompt: str
) -> tuple[str, list[dict]]:
    """
    Chat with Mafuyu persona.

    Args:
        user_input: User's message
        history: Conversation history
        system_prompt: System prompt text

    Returns:
        (response, updated_history)
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_input})

    response = call_ollama(messages)

    new_history = history + [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": response},
    ]

    return response, new_history
