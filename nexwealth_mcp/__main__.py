"""Entry point: `python -m nexwealth_mcp` starts the stdio MCP server."""
from nexwealth_mcp.server import mcp


if __name__ == "__main__":
    mcp.run(transport="stdio")
