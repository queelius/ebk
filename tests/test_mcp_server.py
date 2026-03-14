"""Tests for MCP server setup."""
import pytest

mcp_mod = pytest.importorskip("mcp")

from ebk.library_db import Library
from ebk.mcp.server import create_mcp_server


@pytest.fixture
def mcp_server(tmp_path):
    """Create a library and MCP server for testing."""
    lib = Library.open(tmp_path / "test-lib")
    server = create_mcp_server(lib)
    yield server
    lib.close()


class TestMCPServer:
    def test_server_creates_successfully(self, mcp_server):
        assert mcp_server is not None
        assert mcp_server.name == "ebk"

    def test_server_has_instructions(self, mcp_server):
        assert mcp_server.instructions is not None
        assert "get_schema" in mcp_server.instructions
