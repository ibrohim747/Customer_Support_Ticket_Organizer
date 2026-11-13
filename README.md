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
