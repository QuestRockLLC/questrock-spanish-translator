from __future__ import annotations

from pathlib import Path

from backend.paths import glossary_path, macos_helper_path, resource_root


def test_dev_glossary_is_under_cwd(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mortgage_glossary.json").write_text("{}", encoding="utf-8")
    assert glossary_path() == tmp_path / "config" / "mortgage_glossary.json"
    assert resource_root() == tmp_path


def test_macos_helper_dev_path_points_at_native_tree() -> None:
    helper = macos_helper_path()
    assert helper.name == "AudioTap"
    assert helper.parent.name == "macos"
