# Architecture

Mafuyu AI is organized around dependency direction rather than entry-point type.

```text
interfaces (CLI / Discord)
        |
        v
core (session / prompts / memory / emotion)
        |
        +--------> llm (client / routing / agent protocol)
        |
        +--------> tools (policy / safety / implementations / registry)
```

## Package boundaries

- `mafuyu_ai.interfaces`: translates CLI or Discord events into session calls. It owns no model or tool policy.
- `mafuyu_ai.core`: coordinates a conversation and owns prompt, history, memory, emotion, and response cleanup.
- `mafuyu_ai.llm`: contains the Ollama transport, adaptive router, inference budgets, optional Hugging Face backend, and the legacy JSON agent protocol.
- `mafuyu_ai.tools`: separates model-visible policy, path/URL safety, filesystem and web implementations, privileged Codex operations, and the execution registry.
- `mafuyu_ai.agent`: retains the legacy multi-step agent runner and persisted state without coupling it to the chat interfaces.
- `mafuyu_ai.resources`: contains editable prompt, few-shot, and help data.

The root-level Python modules are compatibility shims. New code should import from `mafuyu_ai` and its subpackages.

## Dependency rules

1. Interfaces may depend on core and settings.
2. Core may depend on LLM and tools.
3. LLM routing may depend on the LLM client, but the client must not depend on core.
4. Tool implementations must not depend on the chat session.
5. All model-triggered tool calls must pass through `tools.registry.execute_tool` and an explicit allowlist.
6. Importing settings must not create runtime directories; entry points and persistence operations create them when needed.
