"""Interactive mode: choose a file -> preliminary analysis -> confirm -> full analysis.

Started when the program is run without a CSV file (`python -m ticket_organizer`, `./start.sh`).
`ask` is the function that reads an answer (normally `input`); tests pass their own.
"""
import os
import sys
from pathlib import Path

from ticket_organizer.cli import (
    EXIT_ERROR,
    EXIT_OK,
    USER_ERRORS,
    error_message,
    import_hint,
    run_export,
    run_full,
)
from ticket_organizer.reader import quick_check
from ticket_organizer.summary import format_summary
from ticket_organizer.timing import format_timings, timed

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

def ask_yes_no(question, ask):
    """Every yes/no question looks the same: [y/n]. Capital letters work too (Y, N, Yes, NO).

    There is no hidden default: an empty answer (just Enter) asks again.
    """
    while True:
        answer = ask(f"{question} [y/n] ").strip().lower()
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

def preliminary_analysis(csv_path):
    """Quick first look: rows in the file and rejected rows only.

    Nothing is saved, categorized or compared with the database, and the file is read
    row by row — fast and light even for a very large file. Everything else is in the full analysis.
    """
    timings = {}
    with timed(timings, "preliminary analysis"):
        rows, reasons, first_rejected = quick_check(csv_path, examples=REJECTED_EXAMPLES)
    rejected = sum(reasons.values())
    reasons_text = ", ".join(f"{reason}: {count}" for reason, count in reasons.items())

    title(f"Preliminary analysis: {csv_path}")
    print(f"  Rows in file:  {rows}")
    print(f"  Rejected:      {rejected}" + (f"  ({reasons_text})" if reasons_text else ""))
    if first_rejected:
        print(f"  Rejected rows (first {REJECTED_EXAMPLES}):")
        for row_number, reason in first_rejected:
            print(f"    row {row_number}: {reason}")
    print(format_timings(timings))


def full_path(path):
    """Absolute path as the user sees it on their computer.

    In Docker the program runs in /app, so start.sh passes the real project folder in HOST_PROJECT_DIR.
    """
    host_dir = os.environ.get("HOST_PROJECT_DIR")
    if host_dir and not os.path.isabs(path):
        return os.path.join(host_dir, path)
    return os.path.abspath(path)


def _writable(folder):
    return Path(folder).is_dir() and os.access(folder, os.W_OK)


def suggested_output_folder(csv_path, project_output):
    """output/ next to the input file.

    Files from the project's own input/ or data/ folder -> the project's output/ (it is next to input/).
    Any other file -> an output/ folder in the same folder as the file.
    """
    parent = Path(csv_path).parent.resolve()
    if parent in (Path(d).resolve() for d in SEARCH_DIRS):
        return project_output
    return str(Path(csv_path).parent / "output")


def _can_create(folder):
    # The folder exists and is writable, or it can be created inside a writable folder.
    path = Path(folder)
    return _writable(path) if path.exists() else _writable(path.parent)


def choose_results_folder(csv_path, ask, project_output):
    """Ask where to save all results (database, summary, rejected rows)."""
    folder = suggested_output_folder(csv_path, project_output)
    if _can_create(folder):
        question = f"Save the results to {full_path(folder)}/? n = choose another folder"
        if ask_yes_no(question, ask):
            Path(folder).mkdir(parents=True, exist_ok=True)
            return folder
    else:
        warn(f"Cannot create {full_path(folder)}/ here (no write access).")

    while True:
        answer = clean_path(ask(f"Folder for the results (Enter = {project_output}/, drag and drop works): "))
        folder = answer or project_output
        try:
            Path(folder).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            warn(f"Cannot create {folder}/: {error}")
            continue
        if _writable(folder):
            return folder
        warn(f"Cannot write to {folder}/. Choose another folder.")


def full_analysis(csv_path, args, ask):
    folder = choose_results_folder(csv_path, ask, project_output=str(Path(args.db).parent))
    # The database lives in the same output folder. Summary and rejected rows are named after
    # the CSV file, so results of different files in one folder do not overwrite each other.
    name = Path(csv_path).stem
    db_path = str(Path(folder) / Path(args.db).name)
    summary_path = str(Path(folder) / f"{name}_summary.json")
    rejected_path = str(Path(folder) / f"{name}_rejected.csv")

    timings = {}
    summary = run_full(csv_path, db_path, summary_path, rejected_path, timings)
    title(f"Full analysis: {csv_path}")
    print(format_summary(summary))
    print()
    print(f"Saved to {full_path(folder)}/:")
    print(f"  database:      {Path(db_path).name}")
    print(f"  summary:       {Path(summary_path).name}")
    print(f"  rejected rows: {Path(rejected_path).name}")
    print(format_timings(timings))
    ok("Done.")
    offer_sql_export(folder, db_path, ask)


def offer_sql_export(folder, db_path, ask):
    """No database server is connected: say where the data is and offer a .sql file for one."""
    print()
    warn("Note: no PostgreSQL database server is connected.")
    print(f"  The results are stored in the SQLite file {full_path(db_path)}")
    print("  To put them into your PostgreSQL database, export them as a .sql file and import it there.")
    if not ask_yes_no("Export the database as a .sql file for PostgreSQL?", ask):
        return
    sql_path = str(Path(folder) / "tickets.sql")
    timings = {}
    with timed(timings, "export .sql"):
        rows = run_export(db_path, sql_path)
    ok(f"Exported {rows} rows to {sql_path}. Import it into PostgreSQL with:")
    print(import_hint(sql_path))
    print(format_timings(timings))


# --- main loop ----------------------------------------------------------------

def run_interactive(args, ask=input):
    print(_color("Customer Support Ticket Organizer", "1"))
    print("Put your own CSV files (columns: ticket_id, message) into the input/ folder,")
    print("or drag and drop a CSV file into this window when asked for a file.")
    try:
        while True:
            csv_path = choose_file(ask)
            try:
                preliminary_analysis(csv_path)
                if ask_yes_no("Run the full analysis and save the results?", ask):
                    full_analysis(csv_path, args, ask)
                else:
                    warn("Skipped, nothing was saved.")
            except USER_ERRORS as error:
                warn(f"Error: {error_message(error, csv_path)}")
                if isinstance(error, FileNotFoundError) and os.environ.get("IN_DOCKER"):
                    print(DOCKER_HINT)
            if not ask_yes_no("Check another file?", ask):
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
