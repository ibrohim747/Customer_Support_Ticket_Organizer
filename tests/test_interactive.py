import argparse
import json
import os

import pytest

from ticket_organizer.interactive import (
    ask_yes_no,
    choose_file,
    clean_path,
    find_csv_files,
    run_interactive,
)


def answers(*replies):
    """A fake `input`: returns the given replies one by one."""
    replies = iter(replies)

    def ask(prompt):
        return next(replies)

    return ask


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A temp folder that looks like the project: input/ with one CSV, empty output/."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "input").mkdir()
    (tmp_path / "input" / "tickets.csv").write_text(
        "ticket_id,message\n"
        "T1,I was charged twice.\n"
        "T2,I cannot reset my password.\n"
        ",No id\n"
        "T1,I was charged twice.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def args():
    return argparse.Namespace(
        db="output/tickets.db", summary="output/summary.json", rejected="output/rejected.csv"
    )


def test_find_csv_files_lists_input_then_data(tmp_path):
    (tmp_path / "input").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "input" / "b.csv").write_text("x", encoding="utf-8")
    (tmp_path / "data" / "a.csv").write_text("x", encoding="utf-8")
    (tmp_path / "input" / "notes.txt").write_text("x", encoding="utf-8")
    dirs = (str(tmp_path / "input"), str(tmp_path / "data"))
    assert [p.split("/")[-1] for p in find_csv_files(dirs)] == ["b.csv", "a.csv"]


@pytest.mark.parametrize("reply, expected", [
    ("y", True), ("Y", True), ("yes", True), ("YES", True), ("да", True), ("Да", True),
    ("n", False), ("N", False), ("no", False), ("No", False), ("нет", False), (" n ", False),
])
def test_ask_yes_no_understands_small_and_capital_letters(reply, expected):
    assert ask_yes_no("Go?", answers(reply)) is expected


def test_ask_yes_no_repeats_on_unclear_or_empty_answer(capsys):
    # no hidden default: Enter alone and unknown words ask again
    assert ask_yes_no("Go?", answers("", "maybe", "N")) is False
    assert capsys.readouterr().out.count("answer y or n") == 2


def test_every_yes_no_question_uses_the_same_hint(project, args):
    prompts = []
    replies = iter(["1", "y", "y", "y", "n"])  # file, full, save, export, another

    def ask(prompt):
        prompts.append(prompt)
        return next(replies)

    run_interactive(args, ask)
    yes_no = prompts[1:]
    assert len(yes_no) == 4
    assert all(p.endswith("[y/n] ") for p in yes_no)
    assert not any("[Y/n]" in p or "[y/N]" in p for p in prompts)


def test_choose_file_enter_takes_first(project):
    assert choose_file(answers("")) == "input/tickets.csv"


def test_choose_file_wrong_number_asks_again(project, capsys):
    assert choose_file(answers("7", "1")) == "input/tickets.csv"
    assert "no file number 7" in capsys.readouterr().out


def test_choose_file_accepts_a_typed_path(project):
    assert choose_file(answers("somewhere/else.csv")) == "somewhere/else.csv"


def test_preliminary_then_full_analysis(project, args, capsys):
    # file 1 -> full: y -> save to output/: y -> export .sql: n -> another: n
    assert run_interactive(args, answers("1", "y", "y", "n", "n")) == 0
    out = capsys.readouterr().out
    assert "Preliminary analysis: input/tickets.csv" in out
    assert "Rows in file:  4" in out
    assert "Rejected:      1  (empty ticket_id: 1)" in out
    assert "row 4: empty ticket_id" in out
    assert "Full analysis" in out and "Done." in out
    # a file from the project's input/ -> the project's output/ (next to input/), named after the CSV
    summary = json.loads((project / "output" / "tickets_summary.json").read_text(encoding="utf-8"))
    assert summary["accepted"] == 2
    assert summary["rows_read"] == 4
    assert (project / "output" / "tickets_rejected.csv").exists()
    assert (project / "output" / "tickets.db").exists()


def test_answer_no_saves_nothing(project, args, capsys):
    assert run_interactive(args, answers("1", "n", "n")) == 0
    assert "nothing was saved" in capsys.readouterr().out
    assert not (project / "output" / "summary.json").exists()


def test_preliminary_shows_only_rows_and_rejected(project, args, capsys):
    run_interactive(args, answers("1", "n", "n"))
    out = capsys.readouterr().out
    preliminary = out[out.index("Preliminary analysis"):out.index("Skipped, nothing was saved")]
    assert "Rows in file" in preliminary and "Rejected" in preliminary
    for heavy in ("Categories", "Duplicates", "Already in database", "Will be saved"):
        assert heavy not in preliminary
    assert not (project / "output" / "tickets.db").exists()  # the database is not even opened


def test_bad_file_shows_error_and_continues(project, args, capsys):
    (project / "input" / "bad.csv").write_text("id,text\n1,x\n", encoding="utf-8")
    # files: 1) input/bad.csv 2) input/tickets.csv -> choose bad -> another? yes -> choose good -> no -> no
    assert run_interactive(args, answers("1", "y", "2", "n", "n")) == 0
    out = capsys.readouterr().out
    assert "Error: Missing column: ticket_id" in out
    assert "Preliminary analysis: input/tickets.csv" in out


def test_ctrl_c_stops(project, args, capsys):
    def ctrl_c(prompt):
        raise KeyboardInterrupt

    assert run_interactive(args, ctrl_c) == 1
    assert "Stopped." in capsys.readouterr().out


