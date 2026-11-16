import argparse
import json

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
    # file 1 -> full analysis: yes -> save next to the file: Enter (yes) -> another file: no
    assert run_interactive(args, answers("1", "y", "", "n")) == 0
    out = capsys.readouterr().out
    assert "Preliminary analysis: input/tickets.csv" in out
    assert "Rows in file:  4" in out
    assert "Rejected:      1  (empty ticket_id: 1)" in out
    assert "row 4: empty ticket_id" in out
    assert "Full analysis" in out and "Done." in out
    # saved next to the CSV, named after it; the database stays in output/
    summary = json.loads((project / "input" / "tickets_summary.json").read_text(encoding="utf-8"))
    assert summary["accepted"] == 2
    assert summary["rows_read"] == 4
    assert (project / "input" / "tickets_rejected.csv").exists()
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
    # full analysis: yes -> next to the file: n -> folder typed (dragged, with quotes) -> another file: no
    target = project / "results here"
    run_interactive(args, answers("1", "y", "n", f"'{target}' ", "n"))
    assert (target / "tickets_summary.json").exists()
    assert (target / "tickets_rejected.csv").exists()
    assert not (project / "input" / "tickets_summary.json").exists()


def test_enter_for_folder_uses_output(project, args):
    run_interactive(args, answers("1", "y", "n", "", "n"))
    assert (project / "output" / "tickets_summary.json").exists()


def test_not_writable_folder_asks_for_another(project, args, capsys):
    read_only = project / "read_only"
    read_only.mkdir()
    (read_only / "t.csv").write_text("ticket_id,message\nT1,Hello\n", encoding="utf-8")
    read_only.chmod(0o555)  # nobody may write here
    try:
        # path to the file -> full: yes -> (next to the file is impossible) -> Enter = output/ -> no
        run_interactive(args, answers(str(read_only / "t.csv"), "y", "", "n"))
    finally:
        read_only.chmod(0o755)
    out = capsys.readouterr().out
    assert "is not writable here" in out
    assert (project / "output" / "t_summary.json").exists()
