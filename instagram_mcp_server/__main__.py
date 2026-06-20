"""
Entry point for running the Instagram MCP server as a CLI command.
Usage: instagram-mcp
"""
import os
import sys


def main():
    # Ensure the package directory is in sys.path when called as CLI
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)

    from instagram_mcp_server.mcp_server import mcp
    mcp.run()


if __name__ == "__main__":
    main()
