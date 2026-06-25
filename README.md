# capsolver-agent

Agent integrations for [CapSolver](https://capsolver.com) — framework-agnostic tool definitions and LangChain BaseTool implementations.

See the [capsolver-ai](https://github.com/capsolver-ai/capsolver-ai) hub repo for integration examples and the full documentation.

For framework integration guides (OpenAI, LangChain, LlamaIndex, CrewAI, Google ADK, and more), see [docs/agent-integration.md](docs/agent-integration.md).

## Install

```bash
pip install capsolver-agent
pip install capsolver-agent[langchain]   # with LangChain support
pip install capsolver-agent[browser]     # with Playwright support (for detect/solve_on_page)
```

All packages read the API key from the environment:

```bash
# bash / zsh
export CAPSOLVER_API_KEY="your-capsolver-api-key"

# PowerShell
$env:CAPSOLVER_API_KEY = "your-capsolver-api-key"

# cmd
set CAPSOLVER_API_KEY=your-capsolver-api-key
```

## Framework-agnostic tools (any LLM / agent framework)

Use `schema.py` to get tool schemas as JSON and an async executor to run tool calls. Works with OpenAI function calling, OpenAI Agents SDK, Browser Use, or any custom agent loop.

```python
import asyncio
from capsolver_agent.schema import get_all_tools, create_executor

async def main():
    # 1. Get tool schemas — feed to your LLM's function-calling API
    tools = get_all_tools()
    openai_functions = [t.to_openai_function() for t in tools]

    # 2. Execute a tool call returned by the LLM
    executor = create_executor(api_key="YOUR_API_KEY")
    result = await executor.execute("solve_captcha", {
        "captcha_type": "reCaptchaV2",
        "website_url": "https://example.com",
        "website_key": "6Le-wvkSAAAAAPBMRT...",
    })
    print(result)
    # {"success": True, "solution": {"token": "03AF...", ...}}

asyncio.run(main())
```

Each `ToolDef` provides two export formats:

```python
tool = get_all_tools()[0]
tool.to_openai_function()  # → OpenAI function-calling schema
tool.to_json_schema()      # → MCP-style tool descriptor (name + inputSchema)
```

For a quick one-shot call without creating an executor:

```python
from capsolver_agent.schema import execute_tool

result = await execute_tool("solve_captcha", {
    "captcha_type": "reCaptchaV2",
    "website_url": "https://example.com",
    "website_key": "6Le-wvkSAAAAAPBMRT...",
}, api_key="YOUR_API_KEY")
```

## LangChain integration

Pre-built `BaseTool` subclasses with Pydantic input schemas — plug directly into any LangChain agent.

```python
import asyncio
from capsolver_agent.langchain_tools import get_langchain_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

tools = get_langchain_tools(api_key="YOUR_API_KEY")

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, tools)

async def main():
    result = await agent.ainvoke({"messages": [...]})

asyncio.run(main())
```

Or import individual tools:

```python
from capsolver_agent.langchain_tools import SolveCaptchaTool, GetBalanceTool

solver = SolveCaptchaTool(api_key="YOUR_API_KEY")
balance = GetBalanceTool(api_key="YOUR_API_KEY")
```

## CLI

The `capsolver-agent` command lets you inspect available tools and their schemas from the terminal.

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

Also works via `python -m capsolver_agent list`.

## Available tools

| Tool | Browser? | Description |
|---|---|---|
| `solve_captcha` | No | Token-mode solving — provide type + URL + site key, get a token back |
| `detect_captchas` | Yes | Scan a page URL and return which captcha types are present |
| `solve_on_page` | Yes | One-shot: detect + solve + autofill all captchas on a page |
| `get_balance` | No | Check account balance and packages |
| `get_supported_captchas` | No | List all supported captcha types and handler names |

Browser-based tools require `pip install capsolver-agent[browser]` and `playwright install chromium`.

## Integration examples

See the [capsolver-ai examples](https://github.com/capsolver-ai/capsolver-ai/tree/main/examples) for runnable demos:

- `openai_function_calling.py` — agentic loop with OpenAI function calling
- `openai_agents.py` — OpenAI Agents SDK with `@function_tool`
- `langchain_agent.py` — LangChain ReAct agent
- `browser_use_agent.py` — Browser Use with `@tools.action()`

## Development

```bash
git clone https://github.com/capsolver-ai/agent-capsolver.git
cd agent-capsolver
uv sync --all-extras          # or: pip install -r requirements-dev.txt
uv run pytest                 # run tests
uv run ruff check src tests   # lint
```

## License

ISC
