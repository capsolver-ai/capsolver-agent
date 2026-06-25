"""Comprehensive tests for capsolver-agent: schema, executor, and LangChain tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from capsolver_agent.schema import (
    ToolExecutor,
    create_executor,
    execute_tool,
    get_all_tools,
)


# ══════════════════════════════════════════════════════════════════
#  ToolDef schema tests
# ══════════════════════════════════════════════════════════════════


class TestGetAllTools:
    """Verify the set and structure of framework-agnostic tool definitions."""

    def test_returns_five_tools(self) -> None:
        tools = get_all_tools()
        assert len(tools) == 5

    def test_tool_names(self) -> None:
        names = {t.name for t in get_all_tools()}
        assert names == {
            "solve_captcha",
            "detect_captchas",
            "solve_on_page",
            "get_balance",
            "get_supported_captchas",
        }

    def test_all_have_descriptions(self) -> None:
        for tool in get_all_tools():
            assert tool.description, f"{tool.name} has empty description"

    def test_all_have_parameters(self) -> None:
        for tool in get_all_tools():
            assert isinstance(tool.parameters, dict), f"{tool.name} parameters is not a dict"
            assert "type" in tool.parameters, f"{tool.name} parameters missing 'type'"
            assert "properties" in tool.parameters, f"{tool.name} parameters missing 'properties'"

    def test_solve_captcha_required_fields(self) -> None:
        tools = {t.name: t for t in get_all_tools()}
        required = tools["solve_captcha"].parameters["required"]
        assert "captcha_type" in required
        assert "website_url" in required
        assert "website_key" in required

    def test_detect_captchas_requires_page_url(self) -> None:
        tools = {t.name: t for t in get_all_tools()}
        required = tools["detect_captchas"].parameters["required"]
        assert required == ["page_url"]

    def test_solve_on_page_requires_page_url(self) -> None:
        tools = {t.name: t for t in get_all_tools()}
        required = tools["solve_on_page"].parameters["required"]
        assert required == ["page_url"]

    def test_get_balance_no_required(self) -> None:
        tools = {t.name: t for t in get_all_tools()}
        assert tools["get_balance"].parameters["required"] == []

    def test_get_supported_captchas_no_required(self) -> None:
        tools = {t.name: t for t in get_all_tools()}
        assert tools["get_supported_captchas"].parameters["required"] == []

    def test_solve_captcha_enum_values(self) -> None:
        tools = {t.name: t for t in get_all_tools()}
        enum_vals = tools["solve_captcha"].parameters["properties"]["captcha_type"]["enum"]
        assert set(enum_vals) == {"reCaptchaV2", "reCaptchaV3", "cloudflare"}


class TestToolDefSerialization:
    """Test to_openai_function() and to_json_schema() for every tool."""

    @pytest.mark.parametrize("tool_idx", range(5))
    def test_to_openai_function(self, tool_idx: int) -> None:
        tool = get_all_tools()[tool_idx]
        fn = tool.to_openai_function()
        assert fn["type"] == "function"
        assert fn["function"]["name"] == tool.name
        assert fn["function"]["description"] == tool.description
        assert fn["function"]["parameters"] is tool.parameters

    @pytest.mark.parametrize("tool_idx", range(5))
    def test_to_json_schema(self, tool_idx: int) -> None:
        tool = get_all_tools()[tool_idx]
        schema = tool.to_json_schema()
        assert schema["name"] == tool.name
        assert schema["description"] == tool.description
        assert schema["inputSchema"] is tool.parameters


# ══════════════════════════════════════════════════════════════════
#  ToolExecutor tests
# ══════════════════════════════════════════════════════════════════


class TestToolExecutor:
    """Test the ToolExecutor dispatch and error handling."""

    def test_create_executor(self) -> None:
        executor = create_executor(api_key="test-key-123")
        assert isinstance(executor, ToolExecutor)

    def test_create_executor_kwargs_forwarded(self) -> None:
        executor = create_executor(api_key="test-key", service="https://custom.api.com")
        assert executor._capsolver._client_options.service == "https://custom.api.com"

    def test_create_executor_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CAPSOLVER_API_KEY", "env-key-456")
        executor = create_executor()
        assert executor._capsolver._client_options.api_key == "env-key-456"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self) -> None:
        executor = create_executor(api_key="test-key-123")
        result = await executor.execute("nonexistent_tool", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]
        assert "Available" in result["error"]

    @pytest.mark.asyncio
    async def test_get_supported_captchas(self) -> None:
        executor = create_executor(api_key="test-key-123")
        result = await executor.execute("get_supported_captchas", {})
        assert result["success"] is True
        assert isinstance(result["registered_handlers"], list)
        assert len(result["registered_handlers"]) > 0
        assert isinstance(result["captcha_types"], list)
        assert "reCaptchaV2" in result["captcha_types"]

    @pytest.mark.asyncio
    async def test_solve_captcha_invalid_type(self) -> None:
        executor = create_executor(api_key="test-key-123")
        result = await executor.execute(
            "solve_captcha",
            {
                "captcha_type": "invalidType",
                "website_url": "https://example.com",
                "website_key": "abc123",
            },
        )
        assert result["success"] is False
        assert "Invalid captcha_type" in result["error"]

    @pytest.mark.asyncio
    async def test_solve_captcha_success(self) -> None:
        """Mock Capsolver.solve to return a fake solution."""
        from capsolver_core.captcha.types import Solution
        from capsolver_core.core.types import CaptchaType

        fake_solution = Solution(
            captcha_type=CaptchaType.RECAPTCHA_V2,
            token="fake-token-abc",
            expire_time=1234567890,
            user_agent="Mozilla/5.0",
        )
        executor = create_executor(api_key="test-key")
        executor._capsolver = MagicMock()
        executor._capsolver.solve = AsyncMock(return_value=fake_solution)

        result = await executor.execute(
            "solve_captcha",
            {
                "captcha_type": "reCaptchaV2",
                "website_url": "https://example.com",
                "website_key": "6Lc...",
            },
        )
        assert result["success"] is True
        assert result["solution"]["token"] == "fake-token-abc"
        assert result["solution"]["captcha_type"] == "reCaptchaV2"
        assert result["solution"]["expire_time"] == 1234567890

    @pytest.mark.asyncio
    async def test_solve_captcha_with_optional_params(self) -> None:
        """Verify optional params (version, proxy, timeout) are forwarded."""
        from capsolver_core.captcha.types import Solution
        from capsolver_core.core.types import CaptchaType

        fake_solution = Solution(captcha_type=CaptchaType.RECAPTCHA_V3, token="v3-token")
        executor = create_executor(api_key="test-key")
        executor._capsolver = MagicMock()
        executor._capsolver.solve = AsyncMock(return_value=fake_solution)

        result = await executor.execute(
            "solve_captcha",
            {
                "captcha_type": "reCaptchaV3",
                "website_url": "https://example.com",
                "website_key": "6Lc...",
                "version": "v3",
                "page_action": "login",
                "min_score": 0.7,
                "proxy": "http://proxy:8080",
                "timeout": 60,
                "polling_interval": 2,
            },
        )
        assert result["success"] is True
        # Verify solve was called with a CaptchaInfo carrying the optional fields
        call_args = executor._capsolver.solve.call_args
        info = call_args[0][0]
        assert info.version == "v3"
        assert info.page_action == "login"
        assert info.min_score == 0.7
        assert info.proxy == "http://proxy:8080"
        # Verify wait_options were set
        wait_opts = (
            call_args[1].get("wait_options") or call_args[0][1]
            if len(call_args[0]) > 1
            else call_args[1]["wait_options"]
        )
        assert wait_opts is not None
        assert wait_opts.timeout == 60
        assert wait_opts.polling_interval == 2

    @pytest.mark.asyncio
    async def test_solve_captcha_api_error(self) -> None:
        """When Capsolver.solve raises, executor returns error dict."""
        from capsolver_core.core.errors import CapsolverError

        executor = create_executor(api_key="test-key")
        executor._capsolver = MagicMock()
        executor._capsolver.solve = AsyncMock(side_effect=CapsolverError("API rate limit"))

        result = await executor.execute(
            "solve_captcha",
            {
                "captcha_type": "reCaptchaV2",
                "website_url": "https://example.com",
                "website_key": "abc",
            },
        )
        assert result["success"] is False
        assert "API rate limit" in result["error"]

    @pytest.mark.asyncio
    async def test_get_balance_success(self) -> None:
        mock_balance = MagicMock()
        mock_balance.balance = 12.34
        mock_balance.packages = [{"name": "pro"}]

        executor = create_executor(api_key="test-key")
        executor._capsolver = MagicMock()
        executor._capsolver.get_balance = AsyncMock(return_value=mock_balance)

        result = await executor.execute("get_balance", {})
        assert result["success"] is True
        assert result["balance"] == 12.34
        assert result["packages"] == [{"name": "pro"}]

    @pytest.mark.asyncio
    async def test_get_balance_error(self) -> None:
        from capsolver_core.core.errors import CapsolverError

        executor = create_executor(api_key="test-key")
        executor._capsolver = MagicMock()
        executor._capsolver.get_balance = AsyncMock(side_effect=CapsolverError("Invalid key"))

        result = await executor.execute("get_balance", {})
        assert result["success"] is False
        assert "Invalid key" in result["error"]

    @pytest.mark.asyncio
    async def test_detect_captchas_missing_page_url(self) -> None:
        executor = create_executor(api_key="test-key")
        result = await executor.execute("detect_captchas", {})
        assert result["success"] is False
        assert "page_url is required" in result["error"]

    @pytest.mark.asyncio
    async def test_detect_captchas_no_playwright(self) -> None:
        """When playwright is not installed, ImportError is caught."""
        executor = create_executor(api_key="test-key")
        with patch(
            "capsolver_agent.schema._launch_browser",
            new_callable=AsyncMock,
            side_effect=ImportError("playwright is required"),
        ):
            result = await executor.execute("detect_captchas", {"page_url": "https://example.com"})
        assert result["success"] is False
        assert "playwright" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_detect_captchas_success_mocked(self) -> None:
        """Mock browser + detect to verify executor wiring."""
        from capsolver_core.core.types import CaptchaType

        executor = create_executor(api_key="test-key")
        mock_driver = MagicMock()
        mock_driver.page = MagicMock()

        executor._capsolver = MagicMock()
        executor._capsolver.detect = AsyncMock(return_value=[CaptchaType.RECAPTCHA_V2])

        with (
            patch("capsolver_agent.schema._launch_browser", new_callable=AsyncMock, return_value=mock_driver),
            patch("capsolver_agent.schema._close_browser", new_callable=AsyncMock),
        ):
            result = await executor.execute("detect_captchas", {"page_url": "https://example.com"})
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert "reCaptchaV2" in result["detected_captchas"]

    @pytest.mark.asyncio
    async def test_solve_on_page_missing_page_url(self) -> None:
        executor = create_executor(api_key="test-key")
        result = await executor.execute("solve_on_page", {})
        assert result["success"] is False
        assert "page_url is required" in result["error"]

    @pytest.mark.asyncio
    async def test_solve_on_page_no_playwright(self) -> None:
        """When playwright is not installed, ImportError is caught."""
        executor = create_executor(api_key="test-key")
        with patch(
            "capsolver_agent.schema._launch_browser",
            new_callable=AsyncMock,
            side_effect=ImportError("playwright is required"),
        ):
            result = await executor.execute("solve_on_page", {"page_url": "https://example.com"})
        assert result["success"] is False
        assert "playwright" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_solve_on_page_success_mocked(self) -> None:
        """Mock browser + solve_on_page to verify executor wiring."""
        from capsolver_core.captcha.types import Solution
        from capsolver_core.core.types import CaptchaType

        executor = create_executor(api_key="test-key")
        mock_driver = MagicMock()
        mock_driver.page = MagicMock()

        # Build fake SolveOnPageResult entries
        fake_info = MagicMock()
        fake_info.type = CaptchaType.RECAPTCHA_V2

        fake_result = MagicMock()
        fake_result.info = fake_info
        fake_result.solution = Solution(captcha_type=CaptchaType.RECAPTCHA_V2, token="solved-token")
        fake_result.filled = True
        fake_result.error = None

        executor._capsolver = MagicMock()
        executor._capsolver.solve_on_page = AsyncMock(return_value=[fake_result])

        with (
            patch("capsolver_agent.schema._launch_browser", new_callable=AsyncMock, return_value=mock_driver),
            patch("capsolver_agent.schema._close_browser", new_callable=AsyncMock),
        ):
            result = await executor.execute(
                "solve_on_page",
                {
                    "page_url": "https://example.com",
                    "autofill": True,
                },
            )
        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert len(result["results"]) == 1
        assert result["results"][0]["solved"] is True
        assert result["results"][0]["token"] == "solved-token"
        assert result["results"][0]["filled"] is True


# ══════════════════════════════════════════════════════════════════
#  execute_tool convenience function
# ══════════════════════════════════════════════════════════════════


class TestExecuteToolConvenience:
    """Test the one-shot execute_tool helper."""

    @pytest.mark.asyncio
    async def test_execute_tool_returns_supported_captchas(self) -> None:
        result = await execute_tool("get_supported_captchas", {}, api_key="test-key")
        assert result["success"] is True
        assert "captcha_types" in result

    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self) -> None:
        result = await execute_tool("bogus", {}, api_key="test-key")
        assert result["success"] is False


# ══════════════════════════════════════════════════════════════════
#  LangChain tool tests
# ══════════════════════════════════════════════════════════════════


class TestLangChainTools:
    """Test LangChain BaseTool integration (requires langchain-core)."""

    def test_get_langchain_tools_returns_five(self) -> None:
        from capsolver_agent.langchain_tools import get_langchain_tools

        tools = get_langchain_tools(api_key="test-key")
        assert len(tools) == 5

    def test_get_langchain_tools_names(self) -> None:
        from capsolver_agent.langchain_tools import get_langchain_tools

        tools = get_langchain_tools(api_key="test-key")
        names = {t.name for t in tools}
        assert names == {
            "solve_captcha",
            "detect_captchas",
            "solve_on_page",
            "get_balance",
            "get_supported_captchas",
        }

    def test_get_langchain_tools_descriptions(self) -> None:
        from capsolver_agent.langchain_tools import get_langchain_tools

        tools = get_langchain_tools(api_key="test-key")
        for tool in tools:
            assert tool.description, f"{tool.name} has empty description"

    def test_get_langchain_tools_have_args_schema(self) -> None:
        from capsolver_agent.langchain_tools import get_langchain_tools

        tools = get_langchain_tools(api_key="test-key")
        for tool in tools:
            assert tool.args_schema is not None, f"{tool.name} missing args_schema"

    def test_individual_tool_import(self) -> None:
        from capsolver_agent.langchain_tools import (
            SolveCaptchaTool,
            DetectCaptchasTool,
            SolveOnPageTool,
            GetBalanceTool,
            GetSupportedCaptchasTool,
        )

        assert SolveCaptchaTool is not None
        assert DetectCaptchasTool is not None
        assert SolveOnPageTool is not None
        assert GetBalanceTool is not None
        assert GetSupportedCaptchasTool is not None

    def test_tool_sync_run_raises(self) -> None:
        from capsolver_agent.langchain_tools import SolveCaptchaTool

        tool = SolveCaptchaTool(api_key="test")
        with pytest.raises(NotImplementedError, match="arun"):
            tool._run()

    @pytest.mark.asyncio
    async def test_solve_captcha_tool_arun(self) -> None:
        """LangChain SolveCaptchaTool delegates to executor correctly."""
        from capsolver_core.captcha.types import Solution
        from capsolver_core.core.types import CaptchaType
        from capsolver_agent.langchain_tools import SolveCaptchaTool
        from capsolver_agent.schema import ToolExecutor

        Solution(captcha_type=CaptchaType.RECAPTCHA_V2, token="rc-token")

        tool = SolveCaptchaTool(api_key="test-key")
        mock_executor = MagicMock(spec=ToolExecutor)
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "solution": {"captcha_type": "reCaptchaV2", "token": "rc-token"},
            }
        )
        tool._executor = mock_executor

        result = await tool._arun(
            captcha_type="reCaptchaV2",
            website_url="https://example.com",
            website_key="abc",
        )
        assert result["success"] is True
        mock_executor.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_supported_captchas_tool_arun(self) -> None:
        from capsolver_agent.langchain_tools import GetSupportedCaptchasTool
        from capsolver_agent.schema import ToolExecutor

        tool = GetSupportedCaptchasTool(api_key="test-key")
        mock_executor = MagicMock(spec=ToolExecutor)
        mock_executor.execute = AsyncMock(
            return_value={
                "success": True,
                "registered_handlers": ["reCaptchaV2"],
                "captcha_types": ["reCaptchaV2"],
            }
        )
        tool._executor = mock_executor

        result = await tool._arun()
        assert result["success"] is True

    def test_executor_caching(self) -> None:
        """_get_executor() should return the same instance on repeated calls."""
        from capsolver_agent.langchain_tools import SolveCaptchaTool

        tool = SolveCaptchaTool(api_key="test-key")
        e1 = tool._get_executor()
        e2 = tool._get_executor()
        assert e1 is e2


# ══════════════════════════════════════════════════════════════════
#  Input schema validation
# ══════════════════════════════════════════════════════════════════


class TestInputSchemas:
    """Verify Pydantic input schemas behave correctly."""

    def test_solve_captcha_input_required(self) -> None:
        from capsolver_agent.langchain_tools import SolveCaptchaInput

        with pytest.raises(Exception):
            SolveCaptchaInput()  # missing required fields

    def test_solve_captcha_input_valid(self) -> None:
        from capsolver_agent.langchain_tools import SolveCaptchaInput

        inp = SolveCaptchaInput(
            captcha_type="reCaptchaV2",
            website_url="https://example.com",
            website_key="6Lc...",
        )
        assert inp.captcha_type == "reCaptchaV2"
        assert inp.version is None

    def test_solve_captcha_input_with_optionals(self) -> None:
        from capsolver_agent.langchain_tools import SolveCaptchaInput

        inp = SolveCaptchaInput(
            captcha_type="reCaptchaV3",
            website_url="https://example.com",
            website_key="6Lc...",
            version="v3",
            page_action="login",
            min_score=0.8,
            enterprise=True,
        )
        assert inp.version == "v3"
        assert inp.page_action == "login"
        assert inp.min_score == 0.8

    def test_detect_captchas_input(self) -> None:
        from capsolver_agent.langchain_tools import DetectCaptchasInput

        inp = DetectCaptchasInput(page_url="https://example.com")
        assert inp.page_url == "https://example.com"

    def test_solve_on_page_input_defaults(self) -> None:
        from capsolver_agent.langchain_tools import SolveOnPageInput

        inp = SolveOnPageInput(page_url="https://example.com")
        assert inp.autofill is True
        assert inp.timeout is None

    def test_empty_input(self) -> None:
        from capsolver_agent.langchain_tools import EmptyInput

        inp = EmptyInput()
        assert inp is not None

    def test_solve_captcha_input_remaining_optionals(self) -> None:
        """Cover s_token, cdata, proxy, user_agent, timeout, polling_interval."""
        from capsolver_agent.langchain_tools import SolveCaptchaInput

        inp = SolveCaptchaInput(
            captcha_type="cloudflare",
            website_url="https://example.com",
            website_key="cf-key",
            s_token="s-tok",
            cdata="cf-data",
            proxy="http://user:pass@ip:8080",
            user_agent="Mozilla/5.0 Custom",
            timeout=90.0,
            polling_interval=3.0,
        )
        assert inp.s_token == "s-tok"
        assert inp.cdata == "cf-data"
        assert inp.proxy == "http://user:pass@ip:8080"
        assert inp.user_agent == "Mozilla/5.0 Custom"
        assert inp.timeout == 90.0
        assert inp.polling_interval == 3.0

    def test_solve_captcha_input_defaults_all_none(self) -> None:
        """Every optional field should default to None."""
        from capsolver_agent.langchain_tools import SolveCaptchaInput

        inp = SolveCaptchaInput(
            captcha_type="reCaptchaV2",
            website_url="https://example.com",
            website_key="key",
        )
        assert inp.s_token is None
        assert inp.cdata is None
        assert inp.proxy is None
        assert inp.user_agent is None
        assert inp.timeout is None
        assert inp.polling_interval is None
        assert inp.invisible is None
        assert inp.enterprise is None

    def test_solve_on_page_input_explicit_values(self) -> None:
        """timeout and polling_interval can be set explicitly."""
        from capsolver_agent.langchain_tools import SolveOnPageInput

        inp = SolveOnPageInput(
            page_url="https://example.com",
            autofill=False,
            timeout=60.0,
            polling_interval=2.5,
        )
        assert inp.autofill is False
        assert inp.timeout == 60.0
        assert inp.polling_interval == 2.5
