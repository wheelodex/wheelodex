from   operator           import attrgetter
from   click.testing      import CliRunner
import pytest
from   wheelodex.__main__ import main
from   wheelodex.app      import create_app
from   wheelodex.models   import EntryPointGroup, db

@pytest.fixture(scope='session')
def tmpdb_inited():
    with create_app().app_context():
        db.create_all()
        # See <https://docs.sqlalchemy.org/en/latest/dialects/sqlite.html#foreign-key-support>:
        db.session.execute("PRAGMA foreign_keys=ON")
        yield

@pytest.fixture(autouse=True)
def tmpdb(tmpdb_inited):
    try:
        yield
    finally:
        db.session.rollback()

def test_load_entry_points():
    assert EntryPointGroup.query.all() == []
    db.session.add(EntryPointGroup(name='describe.me'))
    db.session.add(EntryPointGroup(
        name = 'wipe.me',
        summary = 'This will be cleared.',
        description = 'This will also be cleared.',
    ))
    db.session.add(EntryPointGroup(
        name = 'leave_me_alone',
        summary = 'Untouched',
        description = 'This will not be touched.',
    ))
    db.session.add(EntryPointGroup(
        name = 'partial.override',
        summary = 'This will be changed.',
        description = 'This will not be changed.',
    ))
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open('test.ini', 'w') as fp:
            print('''\
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
''', file=fp)
        # This should match the commit at the end of the command, allowing
        # everything done in this test to be rolled back by `tmpdb`:
        ### XXX: db.session.begin(subtransactions=True)
        r = runner.invoke(main, ['load-entry-points', 'test.ini'])
        assert r.exit_code == 0, r.output
    groups = sorted(EntryPointGroup.query.all(), key=attrgetter('name'))
    assert len(groups) == 6
    assert groups[0].name == 'DESCRIBE.ME'
    assert groups[0].summary == 'This is a new, different entry point group.'
    assert groups[0].description is None
    assert groups[1].name == 'describe.me'
    assert groups[1].summary == 'This is a summary.'
    assert groups[1].description == 'This is a description.\n' \
        '[This link is part of the description.](http://example.com)'
    assert groups[2].name == 'empty'
    assert groups[2].summary is None
    assert groups[2].description is None
    assert groups[3].name == 'leave_me_alone'
    assert groups[3].summary == 'Untouched'
    assert groups[3].description == 'This will not be touched.'
    assert groups[4].name == 'partial.override'
    assert groups[4].summary == 'New Summary'
    assert groups[4].description == 'This will not be changed.'
    assert groups[5].name == 'wipe.me'
    assert groups[5].summary == ''
    assert groups[5].description == ''
