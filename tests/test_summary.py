import csv
import json

import pytest

from ticket_organizer.categorizer import categorize
from ticket_organizer.reader import read_csv, remove_duplicates, validation
from ticket_organizer.storage import count_per_category, db_creator, save_messages
from ticket_organizer.summary import (
    build_summary,
    format_summary,
    save_rejected_csv,
    save_summary_json,
)

SAMPLE = "data/sample_tickets.csv"


def run_once(conn, csv_path=SAMPLE):
    """The same steps the program does: read -> validate -> dedupe -> categorize -> save."""
    rows = read_csv(csv_path)
    valid, rejected = validation(rows)
    unique, duplicates = remove_duplicates(valid)
    for record in unique:
        record["categories"] = categorize(record["message"])
    saved, already = save_messages(conn, unique)
    return build_summary(len(rows), saved, rejected, duplicates, already, count_per_category(conn))


@pytest.fixture
def conn():
    conn = db_creator(":memory:")
    yield conn
    conn.close()


def check_invariant(summary):
    assert summary["rows_read"] == (
        summary["accepted"] + summary["rejected"] + summary["skipped"]["total"]
    )


def test_sample_first_run_matches_expected_labels(conn):
    # Expected numbers from data/sample_tickets_labels.csv (task 02).
    summary = run_once(conn)
    check_invariant(summary)
    assert summary["rows_read"] == 19
    assert summary["accepted"] == 14
    assert summary["rejected"] == 4
    assert summary["skipped"] == {"duplicate_in_file": 1, "already_in_db": 0, "total": 1}
    assert summary["categories_this_run"] == {"Account": 4, "Billing": 4, "Other": 4, "Technical": 3}


def test_sample_second_run_skips_everything(conn):
    run_once(conn)
    summary = run_once(conn)
    check_invariant(summary)
    assert summary["accepted"] == 0
    assert summary["skipped"] == {"duplicate_in_file": 1, "already_in_db": 14, "total": 15}
    assert summary["categories_this_run"] == {}
    assert summary["categories_in_db"] == {"Account": 4, "Billing": 4, "Other": 4, "Technical": 3}


def test_counts_that_do_not_add_up_raise():
    with pytest.raises(ValueError):
        build_summary(5, accepted=[], rejected=[], duplicates=[], already_in_db=[], categories_in_db={})


def test_multi_category_message_counts_once_in_accepted():
    accepted = [{"row": 2, "ticket_id": "T1", "message": "m", "categories": ["Account", "Billing"]}]
    summary = build_summary(1, accepted, [], [], [], {})
    assert summary["accepted"] == 1
    assert summary["categories_this_run"] == {"Account": 1, "Billing": 1}


def test_format_summary_is_readable(conn):
    text = format_summary(run_once(conn))
    assert "Rows read:  19" in text
    assert "duplicate in file: 1" in text
    assert "Billing" in text


def test_save_summary_json(tmp_path, conn):
    summary = run_once(conn)
    path = tmp_path / "out" / "summary.json"
    save_summary_json(summary, path)
    assert json.loads(path.read_text(encoding="utf-8")) == summary


def test_save_rejected_csv(tmp_path):
    rejected = [
        {"row": 10, "ticket_id": "", "message": "no id", "reason": "empty ticket_id"},
        {"row": 12, "ticket_id": "E3", "message": "", "reason": "empty message"},
    ]
    path = tmp_path / "out" / "rejected.csv"
    save_rejected_csv(rejected, path)
    with open(path, encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows == [
        {"row": "10", "ticket_id": "", "message": "no id", "reason": "empty ticket_id"},
        {"row": "12", "ticket_id": "E3", "message": "", "reason": "empty message"},
    ]
