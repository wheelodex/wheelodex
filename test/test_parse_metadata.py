import json
from   pathlib import Path
import pytest
from   wheelodex.inspect.metadata import parse_metadata

@pytest.mark.parametrize('mdfile', [
    p for p in (Path(__file__).with_name('data') / 'metadata').iterdir()
      if p.suffix == 'metadata'
])
def test_parse_metadata(mdfile):
    with open(str(mdfile.with_suffix('.json'))) as fp:
        expected = json.load(fp)
    with open(str(mdfile)) as fp:
        assert parse_metadata(fp) == expected
