# Project 12 — MCP Integration

## Overview

**Project 12** demonstrates the power of the Model Context Protocol (MCP) by swapping out hand-written tool functions from **Project 10** (Research Digest Agent) for a dedicated MCP server. 

### Key Principle: Zero Changes to Agent/Frontend/System Prompt

The critical point of this project is to show that:
- ✅ **Agent logic remains identical** — The ReAct-style loop, decision-making, and behavior are unchanged
- ✅ **Frontend remains identical** — No changes to the React UI or API endpoints
- ✅ **System prompt remains identical** — The instructions to the LLM are exactly the same
- ✅ **Only tool delivery changes** — Tools are now provided via MCP instead of hand-written functions

This demonstrates MCP's transparency: **the system can swap tool implementations without changing the consumer.**

---

## Architecture

### Project 10 (Original): Hand-Written Tools

```
agent.py (contains)
├── _generate_query()
├── _evaluate_sufficiency()
├── _stream_digest()
└── _call_json() helper
     ↓ calls
arxiv_client.py
├── search_arxiv()
├── _search_semantic_scholar()
└── _search_arxiv_fallback()
```

### Project 12 (MCP-Based): Delegated to MCP Server

```
agent.py (uses)
└── mcp_client.py
     ├── generate_query() ──→ (MCP call)
     ├── evaluate_sufficiency() ──→ (MCP call)
     ├── search_papers() ──→ (MCP call)
     └── stream_digest() ──→ (MCP call)
          ↓ communicates via MCP protocol
mcp_server/server.py
├── Tool: generate_query
├── Tool: evaluate_sufficiency
├── Tool: search_papers
└── Tool: stream_digest
     ↓ uses
Agent's original function implementations
├── _generate_query_impl()
├── _evaluate_sufficiency_impl()
└── _stream_digest() (unchanged)
     ↓ calls
arxiv_client.py (unchanged)
```

---

## File Structure

```
research_digest_agent/
├── backend/
│   ├── agent.py                    # MODIFIED: Now uses mcp_client instead of direct calls
│   ├── mcp_client.py               # NEW: MCP client exposing tool functions
│   ├── arxiv_client.py             # UNCHANGED
│   ├── main.py                     # UNCHANGED
│   ├── requirements.txt            # UPDATED: Added mcp>=0.2.0
│   └── ...
├── mcp_server/                     # NEW: Dedicated MCP server
│   ├── server.py                   # MCP server implementation with tool handlers
│   ├── requirements.txt            # MCP server dependencies
│   └── __init__.py
├── frontend/                       # UNCHANGED
└── frontend-next/                  # UNCHANGED
```

---

## How It Works

### 1. Tool Call Flow in Project 12

```
agent.py (run_research_agent)
    ├─ calls: await mcp_client.generate_query(...)
    │          ↓
    │          mcp_client.py (in-process client)
    │          ├─ Starts MCP server subprocess if needed
    │          ├─ Sends tool request via MCP protocol
    │          ↓
    │          mcp_server/server.py (subprocess)
    │          ├─ Receives: generate_query tool call
    │          ├─ Invokes: _generate_query_impl()
    │          ├─ Returns: Result via MCP
    │          ↓
    │          mcp_client.py (parses response)
    │          ↓ (returns as string)
    │
    └─ continues with next step (exact same logic as Project 10)
```

### 2. MCP Server Tools

The MCP server exposes four tools:

#### Tool: `generate_query`
- **Input**: topic, collected_papers[], iteration, zero_results
- **Output**: String (search query)
- **Implementation**: Uses LLM to generate search keywords

#### Tool: `evaluate_sufficiency`
- **Input**: topic, papers[]
- **Output**: JSON with {sufficient: bool, reason: str, missing: str}
- **Implementation**: Uses LLM to decide if papers are sufficient

#### Tool: `search_papers`
- **Input**: query, max_results
- **Output**: JSON array of paper objects
- **Implementation**: Calls arxiv_client.search_arxiv()

#### Tool: `stream_digest`
- **Input**: topic, papers[]
- **Output**: String (streamed markdown digest)
- **Implementation**: Uses LLM to synthesize comprehensive digest

---

## Running Project 12

### Prerequisites

1. **MCP Support**: Ensure MCP library is installed:
   ```bash
   pip install -r backend/requirements.txt
   pip install -r mcp_server/requirements.txt
   ```

