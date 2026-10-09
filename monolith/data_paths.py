import os
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = Path(
    os.getenv(
        "MONOLITH_DATA_DIR",
        str(SOURCE_DIR),
    )
).expanduser().resolve()


def data_path(filename):
    return DATA_DIR / filename
