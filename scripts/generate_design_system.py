"""Generate HAKİM design-system/MASTER.md and page overrides via UI/UX Pro Max."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "skills" / "ui-ux-pro-max" / "scripts" / "search.py"

MASTER_QUERY = (
    "legal AI research workspace enterprise professional trustworthy "
    "source-first content-dense graph visualization"
)

PAGES = {
    "research": (
        "legal research workspace source-cited answer knowledge graph "
        "retrieval trace inspector three-pane professional dense"
    ),
    "document": (
        "legal document analysis classification deadlines evidence "
        "confidence source-first dense professional workspace"
    ),
    "process": (
        "legal procedure timeline deadline calculator stages remedies "
        "deterministic professional trustworthy"
    ),
    "action": (
        "legal document generation petition draft review approval "
        "workflow professional trustworthy no decoration"
    ),
    "graph": (
        "legal knowledge graph visualization citation network "
        "sigma.js professional dense source-first"
    ),
    "source-explorer": (
        "source explorer legal text article version official gazette "
        "metadata inspector professional dense"
    ),
}


def run(query: str, *, page: str | None = None, force: bool = False) -> None:
    cmd = [
        sys.executable,
        str(SEARCH),
        query,
        "--design-system",
        "--persist",
        "--density",
        "8",
        "--variance",
        "4",
        "--motion",
        "3",
        "-p",
        "HAKIM",
        "--output-dir",
        str(ROOT),
        "-f",
        "markdown",
    ]
    if page:
        cmd.extend(["--page", page])
    if force:
        cmd.append("--force")
    print("\n$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(ROOT))


def flatten() -> None:
    nested = ROOT / "design-system" / "hakim"
    target = ROOT / "design-system"
    if not nested.exists():
        return
    master_src = nested / "MASTER.md"
    if master_src.exists():
        master_src.replace(target / "MASTER.md")
    pages_src = nested / "pages"
    pages_dst = target / "pages"
    pages_dst.mkdir(parents=True, exist_ok=True)
    if pages_src.exists():
        for page in pages_src.glob("*.md"):
            page.replace(pages_dst / page.name)
    leftover = list(nested.rglob("*"))
    for path in sorted(leftover, reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    if nested.exists():
        nested.rmdir()


def apply_overlays() -> None:
    overlay_root = ROOT / "design-system" / "overlays"
    master = ROOT / "design-system" / "MASTER.md"
    charter = overlay_root / "CHARTER.md"
    if master.exists() and charter.exists():
        text = master.read_text(encoding="utf-8")
        if "## HAKİM Product Charter" not in text:
            insertion = charter.read_text(encoding="utf-8").strip() + "\n\n"
            marker = "## Global Rules"
            if marker in text:
                text = text.replace(marker, insertion + marker, 1)
            else:
                text = insertion + text
            master.write_text(text, encoding="utf-8")
    pages_overlay = overlay_root / "pages"
    pages_dst = ROOT / "design-system" / "pages"
    pages_dst.mkdir(parents=True, exist_ok=True)
    if pages_overlay.exists():
        for page in pages_overlay.glob("*.md"):
            (pages_dst / page.name).write_text(page.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    run(MASTER_QUERY, force=True)
    for page, query in PAGES.items():
        run(query, page=page)
    flatten()
    apply_overlays()


if __name__ == "__main__":
    main()
