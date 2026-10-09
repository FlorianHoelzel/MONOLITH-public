import os
import re


def read_homekit_pin(environ=None):
    configuration = os.environ if environ is None else environ
    pin = configuration.get("HOMEKIT_PIN", "").strip()
    if not re.fullmatch(r"[0-9]{3}-[0-9]{2}-[0-9]{3}", pin):
        raise ValueError("Configure HOMEKIT_PIN in private environment configuration (XXX-XX-XXX).")
    return pin.encode("ascii")
