"""Production MCP client for Research Digest tools.

Features:
- Transport abstraction (stdio, HTTP, WebSocket)
- Dynamic tool discovery and centralized registry
- JSON-schema validation for tool inputs
- Response normalization and resilient retries
- Backward compatible helpers for existing agent/workflow code
"""
from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any, AsyncGenerator, Protocol

import httpx
from jsonschema import ValidationError, validate

try:
    import websockets
except Exception:  # pragma: no cover - optional dependency fallback
    websockets = None

try:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
except Exception:  # pragma: no cover - graceful fallback if MCP lib is missing
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None

from arxiv_client import Paper

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPSettings:
    transport: str
    stdio_server_script: str
    stdio_python_executable: str
    http_url: str
    ws_url: str
    timeout_seconds: float
    retries: int
    retry_backoff_seconds: float
    stream_chunk_size: int


def _settings() -> MCPSettings:
    backend_dir = Path(__file__).resolve().parent
    default_server = str((backend_dir / ".." / "mcp_server" / "server.py").resolve())
    return MCPSettings(
        transport=os.environ.get("MCP_TRANSPORT", "stdio").strip().lower(),
        stdio_server_script=os.environ.get("MCP_STDIO_SERVER_SCRIPT", default_server).strip(),
        stdio_python_executable=os.environ.get("MCP_STDIO_PYTHON", sys.executable).strip(),
        http_url=os.environ.get("MCP_HTTP_URL", "http://127.0.0.1:8020/mcp").strip(),
        ws_url=os.environ.get("MCP_WS_URL", "ws://127.0.0.1:8021/mcp").strip(),
        timeout_seconds=float(os.environ.get("MCP_TIMEOUT_SECONDS", "40")),
        retries=int(os.environ.get("MCP_RETRIES", "2")),
        retry_backoff_seconds=float(os.environ.get("MCP_RETRY_BACKOFF_SECONDS", "1.5")),
        stream_chunk_size=int(os.environ.get("MCP_STREAM_CHUNK_SIZE", "800")),
    )


class MCPError(Exception):
    pass


class MCPTransportError(MCPError):
    pass


class MCPSchemaError(MCPError):
    pass


class MCPMalformedResponseError(MCPError):
    pass


