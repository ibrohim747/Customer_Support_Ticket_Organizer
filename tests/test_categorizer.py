from ticket_organizer.categorizer import categorize, load_rules


def test_billing():
    assert categorize("I was charged twice for my monthly plan.") == ["Billing"]


def test_account():
    assert categorize("I cannot reset my password.") == ["Account"]


def test_technical():
    assert categorize("The app crashes when I switch language.") == ["Technical"]


def test_no_match_is_other():
    assert categorize("Do you offer student discounts?") == ["Other"]


def test_multi_match_returns_all_in_stable_order():
    # Order = sorted category names (file names), not the order of words in the text.
    assert categorize("I was charged twice and now I can't log in.") == ["Account", "Billing"]
    assert categorize("I can't log in and I was charged twice.") == ["Account", "Billing"]


def test_word_forms_charged_is_billing():
    assert categorize("I was charged.") == ["Billing"]


def test_discharge_is_not_billing():
    assert categorize("The battery discharge on my device is fast.") == ["Other"]


def test_uppercase_matches():
    assert categorize("I WAS CHARGED TWICE!!!") == ["Billing"]


def test_typo_from_keyword_file():
    assert categorize("My biling statement is wrong.") == ["Billing"]


def test_phrase_with_extra_spaces():
    assert categorize("I cannot log    in") == ["Account"]


def test_load_rules_skips_comments_and_empty_lines(tmp_path):
    (tmp_path / "billing.txt").write_text("# comment\n\nRefund\n  invoice  \n", encoding="utf-8")
    assert load_rules(tmp_path) == {"Billing": ["refund", "invoice"]}
