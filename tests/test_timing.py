import pytest

from ticket_organizer.timing import format_duration, format_timings, timed


@pytest.mark.parametrize("seconds, text", [
    (0.0004, "0.4 ms"),
    (0.0123, "12 ms"),
    (0.5, "500 ms"),
    (2.345, "2.35 s"),
    (125, "2 min 5 s"),
])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


def test_timed_records_the_step():
    timings = {}
    with timed(timings, "step"):
        sum(range(1000))
    assert list(timings) == ["step"]
    assert timings["step"] >= 0


def test_timed_with_none_records_nothing():
    with timed(None, "step"):
        pass  # must not fail


def test_timed_records_even_when_the_step_fails():
    timings = {}
    with pytest.raises(ValueError):
        with timed(timings, "broken"):
            raise ValueError
    assert "broken" in timings


def test_format_timings_with_total():
    text = format_timings({"read": 0.5, "save": 1.5})
    assert text.splitlines() == [
        "Time:",
        "  read:  500 ms",
        "  save:  1.50 s",
        "  total: 2.00 s",
    ]


def test_format_timings_one_step_has_no_total():
    assert format_timings({"export .sql": 0.002}) == "Time:\n  export .sql: 2.0 ms"
