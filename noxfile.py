from   pathlib import Path
import nox

@nox.session(reuse_venv=True)
def run(session):
    session.install('-e', '.[postgres]')
    session.env["WHEELODEX_CONFIG"] = str(Path(__file__).with_name("config.py"))
    session.run('wheelodex', *session.posargs)

@nox.session(reuse_venv=True)
def inspect(session):
    session.install('-e', '.[postgres]')
    session.run('python', '-m', 'wheelodex.inspect', *session.posargs)
