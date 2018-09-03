from pypi_simple import PyPISimple

def get_all_wheels():
    pypi = PyPISimple()
    for project in pypi.get_projects():
        for pkg in pypi.get_project_files(project):
            if pkg.package_type == 'wheel':
                yield (pkg.filename, pkg.url)
                ### Include pkg.get_digests()?
