import csv
from collections import Counter
from pathlib import Path

from ticket_organizer.models import SkippedCounts, Summary


def build_summary(rows_read, accepted, rejected, duplicates, already_in_db, categories_in_db):
    """Collect the numbers of one run into a models.Summary.

    accepted       — Tickets saved in this run (each has categories)
    rejected       — rows with empty ticket_id / message
    duplicates     — exact duplicates inside the file
    already_in_db  — messages saved by an earlier run
    Everything is counted per message (not per DB row). The Summary model itself checks
    rows_read == accepted + rejected + skipped and raises ValidationError (a ValueError) if not.
    """
    category_counts = Counter(c for ticket in accepted for c in ticket.categories)
    return Summary(
        rows_read=rows_read,
        accepted=len(accepted),
        rejected=len(rejected),
        skipped=SkippedCounts(
            duplicate_in_file=len(duplicates),
            already_in_db=len(already_in_db),
            total=len(duplicates) + len(already_in_db),
        ),
        categories_this_run=dict(sorted(category_counts.items())),
        categories_in_db=dict(categories_in_db),
    )


def format_summary(summary):
    skipped = summary.skipped
    lines = [
        f"Rows read:  {summary.rows_read}",
        f"Accepted:   {summary.accepted}",
        f"Rejected:   {summary.rejected}",
        f"Skipped:    {skipped.total} "
        f"(duplicate in file: {skipped.duplicate_in_file}, already in DB: {skipped.already_in_db})",
        "",
        "Categories (this run):",
    ]
    lines += _category_lines(summary.categories_this_run)
    lines += ["", "Categories (whole database):"]
    lines += _category_lines(summary.categories_in_db)
    return "\n".join(lines)


def _category_lines(counts):
    if not counts:
        return ["  (none)"]
    return [f"  {category:<10} {count}" for category, count in counts.items()]


def save_summary_json(summary, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # The model writes itself as JSON (same shape as before: nested "skipped", category dicts).
    Path(path).write_text(summary.model_dump_json(indent=2), encoding="utf-8")


def save_rejected_csv(rejected, path):
    """Write rejected rows: row, ticket_id, message, reason.

    utf-8-sig (with BOM) so Excel shows non-English text correctly.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["row", "ticket_id", "message", "reason"])
        writer.writeheader()
        for record in rejected:
            writer.writerow(record.model_dump(include=set(writer.fieldnames)))


if __name__ == "__main__":
    from ticket_organizer.categorizer import categorize
    from ticket_organizer.reader import read_csv, remove_duplicates, validation
    from ticket_organizer.storage import count_per_category, db_creator, save_messages

    rows = read_csv("data/sample_tickets.csv")
    valid, rejected = validation(rows)
    unique, duplicates = remove_duplicates(valid)
    for ticket in unique:
        ticket.categories = categorize(ticket.message)

    conn = db_creator("output/tickets.db")
    saved, already = save_messages(conn, unique)
    summary = build_summary(len(rows), saved, rejected, duplicates, already, count_per_category(conn))
    conn.close()

    print(format_summary(summary))
    save_summary_json(summary, "output/summary.json")
    save_rejected_csv(rejected, "output/rejected.csv")
