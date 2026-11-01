import json
import os
import shutil
import subprocess
from config import DOCKER_CLI_TIMEOUT, DOCKER_HOST


class DockerCommandError(RuntimeError):
    pass


def _run(*args):
    docker = shutil.which("docker")
    if not docker:
        raise DockerCommandError("Docker CLI was not found in PATH.")
    if not DOCKER_HOST:
        raise DockerCommandError("DOCKER_HOST is unset; refusing default socket fallback.")
    env = os.environ.copy()
    env["DOCKER_HOST"] = DOCKER_HOST
    try:
        result = subprocess.run(
            [docker, *args], capture_output=True, text=True,
            timeout=DOCKER_CLI_TIMEOUT, check=False, env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise DockerCommandError(f"Docker command timed out after {DOCKER_CLI_TIMEOUT}s.") from exc
    except OSError as exc:
        raise DockerCommandError(f"Could not execute Docker CLI: {exc}") from exc
    if result.returncode:
        raise DockerCommandError((result.stderr.strip() or result.stdout.strip() or "Unknown Docker error")[:1000])
    return result.stdout.strip()


def _json_lines(output):
    return [json.loads(line) for line in output.splitlines() if line.strip()]

#docker contianer summary 
def get_docker_summary():
    d = json.loads(_run("info", "--format", "{{json .}}"))
    return {
        "version": d.get("ServerVersion", "Unknown"),
        "containers": d.get("Containers", 0),
        "running": d.get("ContainersRunning", 0),
        "paused": d.get("ContainersPaused", 0),
        "stopped": d.get("ContainersStopped", 0),
        "images": d.get("Images", 0),
        "os": d.get("OperatingSystem", "Unknown"),
        "driver": d.get("Driver", "Unknown"),
    }

#Display running container
def get_containers():
    out = _run("ps", "--all", "--no-trunc", "--format", "{{json .}}")
    return _json_lines(out) if out else []

#container status
def get_container_stats():
    out = _run("stats", "--no-stream", "--format", "{{json .}}")
    return _json_lines(out) if out else []

#Container Info 
def get_container_info(name_or_id):
    if not name_or_id or not name_or_id.strip():
        raise ValueError("Container name or ID is required.")
    data = json.loads(_run("inspect", name_or_id.strip()))
    if not data:
        raise DockerCommandError("No container information returned.")
    item = data[0]
    state = item.get("State") or {}
    config = item.get("Config") or {}
    ports = (item.get("NetworkSettings") or {}).get("Ports") or {}
    port_lines = []
    for container_port, bindings in ports.items():
        if bindings:
            for b in bindings:
                port_lines.append(f"{b.get('HostIp', '0.0.0.0')}:{b.get('HostPort')} -> {container_port}")
        else:
            port_lines.append(f"{container_port} (not published)")
    return {
        "name": (item.get("Name") or "").lstrip("/") or "Unknown",
        "id": item.get("Id", "")[:12],
        "image": config.get("Image", "Unknown"),
        "status": state.get("Status", "Unknown"),
        "started": state.get("StartedAt", "Unknown"),
        "restarts": item.get("RestartCount", 0),
        "ports": port_lines,
        "exit_code": state.get("ExitCode"),
        "error": state.get("Error") or "None",
    }
