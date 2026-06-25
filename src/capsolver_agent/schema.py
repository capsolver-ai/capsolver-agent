"""Framework-agnostic tool schema definitions and executor.

Each tool is described as a ``ToolDef`` — a simple dataclass carrying the
tool's name, description, and JSON Schema for parameters.  Any agent
framework (OpenAI function calling, custom orchestrators, etc.) can
consume these definitions directly.

Usage:
    from capsolver_agent.schema import get_all_tools, create_executor

    executor = create_executor(api_key="your-key")
    tools = get_all_tools()

    # Feed tool schemas to your LLM
    schemas = [t.to_openai_function() for t in tools]

    # Execute a tool call from the LLM response
    result = await executor.execute("solve_captcha", {
        "captcha_type": "reCaptchaV2",
        "website_url": "https://example.com",
        "website_key": "6Le-wvkSAAAAAPBMRT...",
    })
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from capsolver_core import Capsolver, CaptchaInfo, CaptchaType
from capsolver_core.core.errors import CapsolverError, CapsolverTimeoutError, NetworkError, RateLimitError


def _error_response(exc: Exception) -> dict[str, Any]:
    """Build a consistent error dict from an exception.

    Extracts structured fields from CapsolverError when available.
    """
    base: dict[str, Any] = {"success": False, "error": str(exc)}
    if isinstance(exc, CapsolverTimeoutError) and exc.task_id is not None:
        base["task_id"] = exc.task_id
    if isinstance(exc, NetworkError) and exc.cause is not None:
        base["cause"] = str(exc.cause)
    if isinstance(exc, RateLimitError):
        base["error_type"] = "rate_limit"
    if isinstance(exc, CapsolverError):
        if exc.error_id is not None:
            base["error_id"] = exc.error_id
        if exc.error_code:
            base["error_code"] = exc.error_code
        if exc.error_description:
            base["error_description"] = exc.error_description
        if exc.http_status is not None:
            base["http_status"] = exc.http_status
    return base


# ── Tool Schema ───────────────────────────────────────────────────


@dataclass
class ToolDef:
    """Framework-agnostic definition of a single tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_json_schema(self) -> dict[str, Any]:
        """Return the full tool spec as a JSON-schema-compatible dict."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters,
        }


# ── Tool Definitions ─────────────────────────────────────────────


_SOLVE_CAPTCHA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "captcha_type": {
            "type": "string",
            "enum": ["reCaptchaV2", "reCaptchaV3", "cloudflare"],
            "description": "The captcha family to solve.",
        },
        "website_url": {
            "type": "string",
            "description": "The URL of the page where the captcha appears.",
        },
        "website_key": {
            "type": "string",
            "description": "The site key used by the captcha widget.",
        },
        "version": {
            "type": ["string", "null"],
            "enum": ["v2", "v3", None],
            "description": "reCAPTCHA version (v2 or v3). Only for reCAPTCHA.",
        },
        "page_action": {
            "type": ["string", "null"],
            "description": "The action name for reCAPTCHA v3.",
        },
        "min_score": {
            "type": ["number", "null"],
            "description": "Minimum score for reCAPTCHA v3 (0.0 - 1.0).",
        },
        "invisible": {
            "type": ["boolean", "null"],
            "description": "Whether the reCAPTCHA widget uses invisible mode.",
        },
        "enterprise": {
            "type": ["boolean", "null"],
            "description": "Whether this is an Enterprise captcha.",
        },
        "s_token": {
            "type": ["string", "null"],
            "description": "Enterprise 's' token.",
        },
        "cdata": {
            "type": ["string", "null"],
            "description": "Cloudflare Turnstile cdata parameter.",
        },
        "proxy": {
            "type": ["string", "null"],
            "description": "Proxy string (e.g. http://user:pass@ip:port).",
        },
        "user_agent": {
            "type": ["string", "null"],
            "description": "User-Agent string to use for solving.",
        },
        "timeout": {
            "type": ["number", "null"],
            "description": "Max seconds to wait for a solution (default: 120).",
        },
        "polling_interval": {
            "type": ["number", "null"],
            "description": "Seconds between polling attempts (default: 5).",
        },
    },
    "required": ["captcha_type", "website_url", "website_key"],
}

_DETECT_CAPTCHAS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_url": {
            "type": "string",
            "description": "URL of the page to scan for captchas.",
        },
    },
    "required": ["page_url"],
}

_SOLVE_ON_PAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_url": {
            "type": "string",
            "description": "URL of the page to solve captchas on.",
        },
        "autofill": {
            "type": ["boolean", "null"],
            "description": "Whether to autofill solved tokens into the page (default: true).",
        },
        "timeout": {
            "type": ["number", "null"],
            "description": "Max seconds to wait per captcha.",
        },
        "polling_interval": {
            "type": ["number", "null"],
            "description": "Seconds between polling attempts.",
        },
    },
    "required": ["page_url"],
}

_GET_BALANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
}

_GET_SUPPORTED_CAPTCHAS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "required": [],
}


def get_all_tools() -> list[ToolDef]:
    """Return framework-agnostic definitions for all CapSolver tools."""
    return [
        ToolDef(
            name="solve_captcha",
            description=(
                "Solve a captcha via the CapSolver API (token mode, no browser required). "
                "Supports reCaptchaV2, reCaptchaV3, and Cloudflare Turnstile. "
                "Returns the solved token that can be submitted with a form or injected into a page."
            ),
            parameters=_SOLVE_CAPTCHA_SCHEMA,
        ),
        ToolDef(
            name="detect_captchas",
            description=(
                "Scan a web page and detect which captcha types are present. "
                "Returns a list of captcha families found on the page. "
                "Requires browser automation support (playwright)."
            ),
            parameters=_DETECT_CAPTCHAS_SCHEMA,
        ),
        ToolDef(
            name="solve_on_page",
            description=(
                "One-shot operation: open a page in a browser, detect all captchas, "
                "solve them, and optionally autofill the solved tokens back into the page. "
                "Requires browser automation support (playwright)."
            ),
            parameters=_SOLVE_ON_PAGE_SCHEMA,
        ),
        ToolDef(
            name="get_balance",
            description="Get the current CapSolver account balance and package information.",
            parameters=_GET_BALANCE_SCHEMA,
        ),
        ToolDef(
            name="get_supported_captchas",
            description="List all captcha types and handler names supported by this CapSolver instance.",
            parameters=_GET_SUPPORTED_CAPTCHAS_SCHEMA,
        ),
    ]


# ── Executor ──────────────────────────────────────────────────────


class ToolExecutor:
    """Executes tool calls against a Capsolver instance.

    This is the bridge between LLM-generated tool calls and the SDK.
    """

    def __init__(self, capsolver: Capsolver) -> None:
        self._capsolver = capsolver

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a tool call by name and return the result.

        Args:
            tool_name: One of the registered tool names.
            arguments: Keyword arguments matching the tool's JSON schema.

        Returns:
            A JSON-serializable dict with the result or error.
        """
        dispatch = {
            "solve_captcha": self._solve_captcha,
            "detect_captchas": self._detect_captchas,
            "solve_on_page": self._solve_on_page,
            "get_balance": self._get_balance,
            "get_supported_captchas": self._get_supported_captchas,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            return {"success": False, "error": f"Unknown tool: {tool_name}. Available: {list(dispatch.keys())}"}

        try:
            return await handler(arguments)
        except Exception as e:
            return _error_response(e)

    # ── private handlers ──────────────────────────────────────────

    async def _solve_captcha(self, args: dict[str, Any]) -> dict[str, Any]:
        try:
            ct = CaptchaType(args["captcha_type"])
        except (ValueError, KeyError) as e:
            return {"success": False, "error": f"Invalid captcha_type: {e}"}

        info = CaptchaInfo(
            type=ct,
            website_url=args.get("website_url", ""),
            website_key=args.get("website_key", ""),
            version=args.get("version"),
            page_action=args.get("page_action"),
            min_score=args.get("min_score"),
            invisible=args.get("invisible"),
            enterprise=args.get("enterprise"),
            s=args.get("s_token"),
            cdata=args.get("cdata"),
            proxy=args.get("proxy"),
            user_agent=args.get("user_agent"),
        )

        from capsolver_core.core.client import WaitOptions

        wait_opts = None
        timeout = args.get("timeout")
        interval = args.get("polling_interval")
        if timeout is not None or interval is not None:
            wait_opts = WaitOptions(timeout=timeout, polling_interval=interval)

        solution = await self._capsolver.solve(info, wait_options=wait_opts)
        return {
            "success": True,
            "solution": {
                "captcha_type": solution.captcha_type.value,
                "token": solution.token,
                "expire_time": solution.expire_time,
                "user_agent": solution.user_agent,
            },
        }

    async def _detect_captchas(self, args: dict[str, Any]) -> dict[str, Any]:
        page_url = args.get("page_url", "")
        if not page_url:
            return {"success": False, "error": "page_url is required"}

        try:
            driver = await _launch_browser(page_url)
        except ImportError:
            return {"success": False, "error": "playwright is required. Install: pip install capsolver-agent[browser]"}

        try:
            detected = await self._capsolver.detect(driver)
            return {
                "success": True,
                "url": page_url,
                "detected_captchas": [t.value for t in detected],
            }
        finally:
            await _close_browser(driver)

    async def _solve_on_page(self, args: dict[str, Any]) -> dict[str, Any]:
        page_url = args.get("page_url", "")
        if not page_url:
            return {"success": False, "error": "page_url is required"}

        try:
            driver = await _launch_browser(page_url)
        except ImportError:
            return {"success": False, "error": "playwright is required. Install: pip install capsolver-agent[browser]"}

        try:
            from capsolver_core.capsolver import SolveOnPageOptions

            opts = SolveOnPageOptions(
                autofill=args.get("autofill", True),
                throw_on_error=False,
                timeout=args.get("timeout"),
                polling_interval=args.get("polling_interval"),
            )
            results = await self._capsolver.solve_on_page(driver, options=opts)
            return {
                "success": True,
                "url": page_url,
                "results": [
                    {
                        "captcha_type": r.info.type.value,
                        "solved": r.solution is not None,
                        "token": r.solution.token if r.solution else None,
                        "filled": r.filled,
                        "error": r.error,
                    }
                    for r in results
                ],
            }
        finally:
            await _close_browser(driver)

    async def _get_balance(self, _args: dict[str, Any]) -> dict[str, Any]:
        balance = await self._capsolver.get_balance()
        return {"success": True, "balance": balance.balance, "packages": balance.packages}

    async def _get_supported_captchas(self, _args: dict[str, Any]) -> dict[str, Any]:
        handlers = self._capsolver.get_supported_captchas()
        return {
            "success": True,
            "registered_handlers": handlers,
            "captcha_types": [t.value for t in CaptchaType],
        }


def create_executor(
    api_key: str | None = None,
    **capsolver_kwargs: Any,
) -> ToolExecutor:
    """Create a ToolExecutor backed by a Capsolver instance.

    Args:
        api_key: CapSolver API key. Falls back to CAPSOLVER_API_KEY env var.
        **capsolver_kwargs: Extra arguments forwarded to Capsolver(...).
    """
    key = api_key or os.environ.get("CAPSOLVER_API_KEY", "")
    capsolver = Capsolver(api_key=key, **capsolver_kwargs)
    return ToolExecutor(capsolver)


# Convenience: module-level executor for quick usage
async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    api_key: str | None = None,
) -> dict[str, Any]:
    """One-shot convenience: create an executor and run a single tool call.

    For repeated calls, prefer ``create_executor()`` to reuse the same instance.
    """
    executor = create_executor(api_key=api_key)
    return await executor.execute(tool_name, arguments)


# ── Browser helpers (shared with MCP server) ──────────────────────


async def _launch_browser(page_url: str) -> Any:
    """Launch headless Chromium and navigate to page_url. Returns a PageDriver."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise

    from capsolver_core.browser.adapter import from_playwright_page

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)

    # Captcha widgets (reCAPTCHA api.js, Turnstile) load asynchronously after
    # DOMContentLoaded. Wait for the network to settle so their scripts can
    # register before we detect — bounded so pages with long-lived
    # connections don't hang. Best-effort: ignore timeout.
    try:
        await page.wait_for_load_state("networkidle", timeout=5_000)
    except Exception:
        pass

    driver = from_playwright_page(page)
    driver._pw = pw
    driver._browser = browser
    return driver


async def _close_browser(driver: Any) -> None:
    """Clean up browser resources."""
    try:
        if hasattr(driver, "_browser") and driver._browser:
            await driver._browser.close()
        if hasattr(driver, "_pw") and driver._pw:
            await driver._pw.stop()
    except Exception:
        pass
