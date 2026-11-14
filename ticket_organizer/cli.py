import argparse
import sqlite3
import sys

from ticket_organizer.categorizer import categorize
from ticket_organizer.reader import read_csv, remove_duplicates, validation
from ticket_organizer.storage import count_per_category, db_creator, save_messages
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


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m ticket_organizer",
        description=(
            "Read customer messages from a CSV file (columns: ticket_id, message), "
            "reject rows with an empty id or message, skip duplicates, assign categories "
            "(Billing, Account, Technical, Other) and save them to an SQLite database. "
            "Prints a summary at the end."
        ),
        epilog="Example: python -m ticket_organizer data/sample_tickets.csv",
    )
    parser.add_argument("csv_file", help="path to the input CSV file")
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
    return parser


def process_file(csv_path, conn):
    """read -> validate -> remove duplicates -> categorize -> save. Returns (summary, rejected)."""
    rows = read_csv(csv_path)
    valid, rejected = validation(rows)
    unique, duplicates = remove_duplicates(valid)
    for record in unique:
        record["categories"] = categorize(record["message"])
    saved, already_in_db = save_messages(conn, unique)
    summary = build_summary(
        len(rows), saved, rejected, duplicates, already_in_db, count_per_category(conn)
    )
    return summary, rejected


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        conn = db_creator(args.db)
        try:
            summary, rejected = process_file(args.csv_file, conn)
        finally:
            conn.close()
        save_summary_json(summary, args.summary)
        save_rejected_csv(rejected, args.rejected)
    except UnicodeDecodeError:
        print(f"Error: {args.csv_file} is not a UTF-8 text file.", file=sys.stderr)
        return EXIT_ERROR
    except (FileNotFoundError, ValueError, OSError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return EXIT_ERROR

    print(format_summary(summary))
    print()
    print(f"Saved: database {args.db}, summary {args.summary}, rejected rows {args.rejected}")
    return EXIT_OK
