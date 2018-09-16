import json
from   pathlib           import Path
import pytest
from   wheelodex.inspect import inspect_wheel

@pytest.mark.parametrize('whlfile', [
    p for p in (Path(__file__).with_name('data') / 'wheels').iterdir()
      if p.suffix == '.whl'
])
def test_inspect_wheel(whlfile):
    with open(str(whlfile.with_suffix('.json'))) as fp:
        expected = json.load(fp)
    assert inspect_wheel(str(whlfile)) == expected
