from __future__ import annotations

import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXTENSIONS = ("jewelry_suite",)
EXCLUDED_PARTS = {"__pycache__", "tests"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def package(extension_name: str) -> Path:
    source = ROOT / extension_name
    manifest_path = source / "blender_manifest.toml"
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    output = DIST / f"{manifest['id']}-{manifest['version']}.zip"

    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if not path.is_file():
                continue
            if EXCLUDED_PARTS.intersection(relative.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES or path.name == ".DS_Store":
                continue
            archive.writestr(relative.as_posix(), path.read_bytes())

    return output


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    for extension_name in EXTENSIONS:
        output = package(extension_name)
        print(output.relative_to(ROOT))


if __name__ == "__main__":
    main()
