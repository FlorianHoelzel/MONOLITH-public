"""Export current Git-selected source without history or local runtime files."""

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PATH = re.compile(
    r"(^|/)(?:\.git|\.verification|\.venv[^/]*|node_modules|__pycache__|"
    r"backups|recovery|captures|screenshots)(/|$)|"
    r"(^|/)\.env(?:\..*)?$|desktop/dist/|"
    r"\.(?:db[^/]*|sqlite[^/]*|pem|key|crt|p12|pfx|log|bak|backup|dump|"
    r"zip|tar|gz|7z|pyc|state[^/]*)$|"
    r"(?:_session|_state|pairing).*\.json|apple_tv_pyatv\.conf|"
    r"(?:credentials|secrets).*\.json|token.*\.(?:txt|json)|window-state\.json",
    re.IGNORECASE,
)
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    rb"AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
)


def archive_source(output, name, data):
    # Fixed metadata avoids publishing local file modification times or owner IDs.
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.compress_type = ZIP_DEFLATED
    entry.create_system = 0
    entry.external_attr = 0o644 << 16
    output.writestr(entry, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination", type=Path,
        default=ROOT / ".verification" / "github-public-source",
    )
    destination = parser.parse_args().destination.resolve()
    # No overwrite: an existing export may contain changes worth preserving.
    archive = destination.with_suffix(".zip")
    if destination.exists() or archive.exists():
        parser.error("Destination or archive already exists; choose a new destination.")
    if destination == ROOT or ROOT.is_relative_to(destination):
        parser.error("Destination must not contain the source repository.")
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    ).decode("utf-8").split("\0")
    selected = []
    for name in sorted(set(filter(None, names))):
        path = ROOT / name
        if not path.exists():
            continue
        if name != ".env.example" and PRIVATE_PATH.search(name):
            parser.error(f"Private or generated file selected by Git: {name}")
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            parser.error(f"External path or symlink: {name}")
        if SECRET.search(path.read_bytes()):
            parser.error(f"Possible secret in {name}; value withheld.")
        selected.append((name, path))
    destination.mkdir(parents=True)
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        for name, path in selected:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            archive_source(output, name, target.read_bytes())
    print(f"Exported {len(selected)} files without Git history: {destination}")
    print(f"Source archive: {archive}")
    print("Review each new export before publication; pattern checks are not a guarantee.")


if __name__ == "__main__":
    main()
