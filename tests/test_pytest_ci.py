from __future__ import annotations

from pathlib import Path

from tools.pytest_ci import _first_failure_summary


def test_first_failure_summary_extracts_class_name_and_message(tmp_path: Path) -> None:
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="1">
    <testcase classname="tests.test_sample" name="test_example">
      <failure message="AssertionError: boom">stack trace</failure>
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    assert _first_failure_summary(junit) == "tests.test_sample :: test_example :: AssertionError: boom"


def test_first_failure_summary_returns_none_for_missing_or_invalid_file(tmp_path: Path) -> None:
    assert _first_failure_summary(tmp_path / "missing.xml") is None
    broken = tmp_path / "broken.xml"
    broken.write_text("<not xml", encoding="utf-8")
    assert _first_failure_summary(broken) is None
