"""Regression tests for per-request session isolation (R3).

The FastAPI server keeps a single process-global ``Library`` and reaches into
``library.session`` from every request. Synchronous endpoints run in a worker
threadpool, so concurrent requests are served on different threads. A plain
``Session`` shared across threads is not safe (torn writes, cross-request data
bleed). ``Library.open`` now holds a thread-local ``scoped_session`` registry,
so each thread resolves to its own ``Session``.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path

import pytest

from book_memex.library_db import Library


@pytest.fixture
def lib():
    temp_dir = Path(tempfile.mkdtemp())
    library = Library.open(temp_dir)
    yield library
    library.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_session_is_per_thread(lib):
    """Two concurrent threads must resolve lib.session to distinct Sessions.

    A barrier keeps both threads alive at the same time, so they have distinct
    thread identities (no ident reuse), and we compare the live Session objects
    by identity (not id(), which can collide after GC) while both are still
    referenced.
    """
    barrier = threading.Barrier(2)
    resolved: dict[str, object] = {}

    def grab(name: str) -> None:
        barrier.wait()
        # lib.session is a scoped_session registry; calling it returns the
        # calling thread's own Session instance.
        resolved[name] = lib.session()

    threads = [threading.Thread(target=grab, args=(n,)) for n in ("t1", "t2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert resolved["t1"] is not resolved["t2"]


def test_same_thread_resolves_one_session(lib):
    """Within one thread, repeated access resolves to the same Session."""
    assert lib.session() is lib.session()


def test_query_still_works_through_proxy(lib):
    """The scoped_session proxy preserves the lib.session.* access pattern."""
    from book_memex.db.models import Book

    # No books yet; the point is that the proxy forwards .query/.commit/etc.
    assert lib.session.query(Book).count() == 0
