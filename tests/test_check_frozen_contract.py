from __future__ import annotations

import subprocess

import tools.check_frozen_contract as frozen_contract


def test_compare_frozen_contract_formats_git_diff_output(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str, root=None):  # noqa: ANN001
        calls.append(args)
        return subprocess.CompletedProcess(
            args,
            0,
            "A\tcontracts/new.json\nR100\tcontracts/old.json\tsurepython/contracts/new.json\n",
            "",
        )

    monkeypatch.setattr(frozen_contract, "_git", fake_git)

    assert frozen_contract.compare_frozen_contract(root=tmp_path) == [
        "added: contracts/new.json",
        "renamed: contracts/old.json -> surepython/contracts/new.json",
    ]
    assert calls == [("diff", "--name-status", "--find-renames=100%", frozen_contract.FROZEN_REF, "--", *frozen_contract.FROZEN_PATHS)]


def test_main_reports_frozen_contract_change(monkeypatch, capsys) -> None:
    monkeypatch.setattr(frozen_contract, "compare_frozen_contract", lambda *args, **kwargs: ["modified: contracts/public.json"])

    assert frozen_contract.main(["--ref", "v0.17.0-public-preview"]) == 1
    captured = capsys.readouterr()
    assert "FROZEN_CONTRACT_CHANGED" in captured.err
    assert "modified: contracts/public.json" in captured.err


def test_main_succeeds_when_frozen_contract_matches(monkeypatch, capsys) -> None:
    monkeypatch.setattr(frozen_contract, "compare_frozen_contract", lambda *args, **kwargs: [])

    assert frozen_contract.main([]) == 0
    captured = capsys.readouterr()
    assert "Frozen contract matches" in captured.out
