# Customer Support Ticket Organizer

Reads customer messages from a CSV file, rejects broken rows, skips duplicates,
assigns one or more categories (Billing, Account, Technical, Other) by keyword rules,
stores the messages in an SQLite database and writes a summary.

## Quick start

Needs `git` and **one** of: [Docker](https://docs.docker.com/get-docker/) or
[Python 3.10+](https://www.python.org/downloads/). Nothing else to install.

```
git clone https://github.com/ibrohim747/Customer_Support_Ticket_Organizer.git
cd Customer_Support_Ticket_Organizer
./start.sh
```

`start.sh` uses Docker if it is available (builds the image: about a minute the first time,
a few seconds later), otherwise Python — the program needs only the standard library,
so no virtual environment or `pip install` is needed just to run it. Then it asks you:

1. **Select a CSV file** — a numbered list of files from `input/` (put your own files there)
   and the sample `data/sample_tickets.csv`. Press Enter for the first one, type a number,
   or **drag and drop a CSV file into the terminal window** (or type its path).
   With Docker, files from your home folder and `input/` can be used
   (`start.sh` connects your home folder to the container; files are created as your user).
2. **Preliminary analysis** — a quick first look, nothing is saved: **rows in the file** and
   **rejected rows** (with reasons and the first row numbers). The file is read row by row and not kept
   in memory, so this is fast even for a very large file. Categories, duplicates and the database
   check come only in the full analysis.
3. **Run the full analysis and save the results? [y/n]**
4. **Save the results to `<folder>/output/`? [y/n]** — `y`: an `output/` folder is created
   **next to the input file** and gets all results: the database `tickets.db`, `<name>_summary.json` and
   `<name>_rejected.csv`. For files from the project's `input/` or `data/` this is the project's `output/`
   (next to `input/`). `n` = type (or drag and drop) another folder; Enter there = the project's `output/`.
   If the folder cannot be created (no write access), the program asks for another one right away.
   Each output folder has its own database, so "already in database" works per folder.
5. **Export the database as a .sql file for PostgreSQL? [y/n]** — the program first notes that no
   PostgreSQL server is connected and shows the full path of the SQLite file. `y` = `tickets.sql`
   (`CREATE TABLE` + `INSERT`s) is written to the same output folder, with the command to import it:
   `psql -d your_db -f tickets.sql`.
6. **Check another file? [y/n]** — `n` ends the program.

All yes/no questions end with `[y/n]` and understand small and capital letters
(`y`, `Y`, `yes`, `n`, `N`, `no`, also `да` / `нет`). There is no hidden default: Enter alone asks again.

`./start.sh input/my_tickets.csv` runs the full analysis of one file without questions.
`./start.sh --python` / `./start.sh --docker` forces one way. On Windows run `start.sh` from Git Bash or WSL.

## Setup (without Docker)

Requires Python 3.10+.

```
git clone https://github.com/ibrohim747/Customer_Support_Ticket_Organizer.git
cd Customer_Support_Ticket_Organizer
python -m venv .venv
```

On Linux / macOS the command may be `python3` instead of `python`. On Debian / Ubuntu,
if `venv` is missing, install it first: `sudo apt install python3-venv`.

Activate the virtual environment (needed in every new terminal):

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- macOS / Linux: `source .venv/bin/activate`

Install dependencies:

```
pip install -r requirements.txt
```

## Usage

Run from the project root with the virtual environment activated:

```
python -m ticket_organizer data/sample_tickets.csv
```

Without a file the program starts in **interactive mode** (the same questions as in
[Quick start](#quick-start)):

```
python -m ticket_organizer
```

Example output:

```
Rows read:  19
Accepted:   14
Rejected:   4
Skipped:    1 (duplicate in file: 1, already in DB: 0)

Categories (this run):
  Account    4
  Billing    4
  Other      4
  Technical  3
...
```

Options (all optional):

| Option | Default | What it is |
|---|---|---|
| `--db` | `output/tickets.db` | SQLite database, created if missing |
| `--summary` | `output/summary.json` | summary of the run as JSON |
| `--rejected` | `output/rejected.csv` | rejected rows: `row, ticket_id, message, reason` |
| `--export-sql` | (none) | also export the whole database as a `.sql` file for PostgreSQL |

Example with options:

```
python -m ticket_organizer my_tickets.csv --db output/test.db --summary output/test_summary.json
```

`python -m ticket_organizer --help` shows the same information.

Exit code: `0` on success, `1` if the input file cannot be processed
(not found, not a `.csv`, missing `ticket_id` / `message` column, not UTF-8),
`2` if the command line is wrong.

## Docker

`./start.sh` (see [Quick start](#quick-start)) does all of this for you. The manual commands:

Build the image (from the project root):

```
docker build -t ticket-organizer .
```

Create the output folder first. If it is missing, Docker creates it as `root`,
and with `--user` (see notes below) the program cannot write there:

```
mkdir -p output
```

Run on the sample file. `-v` connects the local `output/` folder to the container,
so the database, summary and rejected rows stay on your computer after the container exits:

```
docker run --rm -v "$(pwd)/output:/app/output" ticket-organizer data/sample_tickets.csv
```

Interactive mode in Docker needs `-it` (a keyboard):

```
docker run --rm -it --user "$(id -u):$(id -g)" -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" ticket-organizer
```

Run on your own CSV — put it into a folder (here `input/`) and connect that folder too:

```
docker run --rm -v "$(pwd)/input:/app/input" -v "$(pwd)/output:/app/output" ticket-organizer input/my_tickets.csv
```

All options from [Usage](#usage) work the same way, e.g. `... ticket-organizer input/my_tickets.csv --db output/test.db`.

Run the tests inside the container:

```
docker run --rm --entrypoint pytest ticket-organizer
```

Notes:
- Windows PowerShell: write `${PWD}` instead of `$(pwd)`.
- Linux: files in `output/` are created by `root`. Add `--user "$(id -u):$(id -g)"` after `docker run`
  to create them as your user.
- After changing the code or keyword files, run `docker build` again.

## Input file

- CSV, UTF-8 (with or without BOM — "CSV UTF-8" from Excel works).
- The header must contain `ticket_id` and `message`. Other columns and column order do not matter.
- If a required column is missing, the whole file is refused with an error.

## Validation

- Values are stripped of spaces at the start and end.
- Empty `ticket_id` or empty `message` (also only spaces) → the row is **rejected**,
  saved to `rejected.csv` with its row number and reason. A bad row never stops the program.
- Row numbers are the line numbers in the file (the header is row 1), the same as in Excel.

## Categorization

- Keyword rules are data, not code: `keywords/<category>.txt`, one keyword or phrase per line,
  `#` for comments. The file name is the category name.
- Matching ignores case and works on **whole words / phrases**:
  "I was charged" matches because `charged` is in the list, but `charge` does not match inside "discharge".
- Word forms and common typos are listed in the keyword files (no stemming).
- A message gets **all** matching categories (e.g. "I was charged twice and can't log in" →
  Account + Billing). No match → `Other`.
- Categories are returned in alphabetical order, so the result is always the same.
- To add a category, add a new `keywords/<name>.txt` file. No code changes.

## Duplicates and re-processing

- **Exact duplicate inside the file** (same `ticket_id` **and** same `message` after stripping) → skipped.
- **Same `ticket_id` with a different message** → accepted, treated as a follow-up of the same ticket.
- **Message already in the database** (from an earlier run) → skipped.
  Running the same file twice gives the same database; the second run reports every message as skipped.
- One file is saved in one transaction: if the program fails halfway, nothing from that file is saved,
  and it can simply be run again.

## Database

One table:

```sql
messages (ticket_id TEXT, message TEXT, category TEXT, UNIQUE(ticket_id, message, category))
```

One row per (message, category): a message with two categories is stored as two rows.
This keeps the insert code simple; the cost is that the message text repeats per category.
For a large database, two tables (`messages` + `message_categories`) would be better.

The database is an SQLite **file** (`tickets.db`), no database server is needed. To move the data into
PostgreSQL, export it (`--export-sql FILE` or the question in interactive mode) and import the file with
`psql -d your_db -f FILE`. The export is plain SQL (`CREATE TABLE` + `INSERT`, quotes doubled), checked by
importing it into a real PostgreSQL 16.

## Summary

After each run the program prints a summary and saves it to `output/summary.json`;
rejected rows go to `output/rejected.csv`.

- `rows_read = accepted + rejected + skipped`, counted per message (not per database row).
  The program checks this and stops with an error if the numbers do not add up.
- `skipped` = exact duplicates inside the file + messages already saved by an earlier run.
- Category counts are shown twice: for **this run** (messages saved now) and for the
  **whole database**. A message can have several categories, so the category sum can be
  bigger than the number of accepted messages.

## Assumptions and limitations

- Messages are in **English**; keywords are English only.
- Keyword matching does not understand meaning: synonyms that are not in the lists are missed
  ("my bank statement shows two debits" → Other), and a keyword in an unrelated sense still matches
  ("Any update?" → Technical, because `update` is a Technical keyword).
- Only typos listed in the keyword files are recognized.
- Duplicate check is exact and case-sensitive: "Hello" and "hello" are different messages.
- The whole file is read into memory — fine for thousands of rows, not for very large files.

## Running the tests

With the virtual environment activated, from the project root:

```
pytest
```

Useful variants: `pytest -v` (one line per test), `pytest tests/test_reader.py` (one file),
`pytest -k duplicate` (tests whose name contains "duplicate").

## Project structure

```
ticket_organizer/   program code
  reader.py         read the CSV, validate rows, remove duplicates inside the file
  categorizer.py    keyword rules -> categories
  storage.py        SQLite: save messages, count per category
  summary.py        build / print / save the summary and rejected.csv
  cli.py            command line (argparse), runs all steps
  interactive.py    interactive mode: choose file, preliminary analysis, confirm, full analysis
  __main__.py       makes `python -m ticket_organizer` work
keywords/           keyword rules, one file per category
data/               sample input (sample_tickets.csv) and its expected results
tests/              pytest tests
input/              your own CSV files for interactive mode — not in git (created by start.sh)
output/             generated files (database, summary, rejected rows) — not in git
start.sh            one-command start (Docker or Python)
NOTES.md            development notes and how AI was used
Dockerfile          Docker image (see "Docker"); .dockerignore lists what is left out
```
