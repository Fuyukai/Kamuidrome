from __future__ import annotations

import json
import re
from pathlib import Path

import platformdirs


def get_prism_subdir(
    base_dir: Path,
    config_text: str,
    key: str,
    default_name: str,
) -> Path:
    """
    Gets the appropriate sub-directory from the Prism Launcher configuration.

    :param base_dir: The base Prism Launcher directory (e.g. ``~/.local/share/PrismLauncher``).
    :param config_text: The contents of the Prism config file.
    :param key: The key to extract from the config text.
    :param default_name: The default name to use if unset, e.g. ``instances``.
    """

    rxp = rf"{key}=(.*)$"
    matched = re.search(rxp, config_text, re.MULTILINE)
    dir_name = Path(default_name if matched is None else matched.group(1))
    if not dir_name.is_absolute():
        dir_name = base_dir / dir_name

    return dir_name


def get_prism_instances_directory() -> Path:
    """
    Gets the location of the Prism Launcher instances directory.
    """

    base_dir = Path(platformdirs.user_data_dir("PrismLauncher"))
    config_file = base_dir / "prismlauncher.cfg"
    return get_prism_subdir(
        base_dir, config_file.read_text(), key="InstanceDir", default_name="instances"
    )


def find_minecraft_dir(instances_dir: Path, instance: str):
    """
    Finds the ``.minecraft`` directory within a Prism Launcher instance directory.
    """

    instance_path = (instances_dir / instance).absolute()

    for path in (".minecraft", "minecraft"):
        if (what := instance_path / path).exists():
            return what

    raise FileNotFoundError(f"Can't find the ``.minecraft`` for {instance_path}")


def cleanup_from_index(instance_path: Path, index_path: Path) -> None:
    """
    Cleans up created symlinks from an index file.
    """

    with index_path.open() as f:
        index: list[str] = json.load(f)

    for fp in index:
        path = Path(fp)

        if not path.exists(follow_symlinks=False):
            # ok?
            continue

        if not path.is_symlink():
            # ok x2?
            continue

        path.unlink()
