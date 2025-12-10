"""A tiny local shim for the `litellm` package used by the project.

This shim provides a minimal `completion` function with the same
call signature used in the codebase. It returns a lightweight object
with `choices[0].message.model_dump()` to avoid import-time crashes
when the real `litellm` package isn't installed.

This is intended as a developer convenience so the repository can be
run locally without installing the external `litellm` dependency.
Replace this shim by installing the real package or remove it when
you want the real behaviour.
"""
from typing import List, Dict, Any


class _Message:
    def __init__(self, content: str):
        self.content = content

    # The real litellm message objects expose a `model_dump()` method
    # returning a dict with a `content` key. Provide the same small API.
    def model_dump(self) -> Dict[str, Any]:
        return {"content": self.content}


class _Choice:
    def __init__(self, content: str):
        self.message = _Message(content)


class _Response:
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


def completion(*, messages: List[Dict[str, str]] = None, model: str | None = None, custom_llm_provider: str | None = None, temperature: float = 0.0, **kwargs) -> _Response:
    """Minimal completion shim.

    - `messages` is expected to be a list of dicts with `role` and `content` keys.
    - Returns object with `.choices[0].message.model_dump()` -> dict with `content`.

    This shim simply echoes the last user message prefixed with a note so
    the rest of the code can continue during local development.
    """
    if not messages:
        last = ""
    else:
        last = messages[-1].get("content", "")

    # Small heuristic: if the last message looks like a short instruction,
    # respond with a deterministic stub. This keeps behaviour predictable
    # for local runs and tests that don't hit the network.
    reply = f"[litellm-shim reply | model={model} | provider={custom_llm_provider}] {last}"

    return _Response(reply)