@pytest.mark.parametrize("typed, expected", [
    ("input/t.csv", "input/t.csv"),
    ("  input/t.csv  ", "input/t.csv"),
    ("'/home/me/My Files/t.csv' ", "/home/me/My Files/t.csv"),  # dragged into the terminal
    ('"C:\\Users\\me\\t.csv"', "C:\\Users\\me\\t.csv"),
    ("'only-one-quote.csv", "'only-one-quote.csv"),
])
def test_clean_path_removes_spaces_and_quotes(typed, expected):
    assert clean_path(typed) == expected


def test_dragged_path_with_quotes_is_read(project, args, capsys):
    path = str(project / "input" / "tickets.csv")
    assert run_interactive(args, answers(f"'{path}' ", "n", "n")) == 0
    assert "Rows in file:  4" in capsys.readouterr().out


def test_missing_file_in_docker_shows_hint(project, args, capsys, monkeypatch):
    monkeypatch.setenv("IN_DOCKER", "1")
    run_interactive(args, answers("/home/me/elsewhere.csv", "n"))
    out = capsys.readouterr().out
    assert "does not exist" in out
    assert "only files in your home folder and the project's input/ folder" in out


def test_missing_file_without_docker_has_no_hint(project, args, capsys, monkeypatch):
    monkeypatch.delenv("IN_DOCKER", raising=False)
    run_interactive(args, answers("/home/me/elsewhere.csv", "n"))
    assert "input/ folder are visible" not in capsys.readouterr().out


def test_start_text_mentions_drag_and_drop(project, args, capsys):
    prompts = []  # the questions the program asked (they go to `ask`, not to the output)
    replies = iter(["1", "n", "n"])

    def ask(prompt):
        prompts.append(prompt)
        return next(replies)

    run_interactive(args, ask)
    assert "drag and drop a CSV file into this window" in capsys.readouterr().out
    assert "drag and drop a file here" in prompts[0]


def test_save_to_another_folder(project, args, capsys):
    # full: yes -> next to the file: n -> folder typed (dragged, with quotes) -> export: no -> another: no
    target = project / "results here"
    run_interactive(args, answers("1", "y", "n", f"'{target}' ", "n", "n"))
    assert (target / "tickets_summary.json").exists()
    assert (target / "tickets_rejected.csv").exists()
    assert (target / "tickets.db").exists()  # the database goes with the other results
    assert not (project / "output" / "tickets_summary.json").exists()


def test_enter_for_folder_uses_output(project, args):
    run_interactive(args, answers("1", "y", "n", "", "n", "n"))
    assert (project / "output" / "tickets_summary.json").exists()


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root can write even into read-only folders (e.g. pytest inside Docker)",
)
def test_not_writable_folder_asks_for_another(project, args, capsys):
    read_only = project / "read_only"
    read_only.mkdir()
    (read_only / "t.csv").write_text("ticket_id,message\nT1,Hello\n", encoding="utf-8")
    read_only.chmod(0o555)  # nobody may write here
    try:
        # path -> full: yes -> (next to the file is impossible) -> Enter = output/ -> export: no -> another: no
        run_interactive(args, answers(str(read_only / "t.csv"), "y", "", "n", "n"))
    finally:
        read_only.chmod(0o755)
    out = capsys.readouterr().out
    assert "no write access" in out
    assert (project / "output" / "t_summary.json").exists()


def test_notice_about_database_and_no_export_by_default(project, args, capsys):
    run_interactive(args, answers("1", "y", "y", "n", "n"))
    out = capsys.readouterr().out
    assert "no PostgreSQL database server is connected" in out
    assert f"SQLite file {project / 'output' / 'tickets.db'}" in out  # full path, not just output/...
    assert not (project / "output" / "tickets.sql").exists()


def test_export_sql_on_yes(project, args, capsys):
    # full: y -> save to output/: y -> export: y -> another: n
    run_interactive(args, answers("1", "y", "y", "y", "n"))
    out = capsys.readouterr().out
    sql = project / "output" / "tickets.sql"
    assert sql.exists()
    assert "Exported 2 rows" in out
    assert "psql -d your_db -f" in out
    assert "mysql" not in out.lower() and "mariadb" not in out.lower()


def test_database_path_in_docker_is_shown_as_on_the_computer(project, args, capsys, monkeypatch):
    monkeypatch.setenv("HOST_PROJECT_DIR", "/home/me/project")
    run_interactive(args, answers("1", "y", "y", "n", "n"))
    assert "Saved to /home/me/project/output/:" in capsys.readouterr().out


def test_file_outside_project_gets_output_folder_next_to_it(project, args, capsys):
    elsewhere = project / "Downloads"
    elsewhere.mkdir()
    (elsewhere / "march.csv").write_text("ticket_id,message\nT1,I was charged\n", encoding="utf-8")
    # dragged path -> full: y -> save to Downloads/output/: y -> export: n -> another: n
    run_interactive(args, answers(f"'{elsewhere / 'march.csv'}' ", "y", "y", "n", "n"))
    out_dir = elsewhere / "output"
    assert sorted(p.name for p in out_dir.iterdir()) == [
        "march_rejected.csv", "march_summary.json", "tickets.db",
    ]
    assert not (project / "output").exists()  # nothing in the project's output/


def test_each_interactive_step_shows_its_time(project, args, capsys):
    run_interactive(args, answers("1", "y", "y", "y", "n"))  # file, full, save, export, another
    out = capsys.readouterr().out
    assert "preliminary analysis:" in out
    full = out[out.index("Full analysis"):out.index("Done.")]
    for step in ["read + validate:", "categorize:", "save to database:", "write files:", "total:"]:
        assert step in full
    assert "export .sql:" in out[out.index("Exported"):]
