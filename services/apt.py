"""Read-only Debian APT update checks"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)

APT_TIMEOUT_SECONDS = 180
LIST_TIMEOUT_SECONDS = 60
MAX_PACKAGE_NAMES = 30


@dataclass
class UpdateCheckResult:
    success: bool
    checked_at: str
    packages: list[str]
    total_count: int
    summary: str
    error: str | None = None


def _run_command(args: list[str], timeout: int) -> tuple[int, str, str]:
    """Run a fixed APT command without a shell; capture stdout and stderr."""
    import subprocess

    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=None,
    )
    return result.returncode, result.stdout, result.stderr


def _parse_upgradable(output: str) -> tuple[list[str], int]:
    """Parse apt list --upgradable output; avoid treating its header as a package."""
    names: list[str] = []
    count = 0
    for line in output.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("listing..."):
            continue
        # Typical line: package/stable-updates 1.2.3 amd64 [upgradable from: 1.2.2]
        match = re.match(r"^([^/\s]+)/\S+\s+\S+", line)
        if match:
            count += 1
            if len(names) < MAX_PACKAGE_NAMES:
                names.append(match.group(1))
    return names, count


def _check_updates_sync() -> UpdateCheckResult:
    checked_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    # Refreshing package indexes changes local metadata only; it does not upgrade packages.
    try:
        code, stdout, stderr = _run_command(
            ["sudo", "-n", "/usr/bin/apt-get", "update"],
            APT_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return UpdateCheckResult(
            False, checked_at, [], 0, "Could not refresh APT package lists.",
            f"{type(exc).__name__}: {exc}",
        )

    if code != 0:
        detail = (stderr or stdout).strip()[-1500:]
        return UpdateCheckResult(
            False, checked_at, [], 0, "APT package-list refresh failed.",
            f"Exit code: {code}\n{detail or 'No command output was returned.'}",
        )

    try:
        code, stdout, stderr = _run_command(
            ["/usr/bin/apt", "list", "--upgradable"],
            LIST_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return UpdateCheckResult(
            False, checked_at, [], 0, "Could not read the available-updates list.",
            f"{type(exc).__name__}: {exc}",
        )

    if code != 0:
        detail = (stderr or stdout).strip()[-1500:]
        return UpdateCheckResult(
            False, checked_at, [], 0, "Reading available updates failed.",
            f"Exit code: {code}\n{detail or 'No command output was returned.'}",
        )

    names, count = _parse_upgradable(stdout)
    summary = (
        f"{count} package(s) can be upgraded."
        if count
        else "Debian reports no available package upgrades."
    )
    return UpdateCheckResult(True, checked_at, names, count, summary)


async def check_updates() -> UpdateCheckResult:
    """Run the APT check off the Discord event loop."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_check_updates_sync),
            timeout=APT_TIMEOUT_SECONDS + LIST_TIMEOUT_SECONDS + 15,
        )
    except asyncio.TimeoutError:
        return UpdateCheckResult(
            False,
            datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            [], 0, "APT update check timed out.",
            "The check exceeded its allowed time. Inspect APT and network status on the server.",
        )


def format_update_result(result: UpdateCheckResult) -> str:
    lines = [
        f"**Debian update check** — {'completed' if result.success else 'failed'}",
        f"Checked: {result.checked_at}",
        result.summary,
    ]
    if result.packages:
        names = result.packages
        suffix = f"\n…and more ({result.total_count} total)" if result.total_count > len(names) else ""
        lines.append("Packages:\n" + ", ".join(f"`{name}`" for name in names) + suffix)
    if result.error:
        lines.append(f"Details:\n```text\n{result.error[:2500]}\n```")
    return "\n".join(lines)
