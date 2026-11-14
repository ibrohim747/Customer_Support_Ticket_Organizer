from ticket_organizer.reader import validation


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
