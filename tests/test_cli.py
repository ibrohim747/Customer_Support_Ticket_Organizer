import csv
import json
import sqlite3
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


def test_no_arguments_starts_interactive_mode(tmp_path, capsys):
    # Without a keyboard (EOF on the first question) interactive mode stops with a clear message.
    def no_keyboard(prompt):
        raise EOFError

    assert main(out_args(tmp_path), ask=no_keyboard) == 1
    assert "Interactive mode needs a terminal" in capsys.readouterr().err


def test_unknown_option_is_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["data/sample_tickets.csv", "--colour"])
    assert exit_info.value.code == 2


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


def test_end_to_end_on_small_temp_csv(tmp_path):
    # One row per required case, written to a temp file and run through the whole program.
    csv_path = tmp_path / "in.csv"
    csv_path.write_text(
        "ticket_id,message\n"
        "T1,I was charged twice.\n"                     # row 2: normal -> Billing
        "T2,Do you offer student discounts?\n"          # row 3: unknown -> Other
        "T3,I was charged and can't log in.\n"          # row 4: multiple -> Account + Billing
        ",No id here\n"                                 # row 5: empty id -> rejected
        "T5,   \n"                                      # row 6: only spaces -> rejected
        "T1,I was charged twice.\n"                     # row 7: exact duplicate -> skipped
        "T1,Any news? The app crashed too.\n",          # row 8: follow-up -> Technical
        encoding="utf-8",
    )
    assert main([str(csv_path), *out_args(tmp_path)]) == 0

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["rows_read"] == 7
    assert summary["accepted"] == 4
    assert summary["rejected"] == 2
    assert summary["skipped"] == {"duplicate_in_file": 1, "already_in_db": 0, "total": 1}
    assert summary["categories_this_run"] == {"Account": 1, "Billing": 2, "Other": 1, "Technical": 1}

    conn = sqlite3.connect(tmp_path / "tickets.db")
    rows = conn.execute(
        "SELECT ticket_id, category FROM messages ORDER BY ticket_id, message, category"
    ).fetchall()
    conn.close()
    assert rows == [
        ("T1", "Technical"),  # "Any news? ..." sorts before "I was ..."
        ("T1", "Billing"),
        ("T2", "Other"),
        ("T3", "Account"),
        ("T3", "Billing"),
    ]

    with open(tmp_path / "rejected.csv", encoding="utf-8-sig", newline="") as file:
        rejected = list(csv.DictReader(file))
    assert [(r["row"], r["reason"]) for r in rejected] == [
        ("5", "empty ticket_id"),
        ("6", "empty message"),
    ]


def test_export_sql_option(tmp_path, capsys):
    sql = tmp_path / "export" / "tickets.sql"
    assert main([SAMPLE, *out_args(tmp_path), "--export-sql", str(sql)]) == 0
    assert "Exported 15 rows" in capsys.readouterr().out  # 14 messages, T0147 has 2 categories
    assert sql.read_text(encoding="utf-8").count("INSERT INTO messages") == 15


def test_time_of_each_step_is_shown_at_the_bottom(tmp_path, capsys):
    main([SAMPLE, *out_args(tmp_path), "--export-sql", str(tmp_path / "t.sql")])
    out = capsys.readouterr().out
    time_block = out[out.index("Time:"):]
    for step in ["read + validate", "categorize", "save to database", "write files", "export .sql", "total"]:
        assert step + ":" in time_block
    assert out.rstrip().splitlines()[-1].strip().startswith("total:")  # the very last line


def test_process_file_without_timings_still_works(tmp_path):
    from ticket_organizer.cli import process_file
    from ticket_organizer.storage import db_creator

    conn = db_creator(":memory:")
    summary, _ = process_file(SAMPLE, conn)  # timings not passed
    conn.close()
    assert summary.accepted == 14
