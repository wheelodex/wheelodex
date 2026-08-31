#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import subprocess

log = logging.getLogger("wheelodex-runner")

SERVICES = [
    "wheelodex-process-orphan-wheels",
    "wheelodex-scan-changelog",
    "wheelodex-process-queue",
    "wheelodex-purge-old-versions",
]


@dataclass
class ServiceInfo:
    running: bool
    last_started: datetime | None


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        level=logging.INFO,
    )
    service_info = get_service_info()
    for service, info in service_info.items():
        if info.last_started is None:
            log.info("Service %s: never started", service)
        else:
            log.info(
                "Service %s: last started %s; currently %srunning",
                service,
                info.last_started,
                "" if info.running else "not ",
            )
    if (job := get_next_job(service_info)) is not None:
        subprocess.run(["sudo", "systemctl", "start", f"{job}.service"], check=True)


def get_service_info() -> dict[str, ServiceInfo]:
    service_info = {}
    r = subprocess.run(
        [
            "systemctl",
            "show",
            "--no-pager",
            "--property=Id,ActiveState,ExecMainStartTimestamp",
            "--timestamp=unix",
        ]
        + [f"{s}.service" for s in SERVICES],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    unseen = set(SERVICES)
    for para in r.stdout.split("\n\n"):
        # Note: systemd doesn't guarantee that the properties are output in the
        # same order as passed to --property, so using the --value option and
        # assigning variables based on line number won't work.
        sid = None
        running = False
        last_started = None
        for line in para.splitlines():
            key, _, value = line.partition("=")
            if key == "Id":
                sid = value.removesuffix(".service")
            if key == "ActiveState":
                running = value in {"active", "activating"}
            elif key == "ExecMainStartTimestamp":
                if value:
                    last_started = datetime.fromtimestamp(
                        int(value.removeprefix("@")), tz=UTC
                    )
                else:
                    last_started = None
            else:
                raise RuntimeError(
                    f"`systemctl show` output unexpected property {key!r}"
                )
        if sid is None:
            raise RuntimeError("`systemctl show` output stanza without Id")
        elif sid in unseen:
            service_info[sid] = ServiceInfo(running=running, last_started=last_started)
            unseen.discard(sid)
        else:
            raise RuntimeError(
                f"`systemctl show` output unexpected or duplicate service {sid!r}"
            )
    if unseen:
        raise RuntimeError(
            "`systemctl show` failed to emit all requested service entries:"
            f" {', '.join(unseen)} missing"
        )
    return service_info


def get_next_job(service_info: dict[str, ServiceInfo]) -> str | None:
    if any(info.running for info in service_info.values()):
        log.info("Not starting anything as a service is currently running")
        return None
    for service in SERVICES:
        if service_info[service].last_started is None:
            log.info(
                "Starting service %s as it is next to be started for the first time",
                service,
            )
            return service
    cutoff = datetime.now(tz=UTC) - timedelta(days=1)
    started = [
        (info.last_started, service)
        for service, info in service_info.items()
        if info.last_started is not None and info.last_started <= cutoff
    ]
    started.sort()
    if started:
        service = started[0][1]
        log.info(
            "Starting service %s as it hasn't been started in the longest time", service
        )
        return service
    log.info("Not starting anything as all services have started in the past 24 hours")
    return None


if __name__ == "__main__":
    main()
