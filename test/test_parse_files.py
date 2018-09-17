from   io                import StringIO
import json
from   operator          import attrgetter
from   pathlib           import Path
import pytest
from   wheelodex.inspect import parse_entry_points, parse_metadata, \
                                    parse_record, parse_wheel_info

@pytest.mark.parametrize('mdfile', [
    p for p in (Path(__file__).with_name('data') / 'metadata').iterdir()
      if p.suffix == '.metadata'
], ids=attrgetter("name"))
def test_parse_metadata(mdfile):
    with open(str(mdfile.with_suffix('.json'))) as fp:
        expected = json.load(fp)
    with open(str(mdfile), encoding='utf-8') as fp:
        assert parse_metadata(fp) == expected

@pytest.mark.parametrize('epfile', [
    p for p in (Path(__file__).with_name('data') / 'entry_points').iterdir()
      if p.suffix == '.txt'
], ids=attrgetter("name"))
def test_parse_entry_points(epfile):
    with open(str(epfile.with_suffix('.json'))) as fp:
        expected = json.load(fp)
    with open(str(epfile), encoding='utf-8') as fp:
        assert parse_entry_points(fp) == expected

@pytest.mark.parametrize('wifile', [
    p for p in (Path(__file__).with_name('data') / 'wheel_info').iterdir()
      if p.suffix == '.wheel'
], ids=attrgetter("name"))
def test_parse_wheel_info(wifile):
    with open(str(wifile.with_suffix('.json'))) as fp:
        expected = json.load(fp)
    with open(str(wifile), encoding='utf-8') as fp:
        assert parse_wheel_info(fp) == expected

def test_parse_record():
    assert parse_record(StringIO('''\
qypi/__init__.py,sha256=zgE5-Sk8hED4NRmtnPUuvp1FDC4Z6VWCzJOOZwZ2oh8,532
qypi/__main__.py,sha256=GV5UVn3j5z4x-r7YYEB-quNPCucZYK1JOfWxmbdB0N0,7915
qypi/api.py,sha256=2c4EwxDhhHEloeOIeN0YgpIxCGpZaTDNJMYtHlVCcl8,3867
qypi/util.py,sha256=I2mRemqS5PHe5Iabk-CLrgFB2rznR87dVI3YwvpctSQ,3282
qypi-0.4.1.dist-info/DESCRIPTION.rst,sha256=SbT27FgdGvU8QlauLamstt7g4v7Cr2j6jc4RPr7bKNU,11633
qypi-0.4.1.dist-info/LICENSE.txt,sha256=SDaeT4Cm3ZeLgPOOL_f9BliMMHH_GVwqJa6czCztoS0,1090
qypi-0.4.1.dist-info/METADATA,sha256=msK-_0Fe8JHBjBv4HH35wbpUbIlCYv1Vy3X37tIdY5I,12633
qypi-0.4.1.dist-info/RECORD,,
qypi-0.4.1.dist-info/WHEEL,sha256=rNo05PbNqwnXiIHFsYm0m22u4Zm6YJtugFG2THx4w3g,92
qypi-0.4.1.dist-info/entry_points.txt,sha256=t4_O2VB3V-o52_PLoLLIb8m4SQDmY0HFdEJ9_Q2Odtw,45
qypi-0.4.1.dist-info/metadata.json,sha256=KI5TdfaYL-TPS1dMTABV6S8BFq9iAJRk3rkTXjOdgII,1297
qypi-0.4.1.dist-info/top_level.txt,sha256=J2Q5xVa8BtnOTGxjqY2lKQRB22Ydn9JF2PirqDEKE_Y,5
''')) == [
        {
            "path": "qypi/__init__.py",
            "digests": {
                "sha256": "zgE5-Sk8hED4NRmtnPUuvp1FDC4Z6VWCzJOOZwZ2oh8"
            },
            "size": 532
        },
        {
            "path": "qypi/__main__.py",
            "digests": {
                "sha256": "GV5UVn3j5z4x-r7YYEB-quNPCucZYK1JOfWxmbdB0N0"
            },
            "size": 7915
        },
        {
            "path": "qypi/api.py",
            "digests": {
                "sha256": "2c4EwxDhhHEloeOIeN0YgpIxCGpZaTDNJMYtHlVCcl8"
            },
            "size": 3867
        },
        {
            "path": "qypi/util.py",
            "digests": {
                "sha256": "I2mRemqS5PHe5Iabk-CLrgFB2rznR87dVI3YwvpctSQ"
            },
            "size": 3282
        },
        {
            "path": "qypi-0.4.1.dist-info/DESCRIPTION.rst",
            "digests": {
                "sha256": "SbT27FgdGvU8QlauLamstt7g4v7Cr2j6jc4RPr7bKNU"
            },
            "size": 11633
        },
        {
            "path": "qypi-0.4.1.dist-info/LICENSE.txt",
            "digests": {
                "sha256": "SDaeT4Cm3ZeLgPOOL_f9BliMMHH_GVwqJa6czCztoS0"
            },
            "size": 1090
        },
        {
            "path": "qypi-0.4.1.dist-info/METADATA",
            "digests": {
                "sha256": "msK-_0Fe8JHBjBv4HH35wbpUbIlCYv1Vy3X37tIdY5I"
            },
            "size": 12633
        },
        {
            "path": "qypi-0.4.1.dist-info/RECORD",
            "digests": {},
            "size": None
        },
        {
            "path": "qypi-0.4.1.dist-info/WHEEL",
            "digests": {
                "sha256": "rNo05PbNqwnXiIHFsYm0m22u4Zm6YJtugFG2THx4w3g"
            },
            "size": 92
        },
        {
            "path": "qypi-0.4.1.dist-info/entry_points.txt",
            "digests": {
                "sha256": "t4_O2VB3V-o52_PLoLLIb8m4SQDmY0HFdEJ9_Q2Odtw"
            },
            "size": 45
        },
        {
            "path": "qypi-0.4.1.dist-info/metadata.json",
            "digests": {
                "sha256": "KI5TdfaYL-TPS1dMTABV6S8BFq9iAJRk3rkTXjOdgII"
            },
            "size": 1297
        },
        {
            "path": "qypi-0.4.1.dist-info/top_level.txt",
            "digests": {
                "sha256": "J2Q5xVa8BtnOTGxjqY2lKQRB22Ydn9JF2PirqDEKE_Y"
            },
            "size": 5
        }
    ]
