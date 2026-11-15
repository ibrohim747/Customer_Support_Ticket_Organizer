"""Interactive mode: choose a file -> preliminary analysis -> confirm -> full analysis.

Started when the program is run without a CSV file (`python -m ticket_organizer`, `./start.sh`).
`ask` is the function that reads an answer (normally `input`); tests pass their own.
"""
import os
import sys
from collections import Counter
from pathlib import Path

from ticket_organizer.categorizer import categorize
from ticket_organizer.cli import (
    EXIT_ERROR,
    EXIT_OK,
    USER_ERRORS,
    error_message,
    run_full,
    saved_files_line,
)
from ticket_organizer.reader import read_csv, remove_duplicates, validation
from ticket_organizer.storage import count_already_saved, db_creator
from ticket_organizer.summary import format_summary

# Folders searched for CSV files: the user's files first, then the sample.
SEARCH_DIRS = ("input", "data")
REJECTED_EXAMPLES = 5


# --- small output helpers -------------------------------------------------

def _color(text, code):
    # Colors only in a real terminal (not in tests, files or pipes); NO_COLOR turns them off.
    if sys.stdout.isatty() and "NO_COLOR" not in os.environ:
        return f"\033[{code}m{text}\033[0m"
    return text


def title(text):
    print()
    print(_color(f"=== {text} ===", "1;36"))  # bold cyan


def ok(text):
    print(_color(text, "32"))  # green


def warn(text):
    print(_color(text, "33"))  # yellow


# --- questions --------------------------------------------------------------

def ask_yes_no(question, default, ask):
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        answer = ask(f"{question} {hint} ").strip().lower()
        if answer == "":
            return default
        if answer in ("y", "yes", "д", "да"):
            return True
        if answer in ("n", "no", "н", "нет"):
            return False
        warn("Please answer y or n.")


def find_csv_files(dirs=SEARCH_DIRS):
    files = []
    for folder in dirs:
        files += sorted(str(path) for path in Path(folder).glob("*.csv"))
    return files


def choose_file(ask, dirs=SEARCH_DIRS):
    files = find_csv_files(dirs)
    title("Select a CSV file")
    if files:
        for number, path in enumerate(files, start=1):
            print(f"  {number}) {path}")
        prompt = "File number or path [1]: "
    else:
        warn("No CSV files found in: " + ", ".join(f"{d}/" for d in dirs))
        prompt = "Path to a CSV file: "

    while True:
        answer = ask(prompt).strip()
        if answer == "" and files:
            return files[0]
        if answer.isdigit():
            if 1 <= int(answer) <= len(files):
                return files[int(answer) - 1]
            warn(f"There is no file number {answer}.")
            continue
        if answer:
            return answer  # a path typed by the user


# --- the two analyses -------------------------------------------------------

def preliminary_analysis(csv_path, db_path):
    """Read, validate and categorize without saving anything; print what a full run would do."""
    rows = read_csv(csv_path)
    valid, rejected = validation(rows)
    unique, duplicates = remove_duplicates(valid)
    categories = Counter(c for record in unique for c in categorize(record["message"]))

    conn = db_creator(db_path)
    try:
        already = count_already_saved(conn, unique)
    finally:
        conn.close()

    reasons = Counter(record["reason"] for record in rejected)
    reasons_text = ", ".join(f"{reason}: {count}" for reason, count in reasons.items())

    title(f"Preliminary analysis: {csv_path}")
    print(f"  Rows in file:        {len(rows)}")
    print(f"  Will be saved:       {len(unique) - already}")
    print(f"  Rejected:            {len(rejected)}" + (f"  ({reasons_text})" if reasons_text else ""))
    print(f"  Duplicates in file:  {len(duplicates)}")
    print(f"  Already in database: {already}")
    if categories:
        print("  Categories:          " + ", ".join(f"{c} {n}" for c, n in sorted(categories.items())))
    if rejected:
        print(f"  Rejected rows (first {REJECTED_EXAMPLES}):")
        for record in rejected[:REJECTED_EXAMPLES]:
            print(f"    row {record['row']}: {record['reason']}")


def full_analysis(csv_path, args):
    summary = run_full(csv_path, args.db, args.summary, args.rejected)
    title(f"Full analysis: {csv_path}")
    print(format_summary(summary))
    print()
    print(saved_files_line(args))
    ok("Done.")


# --- main loop ----------------------------------------------------------------

def run_interactive(args, ask=input):
    print(_color("Customer Support Ticket Organizer", "1"))
    print("Put your own CSV files (columns: ticket_id, message) into the input/ folder.")
    try:
        while True:
            csv_path = choose_file(ask)
            try:
                preliminary_analysis(csv_path, args.db)
                if ask_yes_no("Run the full analysis and save the results?", True, ask):
                    full_analysis(csv_path, args)
                else:
                    warn("Skipped, nothing was saved.")
            except USER_ERRORS as error:
                warn(f"Error: {error_message(error, csv_path)}")
            if not ask_yes_no("Check another file?", False, ask):
                print("Bye!")
                return EXIT_OK
    except EOFError:
        # No keyboard input, e.g. `docker run` without -it, or input from a pipe.
        print(
            "\nInteractive mode needs a terminal. Run ./start.sh, "
            "or pass a file: python -m ticket_organizer data/sample_tickets.csv",
            file=sys.stderr,
        )
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("\nStopped.")
        return EXIT_ERROR
