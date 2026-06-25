"""LangChain BaseTool implementations for CapSolver.

Provides ready-to-use LangChain tools that can be plugged directly
into any LangChain Agent (ReAct, OpenAI Functions, etc.).

Usage:
    from capsolver_agent.langchain_tools import get_langchain_tools

    tools = get_langchain_tools(api_key="your-api-key")
    # Pass `tools` to your LangChain agent
    agent = create_react_agent(llm, tools, ...)

Or import individual tools:
    from capsolver_agent.langchain_tools import SolveCaptchaTool
    tool = SolveCaptchaTool(api_key="your-api-key")
"""

from __future__ import annotations

import os
from typing import Any, Optional, Type

try:
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel, Field

    _HAS_LANGCHAIN = True
except ImportError:
    _HAS_LANGCHAIN = False

    # Provide stubs so the module can be imported without langchain
    class BaseModel:  # type: ignore[no-redef]
        pass

    class BaseTool:  # type: ignore[no-redef]
        def __init_subclass__(cls, **kwargs: Any) -> None:
            raise ImportError(
                "langchain-core is required for LangChain tools. Install with: pip install capsolver-agent[langchain]"
            )

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[misc]
        return None


def _ensure_langchain() -> None:
    if not _HAS_LANGCHAIN:
        raise ImportError(
            "langchain-core is required for LangChain tools. Install with: pip install capsolver-agent[langchain]"
        )


# ── Input Schemas ─────────────────────────────────────────────────


class SolveCaptchaInput(BaseModel):
    """Input schema for SolveCaptchaTool."""

    captcha_type: str = Field(
        description="Captcha family: reCaptchaV2, reCaptchaV3, or cloudflare."
    )
    website_url: str = Field(description="URL of the page where the captcha appears.")
    website_key: str = Field(description="Site key used by the captcha widget.")
    version: Optional[str] = Field(default=None, description="reCAPTCHA version: v2 or v3.")
    page_action: Optional[str] = Field(default=None, description="Action name for reCAPTCHA v3.")
    min_score: Optional[float] = Field(default=None, description="Minimum score for reCAPTCHA v3 (0.0-1.0).")
    invisible: Optional[bool] = Field(default=None, description="Whether reCAPTCHA is invisible.")
    enterprise: Optional[bool] = Field(default=None, description="Whether this is an Enterprise captcha.")
    s_token: Optional[str] = Field(default=None, description="Enterprise 's' token.")
    cdata: Optional[str] = Field(default=None, description="Cloudflare Turnstile cdata.")
    proxy: Optional[str] = Field(default=None, description="Proxy (e.g. http://user:pass@ip:port).")
    user_agent: Optional[str] = Field(default=None, description="User-Agent string.")
    timeout: Optional[float] = Field(default=None, description="Max wait time in seconds.")
    polling_interval: Optional[float] = Field(default=None, description="Polling interval in seconds.")


class DetectCaptchasInput(BaseModel):
    """Input schema for DetectCaptchasTool."""

    page_url: str = Field(description="URL of the page to scan for captchas.")


class SolveOnPageInput(BaseModel):
    """Input schema for SolveOnPageTool."""

    page_url: str = Field(description="URL of the page to solve captchas on.")
    autofill: Optional[bool] = Field(default=True, description="Autofill solved tokens into the page.")
    timeout: Optional[float] = Field(default=None, description="Max wait time per captcha.")
    polling_interval: Optional[float] = Field(default=None, description="Polling interval in seconds.")


class EmptyInput(BaseModel):
    """Empty input for tools that take no parameters."""

    pass


# ── Tool Implementations ──────────────────────────────────────────


