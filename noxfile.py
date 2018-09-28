import nox

@nox.session(reuse_venv=True)
def run(session):
    session.install('-e', '.[postgres]')
    session.run('python', '-m', 'wheelodex', *session.posargs)

@nox.session(reuse_venv=True)
def inspect(session):
    session.install('-e', '.[postgres]')
    session.run('python', '-m', 'wheelodex.inspect', *session.posargs)
