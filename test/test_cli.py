from __future__ import annotations
from collections.abc import Iterator, Sequence
from operator import attrgetter
from traceback import format_exception
from typing import TypeVar
from click.testing import CliRunner, Result
import pytest
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from wheelodex.__main__ import main
from wheelodex.app import create_app
from wheelodex.models import EntryPointGroup, db

T = TypeVar("T", bound=DeclarativeBase)


@pytest.fixture(scope="session")
def tmpdb_inited() -> Iterator[None]:
    with create_app().app_context():
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        db.session.execute(text("PRAGMA foreign_keys=ON"))
        db.create_all()
        yield


@pytest.fixture(autouse=True)
def tmpdb(tmpdb_inited: None) -> Iterator[None]:  # noqa: U100
    try:
        yield
    finally:
        db.session.rollback()


def show_result(r: Result) -> str:
    if r.exception is not None:
        assert isinstance(r.exc_info, tuple)
        return "".join(format_exception(*r.exc_info))
    else:
        return r.output


def get_all(cls: type[T]) -> Sequence[T]:
    return db.session.scalars(db.select(cls)).all()


def test_load_entry_points() -> None:
    assert get_all(EntryPointGroup) == []
    db.session.add(EntryPointGroup(name="describe.me"))
    db.session.add(
        EntryPointGroup(
            name="wipe.me",
            summary="This will be cleared.",
            description="This will also be cleared.",
        )
    )
    db.session.add(
        EntryPointGroup(
            name="leave_me_alone",
            summary="Untouched",
            description="This will not be touched.",
        )
    )
    db.session.add(
        EntryPointGroup(
            name="partial.override",
            summary="This will be changed.",
            description="This will not be changed.",
        )
    )
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("test.ini", "w") as fp:
            print(
                """\
[describe.me]
summary = This is a summary.
description = This is a description.
    [This link is part of the description.](http://example.com)

[DESCRIBE.ME]
SUMMARY = This is a new, different entry point group.

[empty]

[wipe.me]
summary =
description =

[partial.override]
summary = New Summary
""",
                file=fp,
            )
        # This should match the commit at the end of the command, allowing
        # everything done in this test to be rolled back by `tmpdb`:
        ### XXX: db.session.begin(subtransactions=True)
        r = runner.invoke(
            main, ["load-entry-points", "test.ini"], standalone_mode=False
        )
        assert r.exit_code == 0, show_result(r)
    groups = sorted(get_all(EntryPointGroup), key=attrgetter("name"))
    assert len(groups) == 6
    assert groups[0].name == "DESCRIBE.ME"
    assert groups[0].summary == "This is a new, different entry point group."
    assert groups[0].description is None
    assert groups[1].name == "describe.me"
    assert groups[1].summary == "This is a summary."
    assert (
        groups[1].description == "This is a description.\n"
        "[This link is part of the description.](http://example.com)"
    )
    assert groups[2].name == "empty"
    assert groups[2].summary is None
    assert groups[2].description is None
    assert groups[3].name == "leave_me_alone"
    assert groups[3].summary == "Untouched"
    assert groups[3].description == "This will not be touched."
    assert groups[4].name == "partial.override"
    assert groups[4].summary == "New Summary"
    assert groups[4].description == "This will not be changed."
    assert groups[5].name == "wipe.me"
    assert groups[5].summary == ""
    assert groups[5].description == ""
