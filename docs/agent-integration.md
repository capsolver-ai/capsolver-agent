# Agent Integration Guide

This guide covers how to integrate CapSolver tools into Python AI frameworks using the `capsolver-agent` package.

If your tool supports the MCP protocol directly (Claude Desktop, Cursor, Windsurf, etc.), see [MCP client configuration](https://github.com/capsolver-ai/mcp-capsolver/blob/main/docs/mcp-integration.md) instead.

## Install

```bash
pip install capsolver-agent
pip install capsolver-agent[langchain]   # with LangChain support
pip install capsolver-agent[browser]     # with Playwright support (for detect/solve_on_page)
```

Set your API key:

```bash
export CAPSOLVER_API_KEY="CAP-XXXXXX"
```

## Available Tools

All frameworks below use these 5 tools via `capsolver-agent`:

| Tool | Browser? | Description |
|------|----------|-------------|
| `solve_captcha` | No | Solve a captcha by type + site params (token mode) |
| `detect_captchas` | Yes | Scan a page URL and list present captcha types |
| `solve_on_page` | Yes | Detect + solve + autofill all captchas on a page |
| `get_balance` | No | Check account balance and packages |
| `get_supported_captchas` | No | List all supported captcha types and handlers |

Browser-based tools require `pip install capsolver-agent[browser]` and `playwright install chromium`.

---

## Framework Integrations

### OpenAI Function Calling

```python
from capsolver_agent.schema import get_all_tools, create_executor

tools = [t.to_openai_function() for t in get_all_tools()]
executor = create_executor(api_key="YOUR_KEY")

# Feed tools to chat completion, execute tool_calls with executor
```

See `examples/openai_function_calling.py` in the [capsolver-ai hub repo](https://github.com/capsolver-ai/capsolver-ai).

### OpenAI Agents SDK

```python
import json
from agents import function_tool
from capsolver_agent.schema import create_executor

executor = create_executor(api_key="YOUR_KEY")

@function_tool
async def solve_captcha(captcha_type: str, website_url: str, website_key: str) -> str:
    """Solve a captcha via the CapSolver API and return the result."""
    result = await executor.execute("solve_captcha", {
        "captcha_type": captcha_type,
        "website_url": website_url,
        "website_key": website_key,
    })
    return json.dumps(result)
```

See `examples/openai_agents.py` in the [capsolver-ai hub repo](https://github.com/capsolver-ai/capsolver-ai).

### Claude Agent SDK

Use the `schema.py` tool schemas with Claude's tool use API:

```python
from capsolver_agent.schema import get_all_tools, create_executor

tools = [t.to_openai_function() for t in get_all_tools()]
executor = create_executor(api_key="YOUR_KEY")

# Pass tools as Anthropic tool definitions in your API call
# Execute tool_use blocks with executor.execute(name, arguments)
```

### Mistral AI

Mistral supports function calling with the same schema format:

```python
from capsolver_agent.schema import get_all_tools, create_executor

tools = [t.to_openai_function() for t in get_all_tools()]
executor = create_executor(api_key="YOUR_KEY")

# Pass tools to mistral client.chat() as tool definitions
# Execute tool_calls returned by the model with executor
```

### LangChain

```python
from capsolver_agent.langchain_tools import get_langchain_tools
from langgraph.prebuilt import create_react_agent

tools = get_langchain_tools(api_key="YOUR_KEY")
agent = create_react_agent(llm, tools)
```

Or import individual tools:

```python
from capsolver_agent.langchain_tools import SolveCaptchaTool, GetBalanceTool

solver = SolveCaptchaTool(api_key="YOUR_KEY")
balance = GetBalanceTool(api_key="YOUR_KEY")
```

See `examples/langchain_agent.py` in the [capsolver-ai hub repo](https://github.com/capsolver-ai/capsolver-ai).

### LlamaIndex

```python
from capsolver_agent.schema import get_all_tools, create_executor
from llama_index.core.tools import FunctionTool

executor = create_executor(api_key="YOUR_KEY")

def solve_captcha(captcha_type: str, website_url: str, website_key: str) -> str:
    import asyncio, json
    result = asyncio.run(executor.execute("solve_captcha", {
        "captcha_type": captcha_type,
        "website_url": website_url,
        "website_key": website_key,
    }))
    return json.dumps(result)

tools = [FunctionTool.from_defaults(fn=solve_captcha)]
```

### CrewAI

```python
from crewai.tools import tool
from capsolver_agent.schema import create_executor

executor = create_executor(api_key="YOUR_KEY")

@tool("Solve Captcha")
def solve_captcha(captcha_type: str, website_url: str, website_key: str) -> str:
    """Solve a captcha and return the token."""
    import asyncio, json
    result = asyncio.run(executor.execute("solve_captcha", {
        "captcha_type": captcha_type,
        "website_url": website_url,
        "website_key": website_key,
    }))
    return json.dumps(result)
```

### Google ADK (Agent Development Kit)

```python
from capsolver_agent.schema import get_all_tools, create_executor

executor = create_executor(api_key="YOUR_KEY")
tools = get_all_tools()

# Map ToolDef schemas to Google ADK function declarations
function_declarations = [
    {
        "name": t.name,
        "description": t.description,
        "parameters": t.parameters,
    }
    for t in tools
]
```

### Vercel AI SDK

For JavaScript/TypeScript projects using Vercel AI SDK, export tool schemas as JSON and call the CapSolver API from your tool handlers:

```python
# Generate schemas from Python, use them in your JS/TS project
from capsolver_agent.schema import get_all_tools
import json

tools = get_all_tools()
schemas = [t.to_openai_function() for t in tools]
print(json.dumps(schemas, indent=2))  # copy to your JS project
```

### Custom Framework

Any framework that accepts JSON Schema tool definitions can use `capsolver-agent`:

```python
from capsolver_agent.schema import get_all_tools, create_executor

# 1. Get schemas
tools = get_all_tools()
schemas = [t.to_json_schema() for t in tools]        # MCP-style
schemas = [t.to_openai_function() for t in tools]     # OpenAI-style

# 2. Execute calls
executor = create_executor(api_key="YOUR_KEY")
result = await executor.execute("solve_captcha", { ... })

# 3. Check result
if result["success"]:
    token = result["solution"]["token"]
else:
    error = result["error"]
```

---

## CLI for Development

```bash
# List all tools with descriptions
capsolver-agent list

# Show JSON Schema for a specific tool
capsolver-agent schema solve_captcha

# Export all tools in OpenAI function-calling format
capsolver-agent schema --format openai

# Export one tool in OpenAI format
capsolver-agent schema --format openai detect_captchas
```

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'capsolver_agent'"**
Install first: `pip install capsolver-agent`.

**"ModuleNotFoundError: No module named 'langchain_core'"**
Install the langchain extra: `pip install capsolver-agent[langchain]`.

**Tool call returns `{"success": false, "error": "..."}`**
Check your `CAPSOLVER_API_KEY` is valid and has balance: `capsolver balance`.

**Browser tools fail with "playwright is required"**
Install browser support: `pip install capsolver-agent[browser]` then `playwright install chromium`.