@dataclass(frozen=True)
class MCPToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPTransport(Protocol):
    async def connect(self) -> None:
        ...

    async def close(self) -> None:
        ...

    async def list_tools(self) -> list[dict[str, Any]]:
        ...

    async def call_tool(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        ...


class StdioMCPTransport:
    def __init__(self, cfg: MCPSettings):
        self._cfg = cfg
        self._session: ClientSession | None = None
        self._stdio_ctx: AbstractAsyncContextManager | None = None

    async def connect(self) -> None:
        if self._session is not None:
            return
        if ClientSession is None or stdio_client is None or StdioServerParameters is None:
            raise MCPTransportError("MCP stdio dependencies are unavailable. Install the mcp package.")

        if not os.path.exists(self._cfg.stdio_server_script):
            raise MCPTransportError(f"MCP stdio server script not found: {self._cfg.stdio_server_script}")

        server_params = StdioServerParameters(
            command=self._cfg.stdio_python_executable,
            args=[self._cfg.stdio_server_script],
            env=os.environ.copy(),
        )
        self._stdio_ctx = stdio_client(server_params)
        read_stream, write_stream = await self._stdio_ctx.__aenter__()

        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            finally:
                self._session = None

        if self._stdio_ctx is not None:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception:
                logger.warning("Failed to close stdio MCP context cleanly.")
            finally:
                self._stdio_ctx = None

    async def list_tools(self) -> list[dict[str, Any]]:
        if self._session is None:
            raise MCPTransportError("Stdio MCP session is not connected.")
        response = await self._session.list_tools()
        tools = getattr(response, "tools", [])
        return [
            {
                "name": getattr(t, "name", ""),
                "description": getattr(t, "description", ""),
                "inputSchema": getattr(t, "inputSchema", {}) or {},
            }
            for t in tools
            if getattr(t, "name", "")
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        if self._session is None:
            raise MCPTransportError("Stdio MCP session is not connected.")
        return await asyncio.wait_for(self._session.call_tool(name, arguments), timeout=timeout)


class HttpMCPTransport:
    """HTTP JSON-RPC transport for MCP-compatible endpoints."""

    def __init__(self, cfg: MCPSettings):
        self._cfg = cfg
        self._client: httpx.AsyncClient | None = None
        self._req_id = 0

    async def connect(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._cfg.timeout_seconds)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rpc(self, method: str, params: dict[str, Any], timeout: float) -> Any:
        if self._client is None:
            raise MCPTransportError("HTTP MCP client is not connected.")

        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params,
        }
        try:
            response = await self._client.post(self._cfg.http_url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise MCPTransportError(f"HTTP transport failure: {exc}") from exc

        if "error" in data:
            raise MCPTransportError(f"MCP HTTP error for {method}: {data['error']}")

        return data.get("result", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._rpc("tools/list", {}, timeout=self._cfg.timeout_seconds)
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        return await self._rpc("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)


class WebSocketMCPTransport:
    """WebSocket JSON-RPC transport for MCP-compatible endpoints."""

    def __init__(self, cfg: MCPSettings):
        self._cfg = cfg
        self._req_id = 0

    async def connect(self) -> None:
        if websockets is None:
            raise MCPTransportError("websockets dependency is unavailable for MCP WebSocket transport.")

    async def close(self) -> None:
        return None

    async def _rpc(self, method: str, params: dict[str, Any], timeout: float) -> Any:
        if websockets is None:
            raise MCPTransportError("websockets dependency is unavailable for MCP WebSocket transport.")

        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": method,
            "params": params,
        }
        try:
            async with websockets.connect(self._cfg.ws_url, ping_interval=20, ping_timeout=20) as ws:
                await asyncio.wait_for(ws.send(json.dumps(payload)), timeout=timeout)
                message = await asyncio.wait_for(ws.recv(), timeout=timeout)
        except Exception as exc:
            raise MCPTransportError(f"WebSocket transport failure: {exc}") from exc

        data = json.loads(message)
        if "error" in data:
            raise MCPTransportError(f"MCP WebSocket error for {method}: {data['error']}")
        return data.get("result", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._rpc("tools/list", {}, timeout=self._cfg.timeout_seconds)
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        return await self._rpc("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)


class MCPToolRegistry:
    def __init__(self):
        self._tools: dict[str, MCPToolSpec] = {}

    def update(self, tools: list[dict[str, Any]]) -> None:
        updated: dict[str, MCPToolSpec] = {}
        for tool in tools:
            name = str(tool.get("name", "")).strip()
            if not name:
                continue
            updated[name] = MCPToolSpec(
                name=name,
                description=str(tool.get("description", "")),
                input_schema=tool.get("inputSchema", {}) or {},
            )
        self._tools = updated

    def get(self, name: str) -> MCPToolSpec | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())


class MCPResponseNormalizer:
    @staticmethod
    def _from_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict) and isinstance(content.get("text"), str):
            return content["text"]
        if hasattr(content, "text"):
            return str(getattr(content, "text"))
        return ""

    @classmethod
    def text(cls, response: Any) -> str:
        if hasattr(response, "content"):
            items = getattr(response, "content", []) or []
            if items:
                text = cls._from_content(items[0])
                if text:
                    return text
        if isinstance(response, dict):
            content = response.get("content")
            if isinstance(content, list) and content:
                text = cls._from_content(content[0])
                if text:
                    return text
            result = response.get("result")
            if isinstance(result, str):
                return result
        if isinstance(response, str):
            return response
        return ""

    @classmethod
    def json_dict(cls, response: Any) -> dict[str, Any]:
        text = cls.text(response)
        if not text:
            raise MCPMalformedResponseError("MCP response did not contain text content.")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPMalformedResponseError(f"Invalid JSON response: {text[:200]}") from exc
        if not isinstance(parsed, dict):
            raise MCPMalformedResponseError("Expected JSON object response from MCP tool.")
        return parsed

    @classmethod
    def json_list(cls, response: Any) -> list[dict[str, Any]]:
        text = cls.text(response)
        if not text:
            raise MCPMalformedResponseError("MCP response did not contain text content.")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MCPMalformedResponseError(f"Invalid JSON list response: {text[:200]}") from exc
        if not isinstance(parsed, list):
            raise MCPMalformedResponseError("Expected JSON list response from MCP tool.")
        return [item for item in parsed if isinstance(item, dict)]


class MCPClientService:
    def __init__(self, cfg: MCPSettings):
        self._cfg = cfg
        self._registry = MCPToolRegistry()
        self._transport = self._build_transport(cfg)
        self._lock = asyncio.Lock()
        self._connected = False

    @staticmethod
    def _build_transport(cfg: MCPSettings) -> MCPTransport:
        if cfg.transport == "stdio":
            return StdioMCPTransport(cfg)
        if cfg.transport == "http":
            return HttpMCPTransport(cfg)
        if cfg.transport in {"ws", "websocket"}:
            return WebSocketMCPTransport(cfg)
        raise MCPTransportError(f"Unsupported MCP transport '{cfg.transport}'. Use stdio, http, or ws.")

    async def _ensure_connected(self) -> None:
        if self._connected:
            return

        async with self._lock:
            if self._connected:
                return
            await self._transport.connect()
            tools = await self._transport.list_tools()
            self._registry.update(tools)
            self._connected = True
            logger.info("MCP connected via transport=%s tools=%s", self._cfg.transport, self._registry.names())

    def _validate_schema(self, tool_name: str, arguments: dict[str, Any]) -> None:
        spec = self._registry.get(tool_name)
        if spec is None:
            raise MCPSchemaError(f"Tool '{tool_name}' is not registered on MCP server.")
        schema = spec.input_schema or {}
        if not schema:
            return
        try:
            validate(instance=arguments, schema=schema)
        except ValidationError as exc:
            raise MCPSchemaError(f"Schema validation failed for tool '{tool_name}': {exc.message}") from exc

    async def discover_tools(self) -> list[str]:
        await self._ensure_connected()
        return self._registry.names()

    async def close(self) -> None:
        await self._transport.close()
        self._connected = False

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        await self._ensure_connected()
        self._validate_schema(tool_name, arguments)

        last_error: Exception | None = None
        for attempt in range(self._cfg.retries + 1):
            started = time.perf_counter()
            try:
                response = await self._transport.call_tool(tool_name, arguments, self._cfg.timeout_seconds)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "mcp_call_ok tool=%s transport=%s attempt=%s elapsed_ms=%s",
                    tool_name,
                    self._cfg.transport,
                    attempt + 1,
                    elapsed_ms,
                )
                return response
            except Exception as exc:
                last_error = exc
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.warning(
                    "mcp_call_failed tool=%s transport=%s attempt=%s elapsed_ms=%s error=%s",
                    tool_name,
                    self._cfg.transport,
                    attempt + 1,
                    elapsed_ms,
                    exc,
                )

                # Refresh tool registry once if server was restarted/unavailable.
                self._connected = False
                if attempt < self._cfg.retries:
                    await asyncio.sleep(self._cfg.retry_backoff_seconds * (attempt + 1))
                    await self._ensure_connected()

        raise MCPTransportError(f"MCP call failed after retries for tool '{tool_name}': {last_error}")

    async def stream_text_tool(self, tool_name: str, arguments: dict[str, Any]) -> AsyncGenerator[str, None]:
        response = await self.call_tool(tool_name, arguments)
        text = MCPResponseNormalizer.text(response)
        if not text:
            return

        # For non-streaming transports, chunk output to preserve incremental SSE behavior.
        chunk_size = max(100, self._cfg.stream_chunk_size)
        for i in range(0, len(text), chunk_size):
            yield text[i : i + chunk_size]


_client = MCPClientService(_settings())


async def _cleanup_async() -> None:
    try:
        await _client.close()
    except Exception as exc:
        logger.warning("MCP cleanup error: %s", exc)


def _cleanup_sync() -> None:
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_cleanup_async())
        loop.close()
    except Exception as exc:
        logger.warning("MCP sync cleanup error: %s", exc)


atexit.register(_cleanup_sync)


def _paper_from_dict(data: dict[str, Any]) -> Paper:
    return Paper(
        arxiv_id=str(data.get("arxiv_id", "")),
        title=str(data.get("title", "")),
        authors=list(data.get("authors", []) or []),
        abstract=str(data.get("abstract", "")),
        published=str(data.get("published", "")),
        url=str(data.get("url", "")),
        categories=list(data.get("categories", []) or []),
        primary_category=str(data.get("primary_category", "")),
    )


async def discover_tools() -> list[str]:
    """Return dynamic MCP-discovered tool names."""
    return await _client.discover_tools()


async def generate_query(
    topic: str,
    collected_papers: list[Paper],
    iteration: int,
    zero_results: bool = False,
) -> str:
    """Backward-compatible query generation for legacy agent flow."""
    arguments = {
        "topic": topic,
        "collected_papers": [p.to_dict() for p in collected_papers],
        "iteration": iteration,
        "zero_results": zero_results,
    }
    try:
        response = await _client.call_tool("generate_query", arguments)
        return MCPResponseNormalizer.text(response) or topic
    except Exception as exc:
        logger.error("generate_query failed: %s", exc)
        return topic


async def generate_query_from_titles(topic: str, iteration: int, collected_titles: list[str]) -> str:
    arguments = {
        "topic": topic,
        "iteration": iteration,
        "collected_titles": collected_titles,
    }
    try:
        response = await _client.call_tool("generate_query_from_titles", arguments)
        return MCPResponseNormalizer.text(response) or topic
    except Exception as exc:
        logger.error("generate_query_from_titles failed: %s", exc)
        return topic


async def evaluate_sufficiency(topic: str, papers: list[Paper]) -> dict[str, Any]:
    """Backward-compatible sufficiency call for legacy agent flow."""
    arguments = {
        "topic": topic,
        "papers": [p.to_dict() for p in papers],
    }
    try:
        response = await _client.call_tool("evaluate_sufficiency", arguments)
        result = MCPResponseNormalizer.json_dict(response)
        return {
            "sufficient": bool(result.get("sufficient", False)),
            "reason": str(result.get("reason", "")),
            "missing": str(result.get("missing", "")),
        }
    except Exception as exc:
        logger.error("evaluate_sufficiency failed: %s", exc)
        return {"sufficient": False, "reason": str(exc), "missing": ""}


async def evaluate_sufficiency_from_summaries(topic: str, paper_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    arguments = {
        "topic": topic,
        "paper_summaries": paper_summaries,
    }
    try:
        response = await _client.call_tool("evaluate_sufficiency", arguments)
        result = MCPResponseNormalizer.json_dict(response)
        return {
            "sufficient": bool(result.get("sufficient", False)),
            "reason": str(result.get("reason", "")),
            "missing_information": str(result.get("missing", "")),
        }
    except Exception as exc:
        logger.error("evaluate_sufficiency_from_summaries failed: %s", exc)
        return {
            "sufficient": False,
            "reason": str(exc),
            "missing_information": "",
        }


async def search_papers(query: str, max_results: int = 5) -> list[Paper]:
    arguments = {
        "query": query,
        "max_results": max_results,
    }
    try:
        response = await _client.call_tool("search_papers", arguments)
        papers_data = MCPResponseNormalizer.json_list(response)
        return [_paper_from_dict(p) for p in papers_data]
    except Exception as exc:
        logger.error("search_papers failed: %s", exc)
        return []


async def summarize_paper(topic: str, title: str, abstract: str) -> str:
    arguments = {
        "topic": topic,
        "title": title,
        "abstract": abstract,
    }
    try:
        response = await _client.call_tool("summarize_paper", arguments)
        return MCPResponseNormalizer.text(response).strip()
    except Exception as exc:
        logger.error("summarize_paper failed: %s", exc)
        return ""


async def stream_digest(topic: str, papers: list[Paper]) -> AsyncGenerator[str, None]:
    """Backward-compatible digest stream for legacy agent flow."""
    arguments = {
        "topic": topic,
        "papers": [p.to_dict() for p in papers],
    }
    try:
        async for chunk in _client.stream_text_tool("stream_digest", arguments):
            yield chunk
    except Exception as exc:
        logger.error("stream_digest failed: %s", exc)
        yield f"Error generating digest: {exc}"


async def stream_digest_from_summaries(topic: str, paper_summaries: list[dict[str, Any]]) -> AsyncGenerator[str, None]:
    arguments = {
        "topic": topic,
        "paper_summaries": paper_summaries,
    }
    try:
        async for chunk in _client.stream_text_tool("stream_digest_from_summaries", arguments):
            yield chunk
    except Exception as exc:
        logger.error("stream_digest_from_summaries failed: %s", exc)
        yield f"Error generating digest: {exc}"
