import pytest

from ticket_organizer.models import RejectedRow, SkippedRow, Ticket
from ticket_organizer.reader import quick_check, read_csv, remove_duplicates, validation


def test_good_row_is_valid():
    valid, rejected = validation([{"ticket_id": "T1", "message": "Hello"}])
    assert valid == [Ticket(row=2, ticket_id="T1", message="Hello")]
    assert rejected == []


def test_values_are_stripped():
    valid, _ = validation([{"ticket_id": "  T1 ", "message": "  Hello  "}])
    assert valid[0].ticket_id == "T1"
    assert valid[0].message == "Hello"


def test_empty_ticket_id_is_rejected():
    valid, rejected = validation([{"ticket_id": "   ", "message": "Hello"}])
    assert valid == []
    assert rejected == [
        RejectedRow(row=2, ticket_id="", message="Hello", reason="empty ticket_id")
    ]


def test_empty_message_is_rejected():
    _, rejected = validation([{"ticket_id": "T1", "message": ""}])
    assert rejected[0].reason == "empty message"


def test_missing_value_none_is_rejected():
    # DictReader gives None when a row has fewer columns than the header.
    _, rejected = validation([{"ticket_id": "T1", "message": None}])
    assert rejected[0].reason == "empty message"


def test_row_numbers_start_at_2_and_count_every_row():
    rows = [
        {"ticket_id": "T1", "message": "ok"},
        {"ticket_id": "", "message": "no id"},
        {"ticket_id": "T3", "message": "ok"},
    ]
    valid, rejected = validation(rows)
    assert [r.row for r in valid] == [2, 4]
    assert rejected[0].row == 3


def test_both_empty_is_rejected_with_combined_reason():
    _, rejected = validation([{"ticket_id": " ", "message": ""}])
    assert rejected[0].reason == "empty ticket_id and message"

def test_exact_duplicate_is_skipped():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": "T1", "message": "Hello"},
    ])
    unique, skipped = remove_duplicates(valid)
    assert unique == [Ticket(row=2, ticket_id="T1", message="Hello")]
    assert skipped == [
        SkippedRow(row=3, ticket_id="T1", message="Hello", reason="duplicate of row 2")
    ]


def test_duplicate_after_strip_is_skipped():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": " T1 ", "message": "  Hello "},
    ])
    _, skipped = remove_duplicates(valid)
    assert [r.row for r in skipped] == [3]


def test_same_id_different_message_is_follow_up():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": "T1", "message": "Any update?"},
    ])
    unique, skipped = remove_duplicates(valid)
    assert [r.row for r in unique] == [2, 3]
    assert skipped == []


def test_same_message_different_id_is_kept():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "I can't log in"},
        {"ticket_id": "T2", "message": "I can't log in"},
    ])
    unique, skipped = remove_duplicates(valid)
    assert len(unique) == 2
    assert skipped == []


@pytest.mark.parametrize("message", ["", " ", "     ", "\t", None])
def test_empty_or_only_spaces_message_is_rejected(message):
    valid, rejected = validation([{"ticket_id": "T1", "message": message}])
    assert valid == []
    assert rejected[0].reason == "empty message"


# --- read_csv: whole-file checks ---

def write(tmp_path, text, name="t.csv", encoding="utf-8"):
    path = tmp_path / name
    path.write_text(text, encoding=encoding)
    return str(path)


def test_read_csv_returns_rows(tmp_path):
    path = write(tmp_path, "ticket_id,message\nT1,Hello\nT2,Hi\n")
    assert read_csv(path) == [
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": "T2", "message": "Hi"},
    ]


@pytest.mark.parametrize("header, missing", [
    ("id,message", "ticket_id"),
    ("ticket_id,text", "message"),
])
def test_read_csv_missing_column_raises(tmp_path, header, missing):
    path = write(tmp_path, f"{header}\nT1,Hello\n")
    with pytest.raises(ValueError, match=f"Missing column: {missing}"):
        read_csv(path)


def test_read_csv_extra_and_reordered_columns_are_ok(tmp_path):
    path = write(tmp_path, "message,priority,ticket_id\nHello,high,T1\n")
    assert read_csv(path)[0]["ticket_id"] == "T1"


def test_read_csv_handles_bom(tmp_path):
    # Excel saves "UTF-8 CSV" with a BOM; without utf-8-sig the header would be "﻿ticket_id".
    path = write(tmp_path, "ticket_id,message\nT1,Hello\n", encoding="utf-8-sig")
    assert read_csv(path)[0]["ticket_id"] == "T1"


def test_read_csv_header_only_gives_no_rows(tmp_path):
    assert read_csv(write(tmp_path, "ticket_id,message\n")) == []


def test_read_csv_empty_file_raises(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        read_csv(write(tmp_path, ""))


def test_read_csv_not_csv_extension_raises(tmp_path):
    with pytest.raises(ValueError, match=r"Not a \.csv file"):
        read_csv(write(tmp_path, "ticket_id,message\n", name="t.txt"))


def test_read_csv_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_csv(str(tmp_path / "nope.csv"))


def test_read_csv_uppercase_extension_is_ok(tmp_path):
    path = write(tmp_path, "ticket_id,message\nT1,Hello\n", name="T.CSV")
    assert read_csv(path)[0]["ticket_id"] == "T1"


# --- quick_check: first look without loading the file ---

def test_quick_check_counts_rows_and_rejected(tmp_path):
    path = write(tmp_path, "ticket_id,message\nT1,ok\n,no id\nT3,\nT1,ok\n, \n")
    rows, reasons, first = quick_check(path)
    assert rows == 5
    assert reasons == {"empty ticket_id": 1, "empty message": 1, "empty ticket_id and message": 1}
    assert first == [(3, "empty ticket_id"), (4, "empty message"), (6, "empty ticket_id and message")]


def test_quick_check_keeps_only_a_few_examples(tmp_path):
    path = write(tmp_path, "ticket_id,message\n" + ",x\n" * 100)
    rows, reasons, first = quick_check(path, examples=3)
    assert rows == 100
    assert reasons["empty ticket_id"] == 100
    assert [row for row, _ in first] == [2, 3, 4]


def test_quick_check_agrees_with_validation():
    rows, reasons, _ = quick_check("data/sample_tickets.csv")
    valid, rejected = validation(read_csv("data/sample_tickets.csv"))
    assert rows == len(valid) + len(rejected)
    assert sum(reasons.values()) == len(rejected)


def test_quick_check_runs_the_same_file_checks(tmp_path):
    with pytest.raises(ValueError, match="Missing column: message"):
        quick_check(write(tmp_path, "ticket_id,text\nT1,x\n"))
