import nox

@nox.session(reuse_venv=True)
def test(session):
    session.install('-r', 'requirements.txt')
    session.install('-r', 'test-requirements.txt')
    # The `python -m` is needed here so that the current directory is added to
    # `sys.path`:
    session.run('python', '-m', 'pytest', *session.posargs, 'wheelodex', 'test')

@nox.session(reuse_venv=True)
def inspect(session):
    session.install('-r', 'requirements.txt')
    session.run('python', '-m', 'wheelodex.inspect', *session.posargs)
