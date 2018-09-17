class WheelDatabase:
    def add_wheel_to_queue(self, filename, url, project, version, size, digests,
                                 uploaded, serial=None):
        ### If `filename` is already in the queue or the database, do nothing
        raise NotImplementedError

    def remove_wheel(self, filename, serial=None):
        # Remove the given wheel from the database and wheel queue
        raise NotImplementedError

    def remove_version(self, project, version, serial=None):
        # Delete all wheels for the given release from the database and wheel
        # queue
        raise NotImplementedError

    def remove_project(self, project, serial=None):
        # Delete all wheels for the given project from the database and wheel
        # queue
        raise NotImplementedError

    @property
    def serial(self):
        # Serial ID of the last seen PyPI event
        raise NotImplementedError
