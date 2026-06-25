"""CapSolver Agent — tool definitions for AI agent frameworks.

Provides two integration layers:
  - ``schema``  : Framework-agnostic tool definitions (JSON schemas + executor)
  - ``langchain_tools`` : LangChain BaseTool implementations

Usage (framework-agnostic):
    from capsolver_agent.schema import get_all_tools, execute_tool

    tools = get_all_tools()           # list of ToolDef with JSON schemas
    result = await execute_tool("solve_captcha", {...})

Usage (LangChain):
    from capsolver_agent.langchain_tools import get_langchain_tools

    tools = get_langchain_tools(api_key="your-key")
    agent = create_react_agent(llm, tools)
"""

from capsolver_agent.schema import ToolDef, get_all_tools, execute_tool, create_executor

__all__ = [
    "ToolDef",
    "get_all_tools",
    "execute_tool",
    "create_executor",
]
__version__ = "0.1.0"
