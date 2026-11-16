import argparse
import sqlite3
import sys

from ticket_organizer.categorizer import categorize
from ticket_organizer.reader import read_csv, remove_duplicates, validation
from ticket_organizer.storage import count_per_category, db_creator, export_sql, save_messages
from ticket_organizer.timing import format_timings, timed
from ticket_organizer.summary import (
    build_summary,
    format_summary,
    save_rejected_csv,
    save_summary_json,
)

# Exit codes: 0 = success, 1 = the input file could not be processed.
# (argparse itself exits with 2 when the command line is wrong.)
EXIT_OK = 0
EXIT_ERROR = 1

# Problems caused by the input file or the environment, not by a bug in the code:
# shown as one line "Error: ...", without a traceback.
USER_ERRORS = (FileNotFoundError, ValueError, OSError, sqlite3.Error)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m ticket_organizer",
        description=(
            "Read customer messages from a CSV file (columns: ticket_id, message), "
            "reject rows with an empty id or message, skip duplicates, assign categories "
            "(Billing, Account, Technical, Other) and save them to an SQLite database. "
            "Prints a summary at the end. "
            "Without csv_file the program starts in interactive mode: choose a file, "
            "see a preliminary analysis, then confirm the full analysis."
        ),
        epilog=(
            "Examples: python -m ticket_organizer data/sample_tickets.csv   "
            "|   python -m ticket_organizer   (interactive)"
        ),
    )
    parser.add_argument(
        "csv_file", nargs="?",
        help="path to the input CSV file (leave out for interactive mode)",
    )
    parser.add_argument(
        "--db", default="output/tickets.db",
        help="SQLite database file, created if missing (default: %(default)s)",
    )
    parser.add_argument(
        "--summary", default="output/summary.json",
        help="where to save the summary as JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--rejected", default="output/rejected.csv",
        help="where to save rejected rows with row number and reason (default: %(default)s)",
    )
    parser.add_argument(
        "--export-sql", metavar="FILE",
        help="also export the whole database as a .sql file for PostgreSQL",
    )
    return parser


def process_file(csv_path, conn, timings=None):
    """read -> validate -> remove duplicates -> categorize -> save. Returns (summary, rejected).

    If `timings` is a dict, the time of each step is written into it.
    """
    with timed(timings, "read + validate"):
        rows = read_csv(csv_path)
        valid, rejected = validation(rows)
        unique, duplicates = remove_duplicates(valid)
    with timed(timings, "categorize"):
        for ticket in unique:
            ticket.categories = categorize(ticket.message)
    with timed(timings, "save to database"):
        saved, already_in_db = save_messages(conn, unique)
        summary = build_summary(
            len(rows), saved, rejected, duplicates, already_in_db, count_per_category(conn)
        )
    return summary, rejected


def run_full(csv_path, db_path, summary_path, rejected_path, timings=None):
    """Full analysis: process the file, save the DB, summary JSON and rejected rows. Returns the summary."""
    conn = db_creator(db_path)
    try:
        summary, rejected = process_file(csv_path, conn, timings)
    finally:
        conn.close()
    with timed(timings, "write files"):
        save_summary_json(summary, summary_path)
        save_rejected_csv(rejected, rejected_path)
    return summary


def run_export(db_path, sql_path):
    """Export the SQLite database to a .sql file. Returns the number of rows."""
    conn = db_creator(db_path)
    try:
        return export_sql(conn, sql_path)
    finally:
        conn.close()


def import_hint(sql_path):
    return f'  psql -d your_db -f "{sql_path}"'



def error_message(error, csv_path):
    # UnicodeDecodeError is a kind of ValueError, so it must be checked first.
    if isinstance(error, UnicodeDecodeError):
        return f"{csv_path} is not a UTF-8 text file."
    return str(error)


def saved_files_line(args):
    return f"Saved: database {args.db}, summary {args.summary}, rejected rows {args.rejected}"


def main(argv=None, ask=input):
    args = build_parser().parse_args(argv)
    if args.csv_file is None:
        # Imported here, not at the top: interactive.py itself imports from this module.
        from ticket_organizer.interactive import run_interactive
        return run_interactive(args, ask)

    timings = {}
    try:
        summary = run_full(args.csv_file, args.db, args.summary, args.rejected, timings)
        if args.export_sql:
            with timed(timings, "export .sql"):
                exported = run_export(args.db, args.export_sql)
        else:
            exported = None
    except USER_ERRORS as error:
        print(f"Error: {error_message(error, args.csv_file)}", file=sys.stderr)
        return EXIT_ERROR

    print(format_summary(summary))
    print()
    print(saved_files_line(args))
    if exported is not None:
        print(f"Exported {exported} rows to {args.export_sql}. Import it into PostgreSQL with:")
        print(import_hint(args.export_sql))
    print()
    print(format_timings(timings))
    return EXIT_OK
