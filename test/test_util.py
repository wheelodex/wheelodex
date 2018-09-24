import pytest
from   wheelodex.util import latest_version

@pytest.mark.parametrize('versions,latest', [
    ([], None),
    (['1.0', '1.1', '2.0', '1.3'], '2.0'),
    (['1.0', '2.0.dev1'], '1.0'),
    (['1.0.dev1', '1.1.dev1', '1.2.dev1'], '1.2.dev1'),
    (['2001.01.01', '1999.12.31'], '2001.01.01'),
])
def test_latest_version(versions, latest):
    assert latest_version(versions) == latest
