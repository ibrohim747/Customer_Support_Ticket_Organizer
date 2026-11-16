import os
import csv
from collections import Counter


def iter_rows(file_path):
    """Check the file, then give its rows one by one (the whole file is never kept in memory)."""
    if not file_path.lower().endswith('.csv'):
        raise ValueError(f"Not a .csv file: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    if os.path.getsize(file_path) == 0:
        raise ValueError("The file is empty.")

    with open(file_path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if "ticket_id" not in reader.fieldnames:
            raise ValueError("Missing column: ticket_id")
        if "message" not in reader.fieldnames:
            raise ValueError("Missing column: message")
        yield from reader


def read_csv(file_path):
    return list(iter_rows(file_path))


def clean_row(row):
    """Strip the values; a short row gives None instead of "" -> "or ''" turns it into ""."""
    return (row["ticket_id"] or "").strip(), (row["message"] or "").strip()


def reject_reason(ticket_id, message):
    """Why a row is rejected, or None if it is valid."""
    if ticket_id == "" and message == "":
        return "empty ticket_id and message"
    if ticket_id == "":
        return "empty ticket_id"
    if message == "":
        return "empty message"
    return None


def validation(rows):
    valid = []
    rejected = []
    # Line 1 of the file is the header, so the first data row is line 2.
    for row_number, row in enumerate(rows, start=2):
        ticket_id, message = clean_row(row)
        reason = reject_reason(ticket_id, message)
        record = {"row": row_number, "ticket_id": ticket_id, "message": message}
        if reason is None:
            valid.append(record)
        else:
            record["reason"] = reason
            rejected.append(record)
    return valid, rejected


def quick_check(file_path, examples=5):
    """Fast first look at a file of any size: count rows and rejected rows, nothing else.

    Rows are read one by one and not kept, so memory use does not grow with the file.
    Returns (rows, rejected_by_reason, first_rejected) — first_rejected is a list of
    (row_number, reason) for at most `examples` rows.
    """
    rows = 0
    reasons = Counter()
    first_rejected = []
    for row_number, row in enumerate(iter_rows(file_path), start=2):
        rows += 1
        reason = reject_reason(*clean_row(row))
        if reason is not None:
            reasons[reason] += 1
            if len(first_rejected) < examples:
                first_rejected.append((row_number, reason))
    return rows, reasons, first_rejected


def remove_duplicates(valid):
    # Duplicate = same ticket_id AND same message (after strip).
    # Same id + different message is a follow-up -> kept.
    unique = []
    skipped = []
    first_row = {}  # (ticket_id, message) -> row number where it was first seen
    for record in valid:
        key = (record["ticket_id"], record["message"])
        if key in first_row:
            skipped.append({**record, "reason": f"duplicate of row {first_row[key]}"})
        else:
            first_row[key] = record["row"]
            unique.append(record)
    return unique, skipped


if __name__ == "__main__":
    res = read_csv("data/sample_tickets.csv")
    valid, rejected = validation(res)
    unique, skipped = remove_duplicates(valid)
    print(f"read: {len(res)}, accepted: {len(unique)}, "
          f"rejected: {len(rejected)}, skipped: {len(skipped)}")
    for record in rejected + skipped:
        print(record)