2. **Environment Variables**: Same as Project 10:
   ```
   LITELLM_API_KEY=...
   LITELLM_PROXY_URL=...
   LLM_MODEL=gpt-4o
   SEMANTIC_SCHOLAR_API_KEY=... (optional)
   ```

### Launch the Service

#### Option 1: Direct Subprocess (Recommended)
MCP server starts automatically as subprocess when first tool is called:

```powershell
# Terminal 1: Backend
cd research_digest_agent/backend
python main.py
```

The frontend is unchanged; still available at http://localhost:3000 or http://localhost:5173

#### Option 2: Explicit Server Launch
For debugging, start MCP server in separate terminal:

```powershell
# Terminal 1: MCP Server
cd research_digest_agent/mcp_server
python server.py

# Terminal 2: Backend (connects to running server)
cd research_digest_agent/backend
python main.py
```

---

## Verification: Zero Changes to Agent

To confirm the agent logic is unchanged, compare:

- **Project 10**: `research_digest_agent/backend/agent.py` (original)
- **Project 12**: `research_digest_agent/backend/agent.py` (current)

Key invariants:
- ✅ `run_research_agent()` loop structure identical
- ✅ ReAct flow: THINK → GENERATE QUERY → SEARCH → EVALUATE → SYNTHESIZE
- ✅ MAX_ITERATIONS, MIN_PAPERS_TARGET constants unchanged
- ✅ Event emission structure unchanged (agent_start, thinking, searching, etc.)
- ✅ Paper deduplication logic unchanged
- ✅ Frontend API endpoints unchanged

**The only changes**: Tool call targets (mcp_client instead of direct function calls).

---

## Verification: Frontend Unchanged

The frontend remains completely unchanged:
- No UI modifications
- No API changes
- No authentication changes
- No data model changes

The API continues to emit server-sent events (SSE) exactly as before:
```json
{"event": "agent_start", "data": {"topic": "...", "max_iterations": 4}}
{"event": "thinking", "data": {"iteration": 1, "message": "..."}}
{"event": "searching", "data": {"iteration": 1, "query": "..."}}
{"event": "papers_found", "data": {...}}
...
```

---

## Verification: System Prompt Unchanged

The LLM system prompts remain identical across all MCP tools:

1. **Query Generation**: "You are a research librarian..." (unchanged)
2. **Sufficiency Evaluation**: "You are a research evaluator..." (unchanged)
3. **Digest Synthesis**: "You are a senior AI research analyst..." (unchanged)

---

## Benefits of MCP Integration

1. **Modularity**: Tool implementations can be developed independently
2. **Reusability**: MCP server can be shared across multiple agents
3. **Testability**: MCP tools can be tested in isolation
4. **Deployment Flexibility**: MCP server can run in separate process/container
5. **Transparency**: Consumer (agent) sees no difference in behavior

---

## Project 12 vs Project 10: Side-by-Side Comparison

| Aspect | Project 10 | Project 12 |
|--------|-----------|-----------|
| Tool delivery | Direct function calls | MCP server |
| Function imports | `from agent import _generate_query` | `import mcp_client` |
| Tool calls | `await _generate_query(...)` | `await mcp_client.generate_query(...)` |
| Server communication | In-process | Subprocess + stdio |
| Agent logic | N/A | **Identical** |
| Frontend | N/A | **Identical** |
| System prompt | N/A | **Identical** |
| arxiv_client.py | Used by agent | Used by MCP server |

---

## Troubleshooting

### MCP Server Fails to Start
- Check MCP package is installed: `pip list | grep mcp`
- Verify Python version >= 3.9
- Check stderr output from server subprocess

### Tool Calls Timeout
- Increase timeout in mcp_client.py if needed
- Check LiteLLM/OpenAI API connectivity
- Verify LITELLM_API_KEY is set

### Subprocess Communication Issues
- Test MCP server independently: `python mcp_server/server.py`
- Check stdio streams are properly connected
- Look for encoding issues (should be UTF-8)

---

## Next Steps

This Project 12 implementation can be extended:
- Add more tools to the MCP server
- Implement concurrent tool calls
- Add tool caching/memoization
- Deploy MCP server as microservice
- Add tool versioning/compatibility

---

## References

- [Model Context Protocol (MCP) Documentation](https://modelcontextprotocol.io/)
- [Research Digest Agent (Project 10) Original Implementation](./backend/agent.py)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
