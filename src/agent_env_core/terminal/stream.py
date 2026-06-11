"""Concurrent subprocess stream readers."""

import asyncio

from agent_env_core.exceptions import InteractivePromptException

from .prompts import contains_interactive_prompt

MAX_STREAM_CHARS = 10_000


async def _read_stream(stream: asyncio.StreamReader) -> tuple[str, bool]:
    chunks: list[str] = []
    total = 0
    truncated = False
    while True:
        chunk = await stream.readline()
        if not chunk:
            break
        text = chunk.decode(errors="replace")
        if contains_interactive_prompt(text):
            raise InteractivePromptException(
                "Interactive prompt detected in command output.",
                "Run a non-interactive command or provide required input through command flags.",
            )
        remaining = MAX_STREAM_CHARS - total
        if remaining > 0:
            chunks.append(text[:remaining])
            total += min(len(text), remaining)
        if len(text) > remaining:
            truncated = True
    return "".join(chunks), truncated


async def collect_streams(
    stdout: asyncio.StreamReader,
    stderr: asyncio.StreamReader,
) -> tuple[str, str, bool, bool]:
    """Read stdout and stderr concurrently with prompt detection and per-stream truncation."""
    out_result, err_result = await asyncio.gather(_read_stream(stdout), _read_stream(stderr))
    return out_result[0], err_result[0], out_result[1], err_result[1]
