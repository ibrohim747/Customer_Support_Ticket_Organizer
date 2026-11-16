import sqlite3
from pathlib import Path


def db_creator(db_path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "ticket_id TEXT, message TEXT, category TEXT, "
        "UNIQUE(ticket_id, message, category))"
    )
    conn.commit()
    return conn


def _is_saved(conn, ticket_id, message):
    row = conn.execute(
        "SELECT 1 FROM messages WHERE ticket_id = ? AND message = ? LIMIT 1",
        (ticket_id, message),
    ).fetchone()
    return row is not None


def save_messages(conn, records):
    """Save records {"row", "ticket_id", "message", "categories"}: one DB row per category.

    A message whose (ticket_id, message) is already in the DB is skipped as a whole
    and reported once, no matter how many categories it has.
    Everything is saved in one transaction: if something fails, nothing from this
    call is saved (no half-saved file, no half-saved message).
    Returns (saved, skipped) — lists of records, counted per message, not per DB row.
    """
    saved = []
    skipped = []
    with conn:  # commit at the end, rollback on any error
        for record in records:
            if _is_saved(conn, record["ticket_id"], record["message"]):
                skipped.append({**record, "reason": "already in database"})
                continue
            conn.executemany(
                "INSERT INTO messages (ticket_id, message, category) VALUES (?, ?, ?)",
                [(record["ticket_id"], record["message"], c) for c in record["categories"]],
            )
            saved.append(record)
    return saved, skipped


def count_per_category(conn):
    """{"Account": 3, "Billing": 5, ...} — sorted by category name."""
    rows = conn.execute(
        "SELECT category, COUNT(*) FROM messages GROUP BY category ORDER BY category"
    ).fetchall()
    return dict(rows)


def count_messages(conn):
    """Number of messages, not rows: a 2-category message is 2 rows but 1 message.

    SQLite does not allow COUNT(DISTINCT ticket_id, message) with two columns,
    so count the rows of a DISTINCT subquery instead.
    """
    return conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT ticket_id, message FROM messages)"
    ).fetchone()[0]


def _sql_text(value):
    # Standard SQL string literal: wrap in '...' and double every ' inside (It's -> 'It''s').
    return "'" + value.replace("'", "''") + "'"


def export_sql(conn, path):
    """Write the whole database as a .sql file for PostgreSQL (CREATE TABLE + INSERTs).

    Plain standard SQL — SQLite can read it too (used by the tests).
    Returns the number of exported rows.
    """
    rows = conn.execute(
        "SELECT ticket_id, message, category FROM messages ORDER BY ticket_id, message, category"
    ).fetchall()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(
            "-- Customer Support Ticket Organizer: export of the messages table for PostgreSQL.\n"
            "-- One row per (message, category). Import into an empty database:\n"
            "--   psql -d your_db -f this_file.sql\n\n"
            "CREATE TABLE IF NOT EXISTS messages (\n"
            "    ticket_id VARCHAR(255) NOT NULL,\n"
            "    message   TEXT         NOT NULL,\n"
            "    category  VARCHAR(100) NOT NULL\n"
            ");\n\n"
            "BEGIN;\n"
        )
        for ticket_id, message, category in rows:
            file.write(
                "INSERT INTO messages (ticket_id, message, category) VALUES "
                f"({_sql_text(ticket_id)}, {_sql_text(message)}, {_sql_text(category)});\n"
            )
        file.write("COMMIT;\n")
    return len(rows)


if __name__ == "__main__":
    from ticket_organizer.categorizer import categorize
    from ticket_organizer.reader import read_csv, remove_duplicates, validation

    valid, rejected = validation(read_csv("data/sample_tickets.csv"))
    unique, duplicates = remove_duplicates(valid)
    for record in unique:
        record["categories"] = categorize(record["message"])

    conn = db_creator("output/tickets.db")
    saved, already = save_messages(conn, unique)
    print(f"saved: {len(saved)}, already in DB: {len(already)}, "
          f"rejected: {len(rejected)}, duplicates: {len(duplicates)}")
    print(f"messages in DB: {count_messages(conn)}, per category: {count_per_category(conn)}")
    conn.close()
