import re
from pathlib import Path


def main() -> int:
    lock = Path(__file__).resolve().parents[1] / "Cargo.lock"
    text = lock.read_text(encoding="utf-8", errors="replace")

    def ver(name: str) -> str | None:
        m = re.search(
            r"\[\[package\]\]\s*\nname = \"%s\"\s*\nversion = \"([^\"]+)\""
            % re.escape(name),
            text,
        )
        return m.group(1) if m else None

    names = [
        "tauri",
        "tauri-build",
        "tauri-plugin-dialog",
        "tauri-plugin-shell",
        "tauri-plugin-process",
        "tauri-plugin-updater",
    ]
    for n in names:
        print(f"{n}={ver(n)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

