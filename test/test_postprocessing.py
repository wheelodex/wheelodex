import pytest
from   wheelodex.inspect.util import extract_modules, split_keywords

@pytest.mark.parametrize('kwstr,expected', [
    (
        'pypi,warehouse,search,packages,pip',
        (['pypi', 'warehouse', 'search', 'packages', 'pip'], ','),
    ),
    (
        'pypi warehouse search packages pip',
        (['pypi', 'warehouse', 'search', 'packages', 'pip'], ' '),
    ),
    (
        "pypi,pep503,simple repository api,packages,pip",
        (["pypi", "pep503", "simple repository api", "packages", "pip"], ','),
    ),
])
def test_split_keywords(kwstr, expected):
    assert split_keywords(kwstr) == expected

@pytest.mark.parametrize('filelist,modules', [
    (
        [
            "qypi/__init__.py",
            "qypi/__main__.py",
            "qypi/api.py",
            "qypi/util.py",
            "qypi-0.4.1.dist-info/DESCRIPTION.rst",
            "qypi-0.4.1.dist-info/LICENSE.txt",
            "qypi-0.4.1.dist-info/METADATA",
            "qypi-0.4.1.dist-info/RECORD",
            "qypi-0.4.1.dist-info/WHEEL",
            "qypi-0.4.1.dist-info/entry_points.txt",
            "qypi-0.4.1.dist-info/metadata.json",
            "qypi-0.4.1.dist-info/top_level.txt",
        ],
        ["qypi", "qypi.__main__", "qypi.api", "qypi.util"],
    ),

    (
        [
            "flit/__init__.py",
            "flit/__main__.py",
            "flit/_get_dirs.py",
            "flit/build.py",
            "flit/common.py",
            "flit/inifile.py",
            "flit/init.py",
            "flit/install.py",
            "flit/installfrom.py",
            "flit/log.py",
            "flit/logo.py",
            "flit/sdist.py",
            "flit/upload.py",
            "flit/wheel.py",
            "flit/license_templates/apache",
            "flit/license_templates/gpl3",
            "flit/license_templates/mit",
            "flit/vcs/__init__.py",
            "flit/vcs/git.py",
            "flit/vcs/hg.py",
            "flit/vendorized/__init__.py",
            "flit/vendorized/readme/__init__.py",
            "flit/vendorized/readme/clean.py",
            "flit/vendorized/readme/rst.py",
            "flit-0.11.1.dist-info/entry_points.txt",
            "flit-0.11.1.dist-info/LICENSE",
            "flit-0.11.1.dist-info/WHEEL",
            "flit-0.11.1.dist-info/METADATA",
            "flit-0.11.1.dist-info/RECORD",
        ],
        [
            "flit",
            "flit.__main__",
            "flit._get_dirs",
            "flit.build",
            "flit.common",
            "flit.inifile",
            "flit.init",
            "flit.install",
            "flit.installfrom",
            "flit.log",
            "flit.logo",
            "flit.sdist",
            "flit.upload",
            "flit.vcs",
            "flit.vcs.git",
            "flit.vcs.hg",
            "flit.vendorized",
            "flit.vendorized.readme",
            "flit.vendorized.readme.clean",
            "flit.vendorized.readme.rst",
            "flit.wheel",
        ],
    ),
])
def test_extract_modules(filelist, modules):
    assert extract_modules(filelist) == modules

### TODO: Add more test cases for all functions!
