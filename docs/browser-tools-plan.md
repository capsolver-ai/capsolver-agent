## Agent-Capsolver Browser Tools Integration Plan

### Goal

Add persistent browser session management and interaction tools to `agent-capsolver`, enabling AI agents to autonomously navigate pages, interact with elements, and solve captchas within a single browser session. This transforms the package from a "captcha solving toolkit" into a "captcha-aware browser automation toolkit" for AI agents.

### Design Principles

1. **Backward compatible**: All 5 existing captcha tools continue to work exactly as before.
2. **Session-scoped browser**: A persistent Playwright browser session lives on the `ToolExecutor`, shared across all browser + captcha tool calls.
3. **CSS selector based**: Element references use standard CSS selectors — simple, well-understood, and consistent with the SDK's existing `wait_for_selector` approach.
4. **Same architectural pattern**: Browser tools follow the existing two-layer design (schema.py for framework-agnostic definitions, langchain_tools.py for LangChain adapter).
5. **Opt-in via `[browser]` extra**: All browser functionality requires `playwright>=1.40`, which is already the `[browser]` optional dependency.

---

### Architecture Overview

```
agent-capsolver/
├── src/capsolver_agent/
│   ├── __init__.py          # Export BrowserSession
│   ├── browser.py           # NEW: BrowserSession class
│   ├── schema.py            # EXTEND: browser tool schemas + dispatch
│   ├── langchain_tools.py   # EXTEND: browser LangChain tools
│   └── __main__.py          # No change
├── tests/
│   ├── test_tools.py        # EXTEND: browser tool tests
│   └── test_browser.py      # NEW: BrowserSession unit tests
├── docs/
│   └── agent-integration.md # UPDATE: add browser tool docs
├── README.md                # UPDATE: mention browser tools
└── pyproject.toml           # No change (browser extra already exists)
```

### New File: `browser.py` — BrowserSession

A `BrowserSession` class manages a persistent Playwright browser instance. It is owned by the `ToolExecutor` and shared across all tool calls.

```python
class BrowserSession:
    """Persistent Playwright browser session for agent-driven page interaction."""

    def __init__(self) -> None:
        self._playwright: AsyncPlaywright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    @property
    def is_active(self) -> bool: ...
    @property
    def page(self) -> Page: ...       # Raises RuntimeError if not active

    async def launch(self, *, url: str | None = None,
                     headless: bool = True,
                     viewport: dict | None = None,
                     user_agent: str | None = None,
                     proxy: str | None = None) -> None: ...

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> dict: ...
    async def navigate_back(self) -> dict: ...
    async def click(self, selector: str) -> dict: ...
    async def fill(self, selector: str, value: str) -> dict: ...
    async def type_text(self, selector: str, text: str, delay: float = 0) -> dict: ...
    async def select(self, selector: str, value: str) -> dict: ...
    async def hover(self, selector: str) -> dict: ...
    async def press_key(self, key: str, selector: str | None = None) -> dict: ...
    async def scroll(self, direction: str, amount: int = 300) -> dict: ...
    async def wait(self, *, time: float | None = None,
                   text: str | None = None, selector: str | None = None) -> dict: ...
    async def screenshot(self, *, full_page: bool = False,
                         selector: str | None = None) -> dict: ...  # Returns base64
    async def evaluate(self, script: str) -> dict: ...
    async def extract_text(self, selector: str | None = None) -> dict: ...
    async def get_state(self) -> dict: ...   # url + title + interactive elements summary
    async def close(self) -> None: ...
```

Key implementation details:

- `launch()`: Imports `playwright.async_api` lazily (raises `ImportError` if not installed). Launches Chromium with optional config. Creates a new page and optionally navigates to `url`.
- `page` property: Returns `self._page` or raises `RuntimeError("No active browser session. Call browser_launch first.")`.
- `screenshot()`: Returns base64-encoded PNG string in the result dict (`{"image": "<base64>"}`) — JSON-serializable, works with all frameworks.
- `get_state()`: Returns `{"url": ..., "title": ..., "interactive_elements": [...]}` where interactive elements is a list of `{tag, text, selector}` for links, buttons, inputs, etc.
- `extract_text()`: Returns all visible text, optionally scoped to a CSS selector.
- `scroll()`: Uses `window.scrollBy()` via `evaluate()`.
- `close()`: Closes browser, stops playwright. Idempotent — safe to call multiple times.
- All methods return `{"success": True, ...}` or raise on error (the executor catches exceptions).

### Modifications to `schema.py`

