from   datetime       import datetime, timezone
import pytest
from   wheelodex.util import VersionNoDot, glob2like, latest_version, \
                                parse_timestamp, wheel_sort_key

@pytest.mark.parametrize('versions,latest', [
    ([], None),
    (['1.0', '1.1', '2.0', '1.3'], '2.0'),
    (['1.0', '2.0.dev1'], '1.0'),
    (['1.0.dev1', '1.1.dev1', '1.2.dev1'], '1.2.dev1'),
    (['2001.01.01', '1999.12.31'], '2001.01.01'),
])
def test_latest_version(versions, latest):
    assert latest_version(versions) == latest

# In ascending order
WHEEL_PREFERENCES = [
    'foo-1.0-nonsense-nonsense-nonsense.whl',
    'foo-1.0-othernonsense-othernonsense-othernonsense.whl',

    'foo-1.0-cp25-none-any.whl',
    'foo-1.0-cp26-none-any.whl',
    'foo-1.0-cp27-none-any.whl',
    'foo-1.0-cp30-none-any.whl',
    'foo-1.0-cp31-none-any.whl',
    'foo-1.0-cp32-none-any.whl',
    'foo-1.0-cp33-none-any.whl',
    'foo-1.0-cp34-none-any.whl',

    'foo-1.0-cp35-cp35m-macosx_10_6_intel.whl',
    'foo-1.0-cp35-cp35m-macosx_10_7_intel.whl',
    'foo-1.0-cp35-cp35m-macosx_10_6_intel.macosx_10_7_intel.whl',
    'foo-1.0-cp35-cp35m-macosx_10_8_intel.whl',
    'foo-1.0-cp35-cp35m-macosx_10_7_intel.macosx_10_8_intel.whl',
    'foo-1.0-cp35-cp35m-macosx_10_6_intel.macosx_10_7_intel.macosx_10_8_intel.whl',
    'foo-1.0-cp35-cp35m-macosx_10_6_intel.macosx_10_7_intel.macosx_10_8_intel.macosx_10_9_intel.macosx_10_6_x86_64.macosx_10_7_x86_64.macosx_10_8_x86_64.macosx_10_9_x86_64.whl',

    'foo-1.0-cp35-none-win32.whl',
    'foo-1.0-cp35-none-win64.whl',
    'foo-1.0-cp35-none-win_amd64.whl',

    'foo-1.0-cp35-cp35m-manylinux1_i686.whl',
    'foo-1.0-cp35-cp35m-manylinux1_x86_64.whl',
    'foo-1.0-1-cp35-cp35m-manylinux1_x86_64.whl',
    'foo-1.0-1a-cp35-cp35m-manylinux1_x86_64.whl',
    'foo-1.0-2-cp35-cp35m-manylinux1_x86_64.whl',
    'foo-1.0-2a-cp35-cp35m-manylinux1_x86_64.whl',
    'foo-1.0-2b-cp35-cp35m-manylinux1_x86_64.whl',
    'foo-1.0-cp35-cp35m-manylinux1_i686.manylinux1_x86_64.whl',
    'foo-1.0-cp35-cp35m-manylinux2010_x86_64.whl',

    'foo-1.0-cp35-none-any.whl',
    'foo-1.0-cp36-none-any.whl',
    'foo-1.0-cp37-none-any.whl',
    'foo-1.0-cp38-none-any.whl',
    'foo-1.0-cp39-none-any.whl',

    'foo-1.0-py2-none-any.whl',
    'foo-1.0-py30-none-any.whl',
    'foo-1.0-py31-none-any.whl',
    'foo-1.0-py32-none-any.whl',
    'foo-1.0-py33-none-any.whl',
    'foo-1.0-py34-none-any.whl',
    'foo-1.0-py35-none-any.whl',
    'foo-1.0-py36-none-any.whl',
    'foo-1.0-py37-none-any.whl',
    'foo-1.0-py38-none-any.whl',
    'foo-1.0-py39-none-any.whl',
    'foo-1.0-py3_10_1-none-any.whl',
    'foo-1.0-py3_10-none-any.whl',
    'foo-1.0-py3_11-none-any.whl',
    'foo-1.0-py3_101-none-any.whl',
    'foo-1.0-py3-none-any.whl',
    'foo-1.0-py2.py3-none-any.whl',
    'foo-1.0-1-py2.py3-none-any.whl',
    'foo-1.0-1a-py2.py3-none-any.whl',
    'foo-1.0-2-py2.py3-none-any.whl',
    'foo-1.0-2a-py2.py3-none-any.whl',
    'foo-1.0-2b-py2.py3-none-any.whl',
]

@pytest.mark.parametrize(
    'lower,higher',
    zip(WHEEL_PREFERENCES, WHEEL_PREFERENCES[1:]),
)
def test_wheel_sort_key(lower, higher):
    assert wheel_sort_key(lower) < wheel_sort_key(higher)


VERSIONS_NO_DOTS = [
    '12',
    '1',
    '200',
    '2015',
    '201',
    '202',
    '20',
    '21',
    '22',
    '2',
    '30',
    '3101',
    '310',
    '311',
    '39',
    '3_10_1',
    '3_10',
    '3_11',
    '3_101',
    '3',
]

@pytest.mark.parametrize(
    'lower,higher',
    zip(VERSIONS_NO_DOTS, VERSIONS_NO_DOTS[1:]),
)
def test_version_no_dot(lower, higher):
    assert VersionNoDot(lower) < VersionNoDot(higher)

@pytest.mark.parametrize('glob,like', [
    ('python*', 'python%'),
    ('p?thon', 'p_thon'),
    (r'python\*', 'python*'),
    (r'p\?thon', 'p?thon'),
    ('__init__.*', r'\_\_init\_\_.%'),
    ('mod%ulo', r'mod\%ulo'),
    (r'foo\bar', r'foo\\bar'),
    (r'foo\%bar', r'foo\\\%bar'),
    (r'foo\_bar', r'foo\\\_bar'),
    (r'foo\\bar', r'foo\\bar'),
])
def test_glob2like(glob, like):
    assert glob2like(glob) == like

@pytest.mark.parametrize('s,dt', [
    (
        '2018-09-26T15:12:54',
        datetime(2018, 9, 26, 15, 12, 54, tzinfo=timezone.utc),
    ),
    (
        '2018-09-26T15:12:54.123456',
        datetime(2018, 9, 26, 15, 12, 54, 123456, tzinfo=timezone.utc),
    ),
    (
        '2018-09-26T15:12:54Z',
        datetime(2018, 9, 26, 15, 12, 54, tzinfo=timezone.utc),
    ),
    (
        '2018-09-26T15:12:54.123456Z',
        datetime(2018, 9, 26, 15, 12, 54, 123456, tzinfo=timezone.utc),
    ),
])
def test_parse_timestamp(s, dt):
    parsed = parse_timestamp(s)
    assert parsed == dt
    assert parsed.replace(tzinfo=None) == dt.replace(tzinfo=None)
    # pyRFC3339 uses its own UTC type, so this is false:
    #assert parsed.tzinfo == dt.tzinfo
