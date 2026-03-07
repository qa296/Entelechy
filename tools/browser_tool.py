"""Browser tool - web automation interface for the agent."""

from browser.client import BrowserClient


# Global browser client (set during initialization)
_browser_client: BrowserClient | None = None


def set_browser_client(client: BrowserClient):
    """Set the global browser client instance."""
    global _browser_client
    _browser_client = client


def _get_client() -> BrowserClient:
    if _browser_client is None:
        raise RuntimeError("Browser client not initialized. Call set_browser_client() first.")
    return _browser_client


async def run_browser(action: str, **kwargs) -> str:
    """Execute a browser action.

    Args:
        action: One of "navigate", "click", "type", "screenshot", "extract".
        **kwargs: Action-specific parameters (url, selector, text).

    Returns:
        Action result string.
    """
    client = _get_client()
    return await client.execute_action(action, **kwargs)
