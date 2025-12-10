"""Simple file reading and search utilities used by agents.

Tools:
- read_file_tool(path): if `path` is a file, return its contents; if it's a directory,
  concatenate and return the text of files under it (skipping binary files).
- search_file_tool(query, path, context_words=50): search the text for occurrences of
  `query` and return snippets containing the match and `context_words` words after it.

These are intentionally simple, synchronous helpers for local development and testing.
"""
from __future__ import annotations
import os
import io
import typing as t
import re


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        # Fallback to binary-safe read and decode errors ignored
        try:
            with open(path, "rb") as f:
                data = f.read()
                return data.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[error reading file {path}: {e}]"


def read_file_tool(path: str) -> str:
    """Return file contents for a path. If path is a directory, return concatenation
    of text files inside (sorted by name).
    """
    # user-observable log for debugging
    try:
        print(f"read_file called with argument: {path}")
    except Exception:
        pass
    if not path:
        return ""

    if os.path.isdir(path):
        out_parts: t.List[str] = []
        # Walk directory non-recursively (only top-level files) to keep output predictable
        try:
            for name in sorted(os.listdir(path)):
                full = os.path.join(path, name)
                if os.path.isfile(full):
                    out_parts.append(f"--- FILE: {name} ---\n")
                    out_parts.append(_read_text_file(full))
        except Exception as e:
            return f"[error reading directory {path}: {e}]"
        return "\n".join(out_parts)

    # single file
    return _read_text_file(path)


def search_file_tool(query: str, path: str, context_words: int = 50) -> t.List[str]:
    """Search `path` (file or directory) for occurrences of `query` (case-insensitive).
    Returns a list of snippet strings containing the match and up to `context_words` words
    after the match. If query is short (like 'p2') this returns surrounding tokens.
    """
    if not query or not path:
        return []

    # Build large text that we can search
    text = read_file_tool(path)
    if not text:
        return []

    snippets: t.List[str] = []
    # Normalize whitespace
    norm = re.sub(r"\s+", " ", text)
    # Case-insensitive search
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    for m in pattern.finditer(norm):
        start = m.start()
        end = m.end()
        # Extract context: get next context_words words after the match
        after = norm[end:]
        words = after.split()
        take = " ".join(words[:context_words])
        snippet = norm[max(0, start-100):end] + " " + take
        snippets.append(snippet.strip())
        # Limit to first 10 matches to avoid huge outputs
        if len(snippets) >= 10:
            break

    return snippets
