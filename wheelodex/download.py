from   collections   import namedtuple
from   xmlrpc.client import ServerProxy

#ENDPOINT = 'https://pypi.python.org/pypi'
ENDPOINT = 'https://pypi.org/pypi'

class AddWheel(namedtuple('AddWheel', 'project release filename serial')):
    def obsoletes(self, _):
        return False

class RemoveWheel(namedtuple('RemoveWheel', 'project release filename serial')):
    def obsoletes(self, act):
        return isinstance(act, AddWheel) and \
            self.project == act.project and \
            self.release == act.release and \
            self.filename == act.filename

class RemoveRelease(namedtuple('RemoveRelease', 'project release serial')):
    def obsoletes(self, act):
        return isinstance(act, (AddWheel, RemoveWheel)) and \
            self.project == act.project and \
            self.release == act.release

class RemoveProject(namedtuple('RemoveProject', 'project serial')):
    def obsoletes(self, act):
        return isinstance(act, (AddWheel, RemoveWheel, RemoveRelease)) and \
            self.project == act.project

def wheel_activity_since(since):
    activity = []
    pypi = ServerProxy(ENDPOINT, use_builtin_types=True)
    for proj, rel, _, action, serial in pypi.changelog_since_serial(since):
        actwords = action.split()
        # cf. calls to add_journal_entry in
        # <https://github.com/pypa/pypi-legacy/blob/master/store.py>
        if action == 'remove':
            # Package or version removed
            if rel is None:
                new_event = RemoveProject(proj, serial)
            else:
                new_event = RemoveRelease(proj, rel, serial)
        elif actwords[0] == 'add' and len(actwords) == 4 and \
                actwords[2] == 'file' and actwords[3].endswith('.whl'):
            new_event = AddWheel(proj, rel, actwords[3], serial)
        elif actwords[:2] == ['remove', 'file'] and len(actwords) == 3 and \
                actwords[2].endswith('.whl'):
            new_event = RemoveWheel(proj, rel, actwords[2], serial)
        else:
            continue
        activity = [act for act in activity if not new_event.obsoletes(act)] + \
            [new_event]
    return activity
