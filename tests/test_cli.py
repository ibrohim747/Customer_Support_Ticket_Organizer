import json
import subprocess
import sys

import pytest

from ticket_organizer.cli import main

SAMPLE = "data/sample_tickets.csv"


def out_args(tmp_path):
    return [
        "--db", str(tmp_path / "tickets.db"),
        "--summary", str(tmp_path / "summary.json"),
        "--rejected", str(tmp_path / "rejected.csv"),
    ]


def test_success_returns_0_and_writes_files(tmp_path, capsys):
    assert main([SAMPLE, *out_args(tmp_path)]) == 0
    assert "Rows read:  19" in capsys.readouterr().out
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["accepted"] == 14
    assert (tmp_path / "rejected.csv").exists()
    assert (tmp_path / "tickets.db").exists()


def test_second_run_skips_all_messages(tmp_path):
    main([SAMPLE, *out_args(tmp_path)])
    main([SAMPLE, *out_args(tmp_path)])
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["accepted"] == 0
    assert summary["skipped"]["already_in_db"] == 14


def test_missing_file_gives_error_and_exit_1(tmp_path, capsys):
    assert main([str(tmp_path / "nope.csv"), *out_args(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "Error:" in err and "does not exist" in err
    assert "Traceback" not in err


def test_bad_header_gives_error_and_exit_1(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,text\n1,hello\n", encoding="utf-8")
    assert main([str(bad), *out_args(tmp_path)]) == 1
    assert "Missing column: ticket_id" in capsys.readouterr().err


def test_not_utf8_file_gives_error_and_exit_1(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"ticket_id,message\n1,caf\xe9\n")  # Latin-1, not UTF-8
    assert main([str(bad), *out_args(tmp_path)]) == 1
    assert "not a UTF-8" in capsys.readouterr().err


def test_no_arguments_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2
    assert "csv_file" in capsys.readouterr().err


def test_help_mentions_all_options(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    out = capsys.readouterr().out
    for word in ["csv_file", "--db", "--summary", "--rejected", "Example"]:
        assert word in out


def test_python_dash_m_works(tmp_path):
    # The real command a user types, run as a separate process.
    result = subprocess.run(
        [sys.executable, "-m", "ticket_organizer", SAMPLE, *out_args(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Accepted:   14" in result.stdout
