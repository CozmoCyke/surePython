from __future__ import annotations

import json

import pytest

import tools.check_distribution_install as distribution_install


def test_select_artifact_returns_single_match(tmp_path) -> None:
    wheel = tmp_path / "surepython-0.17.0-py3-none-any.whl"
    wheel.write_text("wheel", encoding="utf-8")

    assert distribution_install._select_artifact(tmp_path, "wheel") == wheel


def test_select_artifact_rejects_missing_or_multiple_matches(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="No wheel artifact"):
        distribution_install._select_artifact(tmp_path, "wheel")

    (tmp_path / "surepython-0.17.0-py3-none-any.whl").write_text("one", encoding="utf-8")
    (tmp_path / "surepython-0.17.1-py3-none-any.whl").write_text("two", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Expected exactly one wheel artifact"):
        distribution_install._select_artifact(tmp_path, "wheel")


def test_main_validates_selected_artifact(monkeypatch, tmp_path, capsys) -> None:
    artifact = tmp_path / "surepython-0.17.0.tar.gz"
    artifact.write_text("sdist", encoding="utf-8")
    calls: list[tuple[str, str | None]] = []

    def fake_validate_installed_artifact(selected_artifact, *, label=None):  # noqa: ANN001
        calls.append((selected_artifact.name, label))

    monkeypatch.setattr(distribution_install.check_release, "_validate_installed_artifact", fake_validate_installed_artifact)

    assert distribution_install.main(["--dist-dir", str(tmp_path), "--kind", "sdist", "--label", "rc1-sdist"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["artifact"] == artifact.name
    assert calls == [(artifact.name, "rc1-sdist")]


def test_main_reports_failure(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(
        distribution_install.check_release,
        "_validate_installed_artifact",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    artifact = tmp_path / "surepython-0.17.0-py3-none-any.whl"
    artifact.write_text("wheel", encoding="utf-8")

    assert distribution_install.main(["--dist-dir", str(tmp_path), "--kind", "wheel"]) == 1
    captured = capsys.readouterr()
    assert "DISTRIBUTION_INSTALL_FAILED" in captured.err
