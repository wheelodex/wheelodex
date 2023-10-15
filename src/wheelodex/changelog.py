""" Parsing PyPI XML-RPC changelog events """

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ChangelogEvent:
    project: str
    version: str | None
    timestamp: int
    action: str
    serial: int

    @property
    def id(self) -> str:
        ts = datetime.fromtimestamp(self.timestamp, timezone.utc)
        return f"{self.serial} @ {ts}"

    @classmethod
    def parse(cls, event: list) -> ChangelogEvent:
        if len(event) != 5:
            raise ValueError(f"Expected 5 fields in changelog event; got {len(event)}")
        project, version, timestamp, action, serial = event
        assert isinstance(project, str)
        assert version is None or isinstance(version, str)
        assert isinstance(timestamp, int)
        assert isinstance(action, str)
        assert isinstance(serial, int)

        # As of pypa/warehouse revision c6d9dd32b (2023-10-15), the possible
        # "action" strings are (found by searching for "JournalEntry" in the
        # code):
        # - "add {python_version} file {filename}"
        # - "remove file {filename}"
        # - "create" [new project]
        # - "remove project"
        # - "new release"
        # - "remove release"
        # - "add Owner {username}"
        # - "add {role_name} {username}"
        # - "remove {role_name} {username}"
        # - "change {role_name} {username} to {role_name2}"
        # - "nuke user" [project field = "user:{username}"]
        # - "docdestroy"
        # - "yank release" (added in 69ce3dd on 2020-04-22)
        # - "unyank release" (added in 69ce3dd on 2020-04-22)
        # - "accepted {desired_role} {username}" (added in bd2b3a22f on 2020-09-11)
        # - "invite {role_name} {username}" (added in 709925e9d on 2023-03-20)
        # - "revoke_invite {role_name} {username}" (added in 709925e9d on 2023-03-20)

        match action.split():
            case ["add", pyver, "file", filename]:
                return FileCreated(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                    python_version=pyver,
                    filename=filename,
                )
            case ["remove", "file", filename]:
                return FileRemoved(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                    filename=filename,
                )
            case ["create"]:
                return ProjectCreated(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                )
            case ["remove", "project"]:
                return ProjectRemoved(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                )
            case ["new", "release"]:
                return VersionCreated(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                )
            case ["remove", "release"]:
                return VersionRemoved(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                )
            case _:
                return Other(
                    project=project,
                    version=version,
                    timestamp=timestamp,
                    action=action,
                    serial=serial,
                )


@dataclass
class FileCreated(ChangelogEvent):
    python_version: str
    filename: str

    def is_wheel(self) -> bool:
        return self.filename.lower().endswith(".whl")


@dataclass
class FileRemoved(ChangelogEvent):
    filename: str

    def is_wheel(self) -> bool:
        return self.filename.lower().endswith(".whl")


class ProjectCreated(ChangelogEvent):
    pass


class ProjectRemoved(ChangelogEvent):
    pass


class VersionCreated(ChangelogEvent):
    pass


class VersionRemoved(ChangelogEvent):
    pass


class Other(ChangelogEvent):
    pass
