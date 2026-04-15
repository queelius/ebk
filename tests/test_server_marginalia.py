"""Integration tests for /api/marginalia endpoints."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library  # set_library is an override for tests


@pytest.fixture
def client_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("hello")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_marginalia_empty_body_returns_400(client_and_book):
    """Empty body violates 'at least content or highlighted_text' and must 400, not 500."""
    client, _, _ = client_and_book
    r = client.post("/api/marginalia", json={})
    assert r.status_code == 400
    assert "content" in r.json()["detail"].lower() or "highlighted_text" in r.json()["detail"].lower()


def test_create_marginalia(client_and_book):
    client, book, _ = client_and_book
    r = client.post("/api/marginalia", json={
        "book_ids": [book.id],
        "content": "note",
        "highlighted_text": "passage",
        "color": "#ffff00",
        "page_number": 3,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["uri"].startswith("book-memex://marginalia/")
    assert data["color"] == "#ffff00"
    assert data["uuid"]


def test_list_marginalia_for_book(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "a"})
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "b"})
    r = client.get(f"/api/marginalia?book_id={book.id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2


def test_get_marginalia_by_uuid(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    r = client.get(f"/api/marginalia/{created['uuid']}")
    assert r.status_code == 200
    assert r.json()["uuid"] == created["uuid"]


def test_patch_marginalia(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    r = client.patch(f"/api/marginalia/{created['uuid']}", json={"content": "y", "color": "#ff0000"})
    assert r.status_code == 200
    assert r.json()["content"] == "y"
    assert r.json()["color"] == "#ff0000"


def test_soft_delete_and_restore(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    uuid = created["uuid"]

    # Default delete is soft.
    r = client.delete(f"/api/marginalia/{uuid}")
    assert r.status_code == 204

    # Default list filters archived.
    items = client.get(f"/api/marginalia?book_id={book.id}").json()
    assert uuid not in {m["uuid"] for m in items}

    # include_archived exposes it.
    items = client.get(f"/api/marginalia?book_id={book.id}&include_archived=true").json()
    assert uuid in {m["uuid"] for m in items}

    # Restore clears archived_at.
    r = client.post(f"/api/marginalia/{uuid}/restore")
    assert r.status_code == 200
    items = client.get(f"/api/marginalia?book_id={book.id}").json()
    assert uuid in {m["uuid"] for m in items}


def test_hard_delete(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/marginalia", json={"book_ids": [book.id], "content": "x"}).json()
    uuid = created["uuid"]

    r = client.delete(f"/api/marginalia/{uuid}?hard=true")
    assert r.status_code == 204

    r = client.get(f"/api/marginalia/{uuid}")
    assert r.status_code == 404


def test_scope_filter(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "bn"})
    client.post("/api/marginalia", json={"book_ids": [book.id], "content": "h", "page_number": 5})
    items = client.get(f"/api/marginalia?book_id={book.id}&scope=highlight").json()
    assert all(m["scope"] == "highlight" for m in items)
    assert len(items) == 1
