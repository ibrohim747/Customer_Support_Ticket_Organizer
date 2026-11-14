import pytest

from ticket_organizer.storage import count_messages, count_per_category, db_creator, save_messages


@pytest.fixture
def conn():
    conn = db_creator(":memory:")
    yield conn
    conn.close()


def rec(ticket_id, message, categories, row=2):
    return {"row": row, "ticket_id": ticket_id, "message": message, "categories": categories}


def all_rows(conn):
    return conn.execute("SELECT ticket_id, message, category FROM messages ORDER BY category").fetchall()


def test_insert_one_message(conn):
    saved, skipped = save_messages(conn, [rec("T1", "I was charged", ["Billing"])])
    assert len(saved) == 1
    assert skipped == []
    assert all_rows(conn) == [("T1", "I was charged", "Billing")]


def test_multi_category_message_is_two_rows(conn):
    save_messages(conn, [rec("T1", "charged and can't log in", ["Account", "Billing"])])
    assert all_rows(conn) == [
        ("T1", "charged and can't log in", "Account"),
        ("T1", "charged and can't log in", "Billing"),
    ]
    assert count_messages(conn) == 1


def test_reinsert_same_message_is_skipped_once(conn):
    message = rec("T1", "charged and can't log in", ["Account", "Billing"])
    save_messages(conn, [message])

    saved, skipped = save_messages(conn, [message])

    assert saved == []
    assert len(skipped) == 1  # one message, not 2 rows
    assert skipped[0]["reason"] == "already in database"
    assert len(all_rows(conn)) == 2  # DB content did not change


def test_running_same_file_twice_gives_same_db(conn):
    records = [
        rec("T1", "I was charged", ["Billing"], row=2),
        rec("T2", "Password reset", ["Account"], row=3),
        rec("T1", "Also the app crashed", ["Technical"], row=4),  # follow-up
    ]
    save_messages(conn, records)
    before = all_rows(conn)

    saved, skipped = save_messages(conn, records)

    assert saved == []
    assert [r["row"] for r in skipped] == [2, 3, 4]
    assert all_rows(conn) == before


def test_same_id_different_message_is_saved(conn):
    save_messages(conn, [rec("T1", "First", ["Other"])])
    saved, skipped = save_messages(conn, [rec("T1", "Follow-up", ["Other"])])
    assert len(saved) == 1
    assert skipped == []


def test_count_per_category(conn):
    save_messages(conn, [
        rec("T1", "a", ["Billing"]),
        rec("T2", "b", ["Account", "Billing"]),
        rec("T3", "c", ["Other"]),
    ])
    assert count_per_category(conn) == {"Account": 1, "Billing": 2, "Other": 1}
    assert count_messages(conn) == 3  # categories sum to 4, messages are 3


def test_error_rolls_back_whole_call(conn):
    good = rec("T1", "a", ["Billing"])
    bad = {"row": 3, "ticket_id": "T2", "message": "b"}  # no "categories" -> KeyError
    with pytest.raises(KeyError):
        save_messages(conn, [good, bad])
    assert all_rows(conn) == []  # "good" was not half-saved


def test_sql_injection_text_is_stored_as_plain_text(conn):
    evil = "x'); DROP TABLE messages; --"
    save_messages(conn, [rec("T1", evil, ["Other"])])
    assert all_rows(conn) == [("T1", evil, "Other")]


def test_db_creator_makes_missing_folder(tmp_path):
    conn = db_creator(str(tmp_path / "new_folder" / "tickets.db"))
    conn.close()
    assert (tmp_path / "new_folder" / "tickets.db").exists()
