import pytest
from pydantic import ValidationError

from ticket_organizer.models import (
    RejectedRow,
    SkippedCounts,
    Summary,
    Ticket,
    parse_row,
)


# --- Ticket: the rules of a valid message ---

def test_ticket_strips_spaces():
    ticket = Ticket(row=2, ticket_id="  T1 ", message="  Hello  ")
    assert (ticket.ticket_id, ticket.message) == ("T1", "Hello")


@pytest.mark.parametrize("field", ["ticket_id", "message"])
@pytest.mark.parametrize("value", ["", "   ", "\t", None])
def test_ticket_empty_value_is_invalid(field, value):
    data = {"row": 2, "ticket_id": "T1", "message": "Hello", field: value}
    with pytest.raises(ValidationError) as error:
        Ticket(**data)
    assert error.value.errors()[0]["loc"] == (field,)


def test_ticket_row_must_be_after_the_header():
    with pytest.raises(ValidationError):
        Ticket(row=1, ticket_id="T1", message="Hello")  # row 1 is the header


def test_ticket_row_given_as_text_is_converted():
    # Pydantic converts "5" -> 5 for an int field (useful: everything in a CSV is text).
    assert Ticket(row="5", ticket_id="T1", message="Hello").row == 5


def test_ticket_categories_default_to_empty_list_not_shared():
    a = Ticket(row=2, ticket_id="T1", message="a")
    b = Ticket(row=3, ticket_id="T2", message="b")
    a.categories.append("Billing")
    assert b.categories == []  # default_factory: each ticket gets its own list


def test_ticket_key_is_id_and_message():
    assert Ticket(row=2, ticket_id="T1", message="Hi").key == ("T1", "Hi")


def test_unknown_attribute_is_an_error_not_silent():
    ticket = Ticket(row=2, ticket_id="T1", message="Hi")
    with pytest.raises(AttributeError):
        ticket.mesage  # typo -> error at once (a dict would only fail on a missing key)


# --- parse_row: CSV row -> Ticket or RejectedRow with the old reasons ---

@pytest.mark.parametrize("ticket_id, message, reason", [
    ("", "Hello", "empty ticket_id"),
    ("T1", "  ", "empty message"),
    (None, None, "empty ticket_id and message"),
    (" ", "", "empty ticket_id and message"),
])
def test_parse_row_reasons(ticket_id, message, reason):
    result = parse_row(7, {"ticket_id": ticket_id, "message": message})
    assert isinstance(result, RejectedRow)
    assert result.row == 7
    assert result.reason == reason


def test_parse_row_valid():
    assert parse_row(2, {"ticket_id": " T1", "message": "Hi "}) == Ticket(
        row=2, ticket_id="T1", message="Hi"
    )


def test_parse_row_ignores_extra_columns():
    result = parse_row(2, {"ticket_id": "T1", "message": "Hi", "priority": "high"})
    assert isinstance(result, Ticket)


# --- Summary: the invariant lives in the model ---

def make_summary(**changes):
    data = {
        "rows_read": 10, "accepted": 6, "rejected": 3,
        "skipped": {"duplicate_in_file": 1, "already_in_db": 0, "total": 1},
        "categories_this_run": {"Billing": 7}, "categories_in_db": {"Billing": 7},
    }
    data.update(changes)
    return Summary(**data)


def test_summary_valid():
    summary = make_summary()
    assert summary.skipped == SkippedCounts(duplicate_in_file=1, already_in_db=0, total=1)


def test_summary_counts_must_add_up():
    with pytest.raises(ValidationError, match="Counts do not add up"):
        make_summary(rows_read=11)


def test_summary_skipped_total_must_be_the_sum():
    with pytest.raises(ValidationError, match="skipped.total"):
        make_summary(skipped={"duplicate_in_file": 1, "already_in_db": 1, "total": 1})


def test_summary_negative_count_is_invalid():
    with pytest.raises(ValidationError):
        make_summary(rejected=-1, accepted=10)


def test_summary_json_round_trip():
    summary = make_summary()
    assert Summary.model_validate_json(summary.model_dump_json()) == summary
