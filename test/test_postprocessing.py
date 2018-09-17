import pytest
from   wheelodex.inspect.util import extract_dependencies, extract_modules, \
                                        split_keywords

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

@pytest.mark.parametrize('requires_dist,expected', [
    (
        ["click (~=6.5)", "packaging (>=16)", "requests (==2.*)"],
        ["click", "packaging", "requests"],
    ),

    (
        [
            "requests",
            "docutils",
            "requests_download",
            "zipfile36; python_version in \"3.3 3.4 3.5\""
        ],
        ["docutils", "requests", "requests_download", "zipfile36"],
    ),

    (
        [
            "setuptools",
            "Sphinx; extra == 'docs'",
            "repoze.sphinx.autointerface; extra == 'docs'",
            "zope.event; extra == 'test'",
            "coverage; extra == 'testing'",
            "nose; extra == 'testing'",
            "zope.event; extra == 'testing'",
        ],
        [
            "Sphinx",
            "coverage",
            "nose",
            "repoze.sphinx.autointerface",
            "setuptools",
            "zope.event",
        ]
    ),

    (
        [
            "certifi (>=2017.4.17)",
            "chardet (<3.1.0,>=3.0.2)",
            "idna (<2.6,>=2.5)",
            "urllib3 (>=1.21.1,<1.22)",
            "cryptography (>=1.3.4); extra == 'security'",
            "idna (>=2.0.0); extra == 'security'",
            "pyOpenSSL (>=0.14); extra == 'security'",
            "PySocks (!=1.5.7,>=1.5.6); extra == 'socks'",
            "win-inet-pton; sys_platform == \"win32\" and (python_version == \"2.7\" or python_version == \"2.6\") and extra == 'socks'",
        ],
        [
            "PySocks",
            "certifi",
            "chardet",
            "cryptography",
            "idna",
            "pyOpenSSL",
            "urllib3",
            "win-inet-pton",
        ],
    )
])
def test_extract_dependencies(requires_dist, expected):
    assert extract_dependencies(requires_dist) == expected

### TODO: Add more test cases for all functions!
