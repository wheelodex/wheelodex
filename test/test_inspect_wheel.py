import json
from   operator          import attrgetter
from   pathlib           import Path
from   jsonschema        import validate
import pytest
from   wheelodex.inspect import SCHEMA, inspect_wheel

@pytest.mark.parametrize('whlfile', [
    p for p in (Path(__file__).with_name('data') / 'wheels').iterdir()
      if p.suffix == '.whl'
], ids=attrgetter("name"))
def test_inspect_wheel(whlfile):
    with open(str(whlfile.with_suffix('.json'))) as fp:
        expected = json.load(fp)
    inspection = inspect_wheel(str(whlfile))
    assert inspection == expected
    validate(inspection, SCHEMA)
