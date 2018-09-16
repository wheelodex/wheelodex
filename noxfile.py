import nox

@nox.session(reuse_venv=True)
def test(session):
    session.install('-r', 'requirements.txt')
    session.install('-r', 'test-requirements.txt')
    # The `python -m` is required here; see <https://docs.pytest.org/en/latest/usage.html#cmdline>
    session.run('python', '-m', 'pytest', *session.posargs, 'wheelodex', 'test')
