"""Tests for MCP server setup."""
import pytest

mcp_mod = pytest.importorskip("mcp")


class TestMCPServer:
    def test_server_creates_successfully(self, tmp_path):
        from ebk.library_db import Library
        from ebk.mcp.server import create_mcp_server
        lib = Library.open(tmp_path / "test-lib")
        try:
            mcp = create_mcp_server(lib)
            assert mcp is not None
            assert mcp.name == "ebk"
        finally:
            lib.close()

    def test_server_has_instructions(self, tmp_path):
        from ebk.library_db import Library
        from ebk.mcp.server import create_mcp_server
        lib = Library.open(tmp_path / "test-lib")
        try:
            mcp = create_mcp_server(lib)
            assert mcp.instructions is not None
            assert "get_schema" in mcp.instructions
        finally:
            lib.close()
