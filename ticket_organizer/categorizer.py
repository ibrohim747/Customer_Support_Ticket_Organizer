import re
from pathlib import Path

# keywords/ folder in the project root (one level above this package).
KEYWORDS_DIR = Path(__file__).resolve().parent.parent / "keywords"
OTHER = "Other"


def load_rules(keywords_dir=KEYWORDS_DIR):
    """Read keywords/<category>.txt files -> {"Account": [...], "Billing": [...], ...}.

    The file name is the category name. Lines starting with # and empty lines are ignored.
    Files are read in sorted order, so the order of categories is always the same.
    """
    rules = {}
    for path in sorted(Path(keywords_dir).glob("*.txt")):
        keywords = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                keywords.append(line)
        rules[path.stem.capitalize()] = keywords
    return rules


def _keyword_pattern(keyword):
    # Whole word / whole phrase only: "charge" must not match inside "discharge".
    # (?<!\w) / (?!\w) work like \b, but also when a keyword starts or ends with
    # a non-letter. Spaces inside a phrase match any amount of whitespace.
    words = [re.escape(word) for word in keyword.split()]
    return r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)"


def compile_rules(rules):
    """{"Billing": ["charge", ...]} -> {"Billing": one compiled regex for all its keywords}."""
    return {
        category: re.compile("|".join(_keyword_pattern(k) for k in keywords), re.IGNORECASE)
        for category, keywords in rules.items()
        if keywords
    }


_DEFAULT_PATTERNS = None


def categorize(message, patterns=None):
    """Return all matching categories in a stable order; no match -> ["Other"]."""
    global _DEFAULT_PATTERNS
    if patterns is None:
        if _DEFAULT_PATTERNS is None:
            _DEFAULT_PATTERNS = compile_rules(load_rules())
        patterns = _DEFAULT_PATTERNS

    found = [category for category, pattern in patterns.items() if pattern.search(message)]
    return found or [OTHER]


if __name__ == "__main__":
    from ticket_organizer.reader import read_csv, validation, remove_duplicates

    valid, _ = validation(read_csv("data/sample_tickets.csv"))
    unique, _ = remove_duplicates(valid)
    for ticket in unique:
        print(ticket.row, ticket.ticket_id, categorize(ticket.message), ticket.message)
