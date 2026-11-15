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
)
from ticket_organizer.reader import read_csv, remove_duplicates, validation
from ticket_organizer.storage import count_already_saved, db_creator
from ticket_organizer.summary import format_summary

# Folders searched for CSV files: the user's files first, then the sample.
SEARCH_DIRS = ("input", "data")
REJECTED_EXAMPLES = 5

# Inside Docker only the project's input/ folder and your home folder (mounted by start.sh)
# are visible, not the rest of the computer.
DOCKER_HINT = (
    "  Running in Docker: only files in your home folder and the project's input/ folder are visible here.\n"
    "  Copy the file into input/ (e.g. cp /path/to/file.csv input/), then choose it from the list."
)


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


def clean_path(text):
    """A path typed or dragged into the terminal: remove spaces and surrounding quotes.

    Dragging a file into the terminal gives '/home/me/My Files/t.csv' (with quotes and a trailing space).
    """
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1]
    return text


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
        prompt = "File number, or drag and drop a file here [1]: "
    else:
        warn("No CSV files found in: " + ", ".join(f"{d}/" for d in dirs))
        prompt = "Drag and drop a CSV file here (or type its path): "

    while True:
        answer = clean_path(ask(prompt))
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


def _writable(folder):
    return Path(folder).is_dir() and os.access(folder, os.W_OK)


def choose_results_folder(csv_path, ask, default_folder):
    """Ask where to save the summary and rejected rows: next to the CSV file or another folder."""
    folder = str(Path(csv_path).parent)
    if _writable(folder):
        question = f"Save the results next to the file ({folder}/)? n = choose another folder"
        if ask_yes_no(question, True, ask):
            return folder
    else:
        warn(f"Cannot save next to the file: {folder}/ is not writable here.")

    while True:
        answer = clean_path(ask(f"Folder for the results (Enter = {default_folder}/, drag and drop works): "))
        folder = answer or default_folder
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            warn(f"Cannot create {folder}/: {error}")
            continue
        if _writable(folder):
            return folder
        warn(f"Cannot write to {folder}/. Choose another folder.")


def full_analysis(csv_path, args, ask):
    folder = choose_results_folder(csv_path, ask, default_folder=str(Path(args.summary).parent))
    # Named after the CSV file, so results of different files do not overwrite each other.
    name = Path(csv_path).stem
    summary_path = str(Path(folder) / f"{name}_summary.json")
    rejected_path = str(Path(folder) / f"{name}_rejected.csv")

    summary = run_full(csv_path, args.db, summary_path, rejected_path)
    title(f"Full analysis: {csv_path}")
    print(format_summary(summary))
    print()
    print("Saved:")
    print(f"  summary:       {summary_path}")
    print(f"  rejected rows: {rejected_path}")
    print(f"  database:      {args.db}")
    ok("Done.")


# --- main loop ----------------------------------------------------------------

def run_interactive(args, ask=input):
    print(_color("Customer Support Ticket Organizer", "1"))
    print("Put your own CSV files (columns: ticket_id, message) into the input/ folder,")
    print("or drag and drop a CSV file into this window when asked for a file.")
    try:
        while True:
            csv_path = choose_file(ask)
            try:
                preliminary_analysis(csv_path, args.db)
                if ask_yes_no("Run the full analysis and save the results?", True, ask):
                    full_analysis(csv_path, args, ask)
                else:
                    warn("Skipped, nothing was saved.")
            except USER_ERRORS as error:
                warn(f"Error: {error_message(error, csv_path)}")
                if isinstance(error, FileNotFoundError) and os.environ.get("IN_DOCKER"):
                    print(DOCKER_HINT)
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
