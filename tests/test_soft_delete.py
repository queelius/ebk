"""Unit tests for soft-delete helpers."""
import tempfile
import shutil
from pathlib import Path

import pytest

from book_memex.library_db import Library
from book_memex.db.models import Marginalia
from book_memex.core.soft_delete import (
    filter_active, archive, restore, hard_delete, is_archived,
)


@pytest.fixture
def lib():
    temp_dir = Path(tempfile.mkdtemp())
    lib = Library.open(temp_dir)
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_filter_active_excludes_archived(lib):
    m1 = Marginalia(content="kept")
    m2 = Marginalia(content="archived")
    lib.session.add_all([m1, m2])
    lib.session.commit()
    archive(lib.session, m2)
    lib.session.commit()

    active = filter_active(lib.session.query(Marginalia), Marginalia).all()
    ids = {m.id for m in active}
    assert m1.id in ids
    assert m2.id not in ids


def test_archive_sets_timestamp(lib):
    m = Marginalia(content="x")
    lib.session.add(m); lib.session.commit()
    assert m.archived_at is None
    archive(lib.session, m)
    lib.session.commit()
    assert m.archived_at is not None
    assert is_archived(m)


def test_restore_clears_timestamp(lib):
    m = Marginalia(content="x")
    lib.session.add(m); lib.session.commit()
    archive(lib.session, m); lib.session.commit()
    restore(lib.session, m); lib.session.commit()
    assert m.archived_at is None
    assert not is_archived(m)


def test_hard_delete_removes_row(lib):
    m = Marginalia(content="x")
    lib.session.add(m); lib.session.commit()
    mid = m.id
    hard_delete(lib.session, m); lib.session.commit()
    assert lib.session.get(Marginalia, mid) is None


def test_filter_active_respects_include_archived(lib):
    m1 = Marginalia(content="a"); m2 = Marginalia(content="b")
    lib.session.add_all([m1, m2]); lib.session.commit()
    archive(lib.session, m2); lib.session.commit()

    all_rows = filter_active(
        lib.session.query(Marginalia), Marginalia, include_archived=True
    ).all()
    assert len(all_rows) == 2
