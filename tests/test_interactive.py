import argparse
import json

import pytest

from ticket_organizer.interactive import (
    ask_yes_no,
    choose_file,
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
    ("", True), ("y", True), ("Yes", True), ("да", True), ("n", False), ("NO", False),
])
def test_ask_yes_no_default_yes(reply, expected):
    assert ask_yes_no("Go?", True, answers(reply)) is expected


def test_ask_yes_no_repeats_on_unclear_answer(capsys):
    assert ask_yes_no("Go?", False, answers("maybe", "y")) is True
    assert "answer y or n" in capsys.readouterr().out


def test_choose_file_enter_takes_first(project):
    assert choose_file(answers("")) == "input/tickets.csv"


def test_choose_file_wrong_number_asks_again(project, capsys):
    assert choose_file(answers("7", "1")) == "input/tickets.csv"
    assert "no file number 7" in capsys.readouterr().out


def test_choose_file_accepts_a_typed_path(project):
    assert choose_file(answers("somewhere/else.csv")) == "somewhere/else.csv"


def test_preliminary_then_full_analysis(project, args, capsys):
    # file 1 -> full analysis: yes -> another file: no
    assert run_interactive(args, answers("1", "y", "n")) == 0
    out = capsys.readouterr().out
    assert "Preliminary analysis: input/tickets.csv" in out
    assert "Will be saved:       2" in out
    assert "row 4: empty ticket_id" in out
    assert "Full analysis" in out and "Done." in out
    summary = json.loads((project / "output" / "summary.json").read_text(encoding="utf-8"))
    assert summary["accepted"] == 2
    assert summary["rows_read"] == 4


def test_answer_no_saves_nothing(project, args, capsys):
    assert run_interactive(args, answers("1", "n", "n")) == 0
    assert "nothing was saved" in capsys.readouterr().out
    assert not (project / "output" / "summary.json").exists()


def test_second_file_shows_already_in_database(project, args, capsys):
    # first pass saves the file, second pass on the same file: preliminary shows it is already there
    run_interactive(args, answers("1", "y", "y", "1", "n", "n"))
    out = capsys.readouterr().out
    assert "Already in database: 2" in out
    assert "Will be saved:       0" in out


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
