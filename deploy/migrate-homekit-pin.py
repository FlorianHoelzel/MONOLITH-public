"""Move the legacy source PIN to private environment configuration without displaying it."""

import argparse
import ast
import os
import re
from pathlib import Path


def migrate(source, environment, pin_file=None):
    configuration = environment.read_text(encoding="utf-8") if environment.exists() else ""
    configured = re.findall(r"^[ \t]*(?:export[ \t]+)?HOMEKIT_PIN[ \t]*=[ \t]*([^\r\n]*)", configuration, re.MULTILINE)
    if configured:
        value = configured[-1].split("#", 1)[0].strip().strip("\"'")
        if re.fullmatch(r"[0-9]{3}-[0-9]{2}-[0-9]{3}", value):
            return False
    if pin_file is not None:
        pin = pin_file.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[0-9]{3}-[0-9]{2}-[0-9]{3}", pin):
            raise RuntimeError("Recovery file does not contain a valid HomeKit PIN.")
        _append_pin(environment, configuration, pin)
        return True
    tree = ast.parse(source.read_text(encoding="utf-8-sig"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HOMEKIT_PIN"
            for target in node.targets
        ):
            try:
                pin = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if isinstance(pin, bytes):
                pin = pin.decode("ascii")
            if isinstance(pin, str) and re.fullmatch(r"[0-9]{3}-[0-9]{2}-[0-9]{3}", pin):
                _append_pin(environment, configuration, pin)
                return True
    raise RuntimeError("No legacy PIN found; configure HOMEKIT_PIN before deployment.")


def _append_pin(environment, configuration, pin):
    environment.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(environment, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(("\n" if configuration and not configuration.endswith("\n") else "")
                     + f"HOMEKIT_PIN={pin}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--source", type=Path)
    inputs.add_argument("--pin-file", type=Path)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    updated = migrate(args.source, args.env_file, args.pin_file)
    print("HomeKit PIN migrated." if updated else "HOMEKIT_PIN already configured; preserved.")
