"""End-to-end Phase 1 integration test."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library
from book_memex.mcp.tools import (
    list_marginalia_impl, get_marginalia_impl,
    list_reading_sessions_impl, get_reading_progress_impl,
)
from book_memex.core.uri import parse_uri


@pytest.fixture
def e2e_env():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "book.txt"; p.write_text("hello world")
    book = lib.add_book(
        p, metadata={"title": "Test Book", "creators": ["Author"]},
        extract_text=False,
    )
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_marginalia_roundtrip_rest_and_mcp(e2e_env):
    client, book, lib = e2e_env

    # Create via REST
    r = client.post("/api/marginalia", json={
        "book_ids": [book.id],
        "content": "note",
        "highlighted_text": "world",
        "page_number": 1,
        "color": "#ffff00",
    })
    assert r.status_code == 201
    uuid = r.json()["uuid"]
    uri = r.json()["uri"]

    # URI parses correctly
    parsed = parse_uri(uri)
    assert parsed.kind == "marginalia"
    assert parsed.id == uuid

    # Fetchable via MCP
    via_mcp = get_marginalia_impl(lib.session, uuid=uuid)
    assert via_mcp["uri"] == uri
    assert via_mcp["scope"] == "highlight"

    # Soft-delete via REST
    r = client.delete(f"/api/marginalia/{uuid}")
    assert r.status_code == 204

    # Hidden from default MCP list
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid not in {m["uuid"] for m in rows}

    # Visible with include_archived
    rows = list_marginalia_impl(
        lib.session, book_id=book.id, include_archived=True
    )
    assert uuid in {m["uuid"] for m in rows}

    # Restore via REST
    r = client.post(f"/api/marginalia/{uuid}/restore")
    assert r.status_code == 200

    # Visible again
    rows = list_marginalia_impl(lib.session, book_id=book.id)
    assert uuid in {m["uuid"] for m in rows}

    # Hard-delete via REST
    r = client.delete(f"/api/marginalia/{uuid}?hard=true")
    assert r.status_code == 204

    # Gone from MCP
    import pytest as _pt
    with _pt.raises(LookupError):
        get_marginalia_impl(lib.session, uuid=uuid)


def test_reading_session_and_progress_roundtrip(e2e_env):
    client, book, lib = e2e_env

    # Start session via REST
    r = client.post("/api/reading/sessions/start", json={
        "book_id": book.id,
        "start_anchor": {"cfi": "epubcfi(/6/4!/4)"},
    })
    assert r.status_code == 201
    rs_uuid = r.json()["uuid"]

    # Post progress via REST
    r = client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "epubcfi(/6/4!/6)"},
        "percentage": 30,
    })
    assert r.status_code == 200

    # Fetchable via MCP
    sessions = list_reading_sessions_impl(lib.session, book_id=book.id)
    assert rs_uuid in {s["uuid"] for s in sessions}

    prog = get_reading_progress_impl(lib.session, book_id=book.id)
    assert prog["anchor"] == {"cfi": "epubcfi(/6/4!/6)"}
    assert prog["percentage"] == 30

    # End session via REST
    r = client.post(f"/api/reading/sessions/{rs_uuid}/end", json={
        "end_anchor": {"cfi": "epubcfi(/6/4!/8)"},
    })
    assert r.status_code == 200
    assert r.json()["end_time"] is not None

    # Session is now complete in MCP
    s = next(s for s in list_reading_sessions_impl(lib.session, book_id=book.id)
             if s["uuid"] == rs_uuid)
    assert s["end_time"] is not None
    assert s["end_anchor"] == {"cfi": "epubcfi(/6/4!/8)"}
