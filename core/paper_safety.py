from pathlib import Path


def assert_paper_path(path: Path, paper_root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = paper_root.resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        raise ValueError(f"Unsafe paper path outside PAPER_TEST_DIR: {path}")