#### 1. BrowserSession on ToolExecutor

```python
class ToolExecutor:
    def __init__(self, capsolver: Capsolver) -> None:
        self._capsolver = capsolver
        self._browser_session: BrowserSession | None = None

    def _get_or_create_browser_session(self) -> BrowserSession:
        if self._browser_session is None:
            from capsolver_agent.browser import BrowserSession
            self._browser_session = BrowserSession()
        return self._browser_session

    async def close(self) -> None:
        """Close browser session if active. Called on cleanup."""
        if self._browser_session and self._browser_session.is_active:
            await self._browser_session.close()
```

#### 2. New `get_browser_tools()` Function

```python
def get_browser_tools() -> list[ToolDef]:
    """Return framework-agnostic definitions for browser interaction tools."""
    return [
        ToolDef(name="browser_launch", ...),
        ToolDef(name="browser_navigate", ...),
        ToolDef(name="browser_navigate_back", ...),
        ToolDef(name="browser_click", ...),
        ToolDef(name="browser_fill", ...),
        ToolDef(name="browser_type", ...),
        ToolDef(name="browser_select", ...),
        ToolDef(name="browser_hover", ...),
        ToolDef(name="browser_press_key", ...),
        ToolDef(name="browser_scroll", ...),
        ToolDef(name="browser_wait", ...),
        ToolDef(name="browser_screenshot", ...),
        ToolDef(name="browser_evaluate", ...),
        ToolDef(name="browser_extract_text", ...),
        ToolDef(name="browser_get_state", ...),
        ToolDef(name="browser_close", ...),
    ]
```

#### 3. `get_all_tools()` Updated

```python
def get_all_tools(*, include_browser: bool = True) -> list[ToolDef]:
    """Return all tool definitions (captcha + browser)."""
    tools = _get_captcha_tools()  # Existing 5 tools, extracted to helper
    if include_browser:
        tools.extend(get_browser_tools())
    return tools
```

`include_browser=True` by default so users get the full set. Set to `False` to get only captcha tools (e.g., for token-mode-only usage or environments without Playwright).

#### 4. Dispatch Table Extended

```python
async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    dispatch = {
        # Captcha tools (existing, unchanged)
        "solve_captcha": self._solve_captcha,
        "detect_captchas": self._detect_captchas,
        "solve_on_page": self._solve_on_page,
        "get_balance": self._get_balance,
        "get_supported_captchas": self._get_supported_captchas,
        # Browser tools (new)
        "browser_launch": self._browser_launch,
        "browser_navigate": self._browser_navigate,
        "browser_navigate_back": self._browser_navigate_back,
        "browser_click": self._browser_click,
        "browser_fill": self._browser_fill,
        "browser_type": self._browser_type,
        "browser_select": self._browser_select,
        "browser_hover": self._browser_hover,
        "browser_press_key": self._browser_press_key,
        "browser_scroll": self._browser_scroll,
        "browser_wait": self._browser_wait,
        "browser_screenshot": self._browser_screenshot,
        "browser_evaluate": self._browser_evaluate,
        "browser_extract_text": self._browser_extract_text,
        "browser_get_state": self._browser_get_state,
        "browser_close": self._browser_close,
    }
    # ... rest unchanged
```

Each `_browser_*` handler is a thin wrapper: get the session, call the corresponding method, return result.

```python
async def _browser_click(self, args: dict[str, Any]) -> dict[str, Any]:
    session = self._get_or_create_browser_session()
    return await session.click(args["selector"])
```

#### 5. Captcha Tools + Session Integration (Optional Enhancement)

The existing `detect_captchas` and `solve_on_page` can optionally reuse the persistent session:

```python
async def _detect_captchas(self, args: dict[str, Any]) -> dict[str, Any]:
    page_url = args.get("page_url", "")
    use_session = args.get("use_session", False)  # New optional param

    if use_session and self._browser_session and self._browser_session.is_active:
        # Use persistent session's current page
        if page_url:
            await self._browser_session.navigate(page_url)
        driver = from_playwright_page(self._browser_session.page)
        detected = await self._capsolver.detect(driver)
        return {"success": True, "url": self._browser_session.page.url, "detected_captchas": [...]}
    else:
        # Existing ephemeral behavior (unchanged)
        ...
```

This is **backward compatible**: `use_session` defaults to `False`, so existing code paths are untouched.

### Browser Tool Schemas (16 Tools)

