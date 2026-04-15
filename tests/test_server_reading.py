"""Integration tests for /api/reading/* endpoints."""
import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from book_memex.library_db import Library
from book_memex.server import app, set_library


@pytest.fixture
def client_and_book():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    p = lib.library_path / "b.txt"; p.write_text("h")
    book = lib.add_book(p, metadata={"title": "B", "creators": ["X"]}, extract_text=False)
    set_library(lib)
    with TestClient(app) as client:
        yield client, book, lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


# --- Reading sessions ---

def test_start_and_end_session(client_and_book):
    client, book, _ = client_and_book
    r = client.post("/api/reading/sessions/start", json={
        "book_id": book.id,
        "start_anchor": {"cfi": "epubcfi(/6/4!/4)"},
    })
    assert r.status_code == 201
    data = r.json()
    assert data["uri"].startswith("book-memex://reading/")
    uuid = data["uuid"]

    r = client.post(f"/api/reading/sessions/{uuid}/end", json={
        "end_anchor": {"cfi": "epubcfi(/6/4!/8)"},
    })
    assert r.status_code == 200
    assert r.json()["end_time"] is not None


def test_list_sessions(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/reading/sessions/start", json={"book_id": book.id})
    client.post("/api/reading/sessions/start", json={"book_id": book.id})
    r = client.get(f"/api/reading/sessions?book_id={book.id}")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_delete_and_restore_session(client_and_book):
    client, book, _ = client_and_book
    created = client.post("/api/reading/sessions/start", json={"book_id": book.id}).json()
    uuid = created["uuid"]

    r = client.delete(f"/api/reading/sessions/{uuid}")
    assert r.status_code == 204
    listed = client.get(f"/api/reading/sessions?book_id={book.id}").json()
    assert uuid not in {s["uuid"] for s in listed}

    client.post(f"/api/reading/sessions/{uuid}/restore")
    listed = client.get(f"/api/reading/sessions?book_id={book.id}").json()
    assert uuid in {s["uuid"] for s in listed}


# --- Reading progress ---

def test_progress_post_and_get(client_and_book):
    client, book, _ = client_and_book
    r = client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "epubcfi(/6/4!/4)"},
        "percentage": 10,
    })
    assert r.status_code == 200

    r = client.get(f"/api/reading/progress?book_id={book.id}")
    assert r.status_code == 200
    data = r.json()
    assert data["anchor"] == {"cfi": "epubcfi(/6/4!/4)"}
    assert data["percentage"] == 10


def test_progress_post_rejects_older_anchor(client_and_book):
    """POST must reject a backwards anchor (compared by percentage)."""
    client, book, _ = client_and_book
    client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "X"},
        "percentage": 50,
    })
    r = client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "Y"},
        "percentage": 20,
    })
    # Rejected with 409 Conflict or 400. Either is acceptable; spec says reject.
    assert r.status_code in (400, 409)

    # Current progress is still the forward one.
    r = client.get(f"/api/reading/progress?book_id={book.id}")
    assert r.json()["percentage"] == 50


def test_progress_patch_always_wins(client_and_book):
    client, book, _ = client_and_book
    client.post("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "X"},
        "percentage": 80,
    })
    r = client.patch("/api/reading/progress", json={
        "book_id": book.id,
        "anchor": {"cfi": "Y"},
        "percentage": 10,
    })
    assert r.status_code == 200
    r = client.get(f"/api/reading/progress?book_id={book.id}")
    assert r.json()["percentage"] == 10
