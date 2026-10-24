
from pathlib import Path

HWMON_PATH = Path("/sys/class/hwmon")


def get_temperatures():
    """Read CPU temperatures from Linux hardware sensors."""
    readings = {}

    for hwmon in HWMON_PATH.glob("hwmon*"):
        try:
            name = (hwmon / "name").read_text().strip()
        except OSError:
            continue

        if name != "coretemp":
            continue

        for temp_file in hwmon.glob("temp*_input"):
            try:
                temperature = int(temp_file.read_text().strip()) / 1000
            except (OSError, ValueError):
                continue

            label_file = temp_file.with_name(
                temp_file.name.replace("_input", "_label")
            )

            try:
                label = label_file.read_text().strip()
            except OSError:
                label = temp_file.stem

            readings[label] = temperature

    return readings

