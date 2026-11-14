from ticket_organizer.reader import validation, remove_duplicates


def test_good_row_is_valid():
    valid, rejected = validation([{"ticket_id": "T1", "message": "Hello"}])
    assert valid == [{"row": 2, "ticket_id": "T1", "message": "Hello"}]
    assert rejected == []


def test_values_are_stripped():
    valid, _ = validation([{"ticket_id": "  T1 ", "message": "  Hello  "}])
    assert valid[0]["ticket_id"] == "T1"
    assert valid[0]["message"] == "Hello"


def test_empty_ticket_id_is_rejected():
    valid, rejected = validation([{"ticket_id": "   ", "message": "Hello"}])
    assert valid == []
    assert rejected == [
        {"row": 2, "ticket_id": "", "message": "Hello", "reason": "empty ticket_id"}
    ]


def test_empty_message_is_rejected():
    _, rejected = validation([{"ticket_id": "T1", "message": ""}])
    assert rejected[0]["reason"] == "empty message"


def test_missing_value_none_is_rejected():
    # DictReader gives None when a row has fewer columns than the header.
    _, rejected = validation([{"ticket_id": "T1", "message": None}])
    assert rejected[0]["reason"] == "empty message"


def test_row_numbers_start_at_2_and_count_every_row():
    rows = [
        {"ticket_id": "T1", "message": "ok"},
        {"ticket_id": "", "message": "no id"},
        {"ticket_id": "T3", "message": "ok"},
    ]
    valid, rejected = validation(rows)
    assert [r["row"] for r in valid] == [2, 4]
    assert rejected[0]["row"] == 3


def test_both_empty_is_rejected_with_combined_reason():
    _, rejected = validation([{"ticket_id": " ", "message": ""}])
    assert rejected[0]["reason"] == "empty ticket_id and message"

def test_exact_duplicate_is_skipped():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": "T1", "message": "Hello"},
    ])
    unique, skipped = remove_duplicates(valid)
    assert unique == [{"row": 2, "ticket_id": "T1", "message": "Hello"}]
    assert skipped == [
        {"row": 3, "ticket_id": "T1", "message": "Hello", "reason": "duplicate of row 2"}
    ]


def test_duplicate_after_strip_is_skipped():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": " T1 ", "message": "  Hello "},
    ])
    _, skipped = remove_duplicates(valid)
    assert [r["row"] for r in skipped] == [3]


def test_same_id_different_message_is_follow_up():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "Hello"},
        {"ticket_id": "T1", "message": "Any update?"},
    ])
    unique, skipped = remove_duplicates(valid)
    assert [r["row"] for r in unique] == [2, 3]
    assert skipped == []


def test_same_message_different_id_is_kept():
    valid, _ = validation([
        {"ticket_id": "T1", "message": "I can't log in"},
        {"ticket_id": "T2", "message": "I can't log in"},
    ])
    unique, skipped = remove_duplicates(valid)
    assert len(unique) == 2
    assert skipped == []