| Tool | Required Params | Optional Params | Description |
|---|---|---|---|
| `browser_launch` | — | url, headless, viewport, user_agent, proxy | Start browser session |
| `browser_navigate` | url | wait_until | Navigate to URL |
| `browser_navigate_back` | — | — | Go back |
| `browser_click` | selector | — | Click element |
| `browser_fill` | selector, value | — | Clear + set input value |
| `browser_type` | selector, text | delay (ms) | Simulate typing |
| `browser_select` | selector, value | — | Select dropdown option |
| `browser_hover` | selector | — | Mouse hover |
| `browser_press_key` | key | selector | Keyboard key press |
| `browser_scroll` | direction | amount (px) | Scroll page |
| `browser_wait` | — | time, text, selector | Wait for condition |
| `browser_screenshot` | — | full_page, selector | Capture screenshot (base64) |
| `browser_evaluate` | script | — | Run JavaScript |
| `browser_extract_text` | — | selector | Extract visible text |
| `browser_get_state` | — | — | URL + title + interactive elements |
| `browser_close` | — | — | Close browser session |

### Modifications to `langchain_tools.py`

#### 1. Pydantic Input Models

```python
class BrowserLaunchInput(BaseModel):
    url: Optional[str] = Field(default=None, description="URL to navigate to after launch.")
    headless: Optional[bool] = Field(default=True, description="Run browser in headless mode.")

class BrowserNavigateInput(BaseModel):
    url: str = Field(description="URL to navigate to.")

class BrowserClickInput(BaseModel):
    selector: str = Field(description="CSS selector of the element to click.")

class BrowserFillInput(BaseModel):
    selector: str = Field(description="CSS selector of the input element.")
    value: str = Field(description="Value to fill into the input.")

class BrowserTypeInput(BaseModel):
    selector: str = Field(description="CSS selector of the input element.")
    text: str = Field(description="Text to type into the element.")
    delay: Optional[float] = Field(default=0, description="Delay between keystrokes (ms).")

class BrowserSelectInput(BaseModel):
    selector: str = Field(description="CSS selector of the select element.")
    value: str = Field(description="Option value to select.")

class BrowserHoverInput(BaseModel):
    selector: str = Field(description="CSS selector of the element to hover.")

class BrowserPressKeyInput(BaseModel):
    key: str = Field(description="Key to press (e.g., Enter, Escape, Tab).")
    selector: Optional[str] = Field(default=None, description="Optional element to focus before pressing.")

class BrowserScrollInput(BaseModel):
    direction: str = Field(description="Scroll direction: up or down.")
    amount: Optional[int] = Field(default=300, description="Pixels to scroll.")

class BrowserWaitInput(BaseModel):
    time: Optional[float] = Field(default=None, description="Seconds to wait.")
    text: Optional[str] = Field(default=None, description="Wait for this text to appear.")
    selector: Optional[str] = Field(default=None, description="Wait for this CSS selector.")

class BrowserScreenshotInput(BaseModel):
    full_page: Optional[bool] = Field(default=False, description="Capture full page.")
    selector: Optional[str] = Field(default=None, description="Capture specific element only.")

class BrowserEvaluateInput(BaseModel):
    script: str = Field(description="JavaScript code to execute.")

class BrowserExtractTextInput(BaseModel):
    selector: Optional[str] = Field(default=None, description="CSS selector scope.")
```

#### 2. LangChain Tool Classes

All browser tools extend `_BrowserToolBase`, which is a subclass of `_CapsolverToolBase`:

```python
class _BrowserToolBase(_CapsolverToolBase):
    """Base for browser interaction tools. Requires [browser] extra."""
    pass

class BrowserLaunchTool(_BrowserToolBase): ...
class BrowserNavigateTool(_BrowserToolBase): ...
class BrowserClickTool(_BrowserToolBase): ...
# ... 16 total
```

#### 3. Factory Functions

```python
def get_langchain_tools(
    api_key: str | None = None,
    *,
    include_browser: bool = True,
) -> list[Any]:
    """Create LangChain tools. Set include_browser=False for captcha-only."""
    ...

def get_browser_tools(api_key: str | None = None) -> list[Any]:
    """Create only browser LangChain tools."""
    ...
```

### Modifications to `__init__.py`

```python
from capsolver_agent.schema import ToolDef, get_all_tools, execute_tool, create_executor, get_browser_tools
from capsolver_agent.browser import BrowserSession

__all__ = [
    "ToolDef",
    "get_all_tools",
    "get_browser_tools",
    "execute_tool",
    "create_executor",
    "BrowserSession",
]
```

### Modifications to `pyproject.toml`

No changes needed — `playwright>=1.40` is already in the `[browser]` extra. No new dependencies.