if _HAS_LANGCHAIN:
    from capsolver_agent.schema import ToolExecutor

    class _CapsolverToolBase(BaseTool):
        """Shared base for all CapSolver LangChain tools.

        Holds a cached ``ToolExecutor`` so repeated calls reuse the same
        Capsolver instance instead of constructing a new one each time.
        """

        api_key: str = ""
        _executor: ToolExecutor | None = None  # type: ignore[assignment]

        def _get_executor(self) -> ToolExecutor:
            if self._executor is None:
                from capsolver_agent.schema import create_executor

                self._executor = create_executor(api_key=self.api_key)
            return self._executor

        def _run(self, **kwargs: Any) -> dict[str, Any]:
            raise NotImplementedError("Use arun() — CapSolver tools are async.")

    class SolveCaptchaTool(_CapsolverToolBase):
        """Solve a captcha via CapSolver API (token mode, no browser required)."""

        name: str = "solve_captcha"
        description: str = (
            "Solve a captcha using the CapSolver API. Supports reCaptchaV2, "
            "reCaptchaV3, and Cloudflare Turnstile. Returns the solved token."
        )
        args_schema: Type[BaseModel] = SolveCaptchaInput  # type: ignore[assignment]

        async def _arun(self, **kwargs: Any) -> dict[str, Any]:
            return await self._get_executor().execute("solve_captcha", kwargs)

    class DetectCaptchasTool(_CapsolverToolBase):
        """Detect captcha types on a web page (requires playwright)."""

        name: str = "detect_captchas"
        description: str = (
            "Scan a web page and detect which captcha types are present. "
            "Returns a list of detected captcha families. Requires playwright."
        )
        args_schema: Type[BaseModel] = DetectCaptchasInput  # type: ignore[assignment]

        async def _arun(self, **kwargs: Any) -> dict[str, Any]:
            return await self._get_executor().execute("detect_captchas", kwargs)

    class SolveOnPageTool(_CapsolverToolBase):
        """Detect, solve, and autofill captchas on a page (requires playwright)."""

        name: str = "solve_on_page"
        description: str = (
            "One-shot: open a page, detect all captchas, solve them, and autofill tokens. Requires playwright."
        )
        args_schema: Type[BaseModel] = SolveOnPageInput  # type: ignore[assignment]

        async def _arun(self, **kwargs: Any) -> dict[str, Any]:
            return await self._get_executor().execute("solve_on_page", kwargs)

    class GetBalanceTool(_CapsolverToolBase):
        """Get CapSolver account balance."""

        name: str = "get_balance"
        description: str = "Get the current CapSolver account balance and package information."
        args_schema: Type[BaseModel] = EmptyInput  # type: ignore[assignment]

        async def _arun(self, **kwargs: Any) -> dict[str, Any]:
            return await self._get_executor().execute("get_balance", kwargs)

    class GetSupportedCaptchasTool(_CapsolverToolBase):
        """List supported captcha types."""

        name: str = "get_supported_captchas"
        description: str = "List all captcha types supported by this CapSolver instance."
        args_schema: Type[BaseModel] = EmptyInput  # type: ignore[assignment]

        async def _arun(self, **kwargs: Any) -> dict[str, Any]:
            return await self._get_executor().execute("get_supported_captchas", kwargs)

else:
    # Stubs when langchain is not installed
    SolveCaptchaTool = None  # type: ignore[assignment,misc]
    DetectCaptchasTool = None  # type: ignore[assignment,misc]
    SolveOnPageTool = None  # type: ignore[assignment,misc]
    GetBalanceTool = None  # type: ignore[assignment,misc]
    GetSupportedCaptchasTool = None  # type: ignore[assignment,misc]


# ── Factory ───────────────────────────────────────────────────────


def get_langchain_tools(api_key: str | None = None) -> list[Any]:
    """Create all LangChain tools, ready to pass to an Agent.

    Args:
        api_key: CapSolver API key. Falls back to CAPSOLVER_API_KEY env var.

    Returns:
        A list of BaseTool instances.

    Raises:
        ImportError: If langchain-core is not installed.
    """
    _ensure_langchain()
    key = api_key or os.environ.get("CAPSOLVER_API_KEY", "")
    return [
        SolveCaptchaTool(api_key=key),
        DetectCaptchasTool(api_key=key),
        SolveOnPageTool(api_key=key),
        GetBalanceTool(api_key=key),
        GetSupportedCaptchasTool(api_key=key),
    ]
