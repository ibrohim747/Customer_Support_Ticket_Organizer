# Customer Support Ticket Organizer

Reads customer messages from a CSV file, validates them, assigns categories by keyword rules,
stores them in SQLite and writes a summary.

## Setup

Requires Python 3.10+.

```
git clone https://github.com/ibrohim747/Customer_Support_Ticket_Organizer.git
cd Customer_Support_Ticket_Organizer
python -m venv .venv
```

Activate the virtual environment:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- macOS / Linux: `source .venv/bin/activate`

Install dependencies and run the tests:

```
pip install -r requirements.txt
pytest
```

## Usage

Run from the project root with the virtual environment activated:

```
python -m ticket_organizer data/sample_tickets.csv
```

Options (all optional): `--db` (default `output/tickets.db`), `--summary` (default
`output/summary.json`), `--rejected` (default `output/rejected.csv`).
See `python -m ticket_organizer --help`.

Exit code: `0` on success, `1` if the input file cannot be processed
(not found, not a `.csv`, missing `ticket_id` / `message` column, not UTF-8),
`2` if the command line is wrong.

## Summary

After each run the program prints a summary and saves it to `output/summary.json`;
rejected rows (row number, ticket_id, message, reason) go to `output/rejected.csv`.

- `rows_read = accepted + rejected + skipped`, counted per message.
- `skipped` = exact duplicates inside the file + messages already saved by an earlier run.
- Category counts are shown twice: for **this run** (messages saved now) and for the
  **whole database**. A message can have several categories, so the category sum can be
  bigger than the number of accepted messages.
