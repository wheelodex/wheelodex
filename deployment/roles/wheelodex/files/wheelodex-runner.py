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
    service_info = {}
    for service in SERVICES:
        info = get_service_info(service)
        if info.last_started is None:
            log.info("Service %s: never started", service)
        else:
            log.info(
                "Service %s: last started %s; currently %srunning",
                service,
                info.last_started,
                "" if info.running else "not ",
            )
        service_info[service] = info
    if (job := get_next_job(service_info)) is not None:
        subprocess.run(["sudo", "systemctl", "start", f"{job}.service"], check=True)


def get_service_info(service: str) -> ServiceInfo:
    r = subprocess.run(
        [
            "systemctl",
            "show",
            "--no-pager",
            "--property=ActiveState,ExecMainStartTimestamp",
            "--timestamp=unix",
            f"{service}.service",
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    # Note: systemd doesn't guarantee that the properties are output in the
    # same order as passed to --property, so using the --value option and
    # assigning variables based on line number won't work.
    running = False
    last_started = None
    for line in r.stdout.splitlines():
        key, _, value = line.partition("=")
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
                f"`systemctl show {service}.service` output unexpected property {key!r}"
            )
    return ServiceInfo(running=running, last_started=last_started)


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
    now = datetime.now(tz=UTC)
    DAY = timedelta(days=1)
    started = [
        (info.last_started, service)
        for service, info in service_info.items()
        if info.last_started is not None and now - info.last_started > DAY
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
