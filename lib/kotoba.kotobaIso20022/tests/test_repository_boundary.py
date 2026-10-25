from pathlib import Path


def test_standalone_repository_has_no_go_runtime() -> None:
    root = Path(__file__).parents[1]
    forbidden_names = {"go.mod", "go.sum"}
    forbidden = [
        path.relative_to(root)
        for path in root.rglob("*")
        if ".git" not in path.parts
        and (path.name in forbidden_names or path.suffix == ".go" or "kotodama-go" in path.parts)
    ]
    assert forbidden == []


def test_migration_record_is_present() -> None:
    assert (Path(__file__).parents[1] / "MIGRATION.edn").is_file()