### Test Strategy

#### `tests/test_browser.py` (New File)

Unit tests for `BrowserSession` with mocked Playwright:

- `test_launch_creates_session`: Mock `async_playwright`, verify browser + page created.
- `test_launch_with_url`: Verify navigation called.
- `test_page_property_raises_when_inactive`: No session → RuntimeError.
- `test_close_idempotent`: Calling close twice doesn't error.
- `test_navigate_returns_url`: Mock page.goto, verify result dict.
- `test_click_calls_page_click`: Mock page.click with selector.
- `test_fill_calls_page_fill`: Verify fill args.
- `test_screenshot_returns_base64`: Mock page.screenshot returning bytes.
- `test_evaluate_returns_result`: Mock page.evaluate.
- `test_extract_text_returns_text`: Mock page.evaluate for text extraction.
- `test_get_state_returns_url_and_title`: Mock page.url, page.title, page.query_selector_all.

#### `tests/test_tools.py` (Extended)

- `TestGetAllTools`: Update `test_returns_five_tools` → parameterized for 5 (captcha only) and 21 (all). Add `test_browser_tool_names`.
- `TestToolDefSerialization`: Extend parametrize range to cover browser tools.
- `TestToolExecutor`: Add tests for each browser tool handler (mock `BrowserSession`). Add test for `browser_close` cleanup. Add test for session not active error.
- `TestLangChainTools`: Add `test_get_langchain_tools_with_browser` (21 tools), `test_get_langchain_tools_captcha_only` (5 tools). Add browser tool arun tests.
- `TestInputSchemas`: Add validation tests for all new Pydantic input models.

### Documentation Updates

#### `docs/agent-integration.md`

Add a new section "Browser Interaction Tools" with:
- Tool list table (name, description, parameters)
- Typical workflow: launch → navigate → interact → detect/solve captcha → close
- Code example for each framework (OpenAI, LangChain, etc.)
- Note: browser tools require `[browser]` extra

#### `README.md`

- Add "Browser Interaction" to feature highlights
- Add `browser` to the install extras list
- Brief code snippet showing launch → navigate → solve → close workflow

### Implementation Order

1. **`browser.py`**: Create `BrowserSession` class with all 16 methods.
2. **`schema.py`**: Add browser tool schemas, `get_browser_tools()`, extend `ToolExecutor` dispatch + `_get_or_create_browser_session()`, update `get_all_tools()`.
3. **`langchain_tools.py`**: Add Pydantic input models, browser tool classes, update factory.
4. **`__init__.py`**: Export new symbols.
5. **`tests/test_browser.py`**: Write `BrowserSession` unit tests.
6. **`tests/test_tools.py`**: Extend existing tests for browser tools.
7. **`docs/agent-integration.md`**: Add browser tools section.
8. **`README.md`**: Update feature highlights.
9. **Run all tests**: Verify 100% pass rate, no regressions.

### Example Usage

#### OpenAI Function Calling

```python
from capsolver_agent.schema import get_all_tools, create_executor

executor = create_executor(api_key="sk-...")
tools = [t.to_openai_function() for t in get_all_tools()]

# Agent decides to:
await executor.execute("browser_launch", {"url": "https://example.com/login"})
await executor.execute("browser_fill", {"selector": "#email", "value": "user@example.com"})
await executor.execute("browser_fill", {"selector": "#password", "value": "secret"})
await executor.execute("browser_click", {"selector": "button[type=submit]"})
await executor.execute("solve_on_page", {"page_url": "", "use_session": True})
await executor.execute("browser_click", {"selector": ".dashboard-link"})
await executor.execute("browser_close", {})
```

#### LangChain Agent

```python
from capsolver_agent.langchain_tools import get_langchain_tools

tools = get_langchain_tools(api_key="sk-...", include_browser=True)  # 21 tools
agent = create_react_agent(llm, tools, ...)
result = await agent.ainvoke({"input": "Log in to example.com and solve any captchas"})
```

### Risk and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| Playwright not installed | Browser tools fail | Lazy import + clear error message pointing to `[browser]` extra |
| Browser session leak | Resource waste | `browser_close` tool + `executor.close()` cleanup + context manager support |
| Screenshot base64 too large | Token limit issues | Document `full_page=False` default, optionally add `max_width` param |
| CSS selector fragility | Agent fails on complex pages | `browser_get_state` returns interactive elements with suggested selectors |
| Concurrent browser calls | Race conditions | Single page per session, sequential execution (agents are sequential by nature) |
