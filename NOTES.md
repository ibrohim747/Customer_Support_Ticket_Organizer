# NOTES — AI usage log

AI (Claude) is used as a mentor/reviewer, not as the author of the code.
Entries are drafted by Claude from our conversations; I review each one and fill in
**Verified by me** myself.

---

## 2026-11-12 — DB schema: two tables → one table

**What I asked:** The task list planned two tables (`messages` + `message_categories`).
After discussion I decided one table with 3 columns (`ticket_id`, `message`, `category`) is enough —
asked AI to update the tasks.

**What AI did:** Did not change anything at first; asked how multi-label categories are stored
in one `category` column and showed two options:
- A — one row per (message, category);
- B — one row per message, categories joined into a string (`"Billing,Technical"`) → `GROUP BY` breaks.

**My decision:** Option A. Table `tickets (ticket_id, message, category, UNIQUE(ticket_id, message, category))`.

**Why (my answer):** simpler code — no `lastrowid`, no second table.
AI pointed out: "no JOIN" is a weak argument — counting per category in the two-table design
did not need a JOIN either (`GROUP BY` on `message_categories`); JOIN is only needed to show
a message together with its categories.

**Cost (my answer):** message text repeats for every category; counting messages (not rows) is harder.

**Important consequence:** accepted / skipped must be counted **per message, not per DB row**,
otherwise a 2-category message is counted twice and breaks `read == accepted + rejected + skipped`.

**When to change:** if the DB grows large → go back to normalized `messages` + `message_categories`.
I first suggested "one table per category"; AI showed this contradicts decision 4
(new category without changing logic) and "categories are rows" — adding `Shipping` would need
a new table, a 2-category message would be stored in two tables, counting would need `UNION`.
Term to remember: **normalization**.

**Changed files:** `CLAUDE.md` (decision 5), `tasks/05-storage.md`.

**Verified by me:** _TODO_

---

## 2026-11-12 — Creating the DB + review of my first `CREATE TABLE`

**What I asked:** how to create the DB and look at it in TablePlus.

**What AI explained:**
- An empty file or `sqlite3.connect(path)` creates an SQLite DB.
- Don't put `.py` files into `output/` — it is for generated files only and is not committed.
- A relative path (`"tickets.db"`) is resolved from the **terminal's current folder**, not the script's
  folder → use `output/tickets.db` and run from the project root.
- Trap: `CREATE TABLE IF NOT EXISTS` silently keeps an old table if the schema changed →
  `DROP TABLE` and recreate; SQL in TablePlus must match `storage.py` exactly.

**My SQL (first version):**
```sql
CREATE TABLE IF NOT EXISTS messages (ticket_id INT, messege TEXT, UNIQUE(ticket_id, messege));
```

**Review findings:**
1. No `category` column, and `UNIQUE` must include it (option A: one row per category).
2. `ticket_id INT` → should be `TEXT`: ids like `T-001` are not numbers; with INT affinity
   `"007"` is stored as `7` (leading zeros lost) and `"1"` / `"01"` become the same id.
3. Typo `messege` → `message` (CSV header and code use `message`).
4. Table name `messages` vs `tickets` in CLAUDE.md — pick one and keep it consistent.

**Second version:**
```sql
CREATE TABLE IF NOT EXISTS messages (ticket_id TEXT, messege TEXT, category TEXT, UNIQUE(messege, category));
```
Fixed: `ticket_id TEXT`, `category` added.
Still wrong: `ticket_id` was removed from `UNIQUE` → the same text from two different tickets
(e.g. two customers write "I can't log in") would be treated as a duplicate and the second one lost.
Contradicts decision 3 (duplicate = same id **and** same message). Typo `messege` still there.

**Table name:** I chose `messages` (renamed from `tickets` in CLAUDE.md and tasks/05).

**Open question:** I then thought `UNIQUE` is not needed at all, because every column can repeat.
AI: true for each column **alone**, but the **combination** `(ticket_id, message, category)` must not
repeat — without `UNIQUE` a second run of the same file inserts everything again
(breaks idempotency, decision 5).
→ **My conclusion (checked in TablePlus):** all three columns go into `UNIQUE`.
- same row twice → `UNIQUE constraint failed` ✔ (protects re-processing)
- same id + text, other category → inserted ✔ (multi-label)
- other id, same text + category → inserted ✔; with `UNIQUE(message, category)` the second customer would be lost.

**Fixed version** (created via Python REPL from the project root, `sqlite3.connect("output/tickets.db")`):
```sql
CREATE TABLE IF NOT EXISTS messages (ticket_id TEXT, message TEXT, category TEXT, UNIQUE(ticket_id, message, category))
```
Then `conn.commit()`, `conn.close()`. First attempt missed the `( ... )` around the column list.

**Verified by me:** _TODO_

---

## 2026-11-12 — `storage.py`: first function `db_creator(db_path)`

**What I asked:** the DB must be created by the program, because `*.db` is not in git and a reviewer
who clones the repo needs their own DB.

**What AI did:** reviewed my code, did not write it (gave a generic example + fill-in hints).

**Review findings on my first version:**
1. Path was hard-coded (`"output/tickets.db"`) → now a parameter `db_path`
   (tests use `":memory:"` / `tmp_path`, CLI will pass `--db`).
2. `conn.close()` + `return 1` → the connection is needed for inserts later → now `return conn`.
   With `close()` the caller gets `sqlite3.ProgrammingError: Cannot operate on a closed database`.
3. I first pasted the generic example (`open_log`) into the project literally — it was only an illustration.
4. Minor: indentation uses tabs; PEP 8 recommends 4 spaces.

**Checked:** `db_creator(":memory:")` → `SELECT * FROM messages` returns `[]` (table exists, empty).

**Verified by me:** _TODO_

---

## 2026-11-12 — `db_creator`: create the folder if it is missing

**Problem:** the reviewer clones the repo without `output/` contents →
`sqlite3.connect("nofolder/test.db")` → `sqlite3.OperationalError: unable to open database file`.
SQLite creates the **file**, but not the **folder**.

**Fix (mine):** `Path(db_path).parent.mkdir(parents=True, exist_ok=True)` before `connect`.

**Mistakes on the way:**
- `Path(db_path, "/output/")` → a part starting with `/` is absolute and **replaces** everything before it
  → result `\output`, `.parent` = `\` (drive root); the needed folder was never created.
- `db_path = "output/tickets.db"` inside the function → overwrote the parameter; every call
  (even `":memory:"`) wrote to the real DB.

**Learned:** `Path` only holds a string; a relative path is resolved from the folder where `python`
was started, at the moment of `mkdir` / `connect`.

**Checked:** in an empty folder `db_creator("nofolder/test.db")` creates `nofolder/test.db`, table exists;
`db_creator(":memory:")` works.

**Verified by me:** _TODO_

---

## 2026-11-12 — Where is the DB path decided?

**Question:** if a reviewer runs the program from the root, where is the DB created? Should
`db_creator` have a default path so the user doesn't need to type it?

**AI explained:** `db_creator` only knows *how* to create the DB; *where* is decided by the caller.
`cli.py` will have `--db` with a default (e.g. `output/tickets.db`), so the user never has to type it.
A default inside the function is also possible, but then: keep the default in **one** place only,
and a test that forgets `":memory:"` would silently write to the real DB.

**My decision:** no default in `db_creator(db_path)` — the path is always passed in;
the default lives in `cli.py` (`--db`, task 07).

**Verified by me:** _TODO_

---

## 2026-11-13 — Task 01: repo & environment setup

**What I did (myself):** `git init`, GitHub remote, `.gitignore`, `.venv`, `pytest`,
`requirements.txt`, `ticket_organizer/__init__.py`, smoke test. AI reviewed each step.

**Review findings / things I learned:**
- `git push` → `src refspec main does not match any`: the first commit was never created because
  nothing was staged (`git add` missing). Git commits only staged files.
- `*.db` must not be in git. My reason: personal customer data. AI added two more:
  it is a generated file (rebuilt from the CSV) and it is binary and changes on every run
  (unreadable diffs, merge conflicts).
- `.gitignore`, first version: `/venv, /__pycache__, /output, CLAUDE.md, /tasks`.
  1. Commas become part of the name → no rule matched.
  2. The folder is `.venv` (with a dot), not `venv`.
  3. A leading `/` means "only in the project root"; `__pycache__` is inside subfolders → no leading `/`.
  4. Trailing `/` marks a folder (`output/`) — clearer.
- **My decision:** ignore `CLAUDE.md` and `tasks/` — I will show them from my PC.
  AI noted: ignoring CLAUDE.md could look like hiding AI use; and files in the repo (README)
  must not link to ignored files.
- `.gitkeep` is only for empty folders → removed from `ticket_organizer/` and `tests/`.
- `pip freeze` lists 6 packages, not 1: pytest **depends on** them (dependencies), pip installs them automatically.
- In Windows PowerShell 5.1, `>` writes **UTF-16** → GitHub shows the file as binary.
  Fixed with `pip freeze | Out-File -Encoding utf8 requirements.txt` (UTF-8 with BOM; pip reads it fine).
- `__init__.py` makes the folder a package → `from ticket_organizer.storage import db_creator` works from tests.
- pytest finds tests by name: file `test_*.py`, function `test_*`.
  Dummy test was first named `test_storage` → misleading name → renamed to `test_smoke`.

**Verified by me:** _TODO_

---

## 2026-11-13 — README: Setup section written by AI

**What I asked:** short on time → asked AI to write the README "Setup" section; I check it afterwards.

**What AI did:** wrote `README.md` (title, one-line description, Setup: clone, venv, activate
on Windows / macOS-Linux, `pip install -r requirements.txt`, `pytest`). These are the same commands
I ran myself in task 01.

**How I verify:** clone the repo into an empty folder, follow README step by step, `pytest` must be green
(task 01 "Done when").

**Verified by me:** _TODO_

---

## 2026-11-13 — Task 02: sample CSV generated with AI, then reduced

**What I did:** generated `data/sample_tickets.csv` (200 rows) and `data/sample_tickets_labels.csv`
with an AI tool.

**Review findings (Claude):**
- Labels were "intended" (what a human thinks), not "expected by the keyword rules".
  Checked with whole-word matching against `keywords/`: 29 rows differ
  (e.g. `T0004` "Search results are empty" → no keyword → Other; follow-up "Any update on this?" →
  `update` is a Technical keyword → Technical).
- No separate status column: duplicates were labeled as a category, "skipped" only in a note.
- 200 rows is too many to explain at the demo; the task asks for ~15–20.

**My decision:** reduce to ~20 rows, one row per test case, and write the expected result myself.

**Then:** to save time, Claude cut the CSV to 19 rows (one per test case, chosen from the 200)
and created an empty labels file (`row, ticket_id, status, categories, note`).
I fill `status` and `categories` myself, using the rules in `keywords/`.

**Verified by me:** _TODO_

---

## 2026-11-13 — Task 03: `read_csv` + first `validation` loop (in progress)

**What I wrote:** `read_csv(file_path)` (extension / exists / empty checks, `utf-8-sig`, `DictReader`,
header check) and a first `validation(rows)` loop that strips values and prints them with row numbers.

**Review findings (Claude):**
- Missing `import os` → `NameError`; no `encoding=` → Windows default codepage, BOM stays in `'\ufeffticket_id'`.
- Header was compared as a whole string (`readlines() == "ticket_id,message\n"`): list vs string is always
  `False`, and any space / column order / extra column breaks it → use `'ticket_id' in reader.fieldnames`.
- `TabError`: tabs and spaces mixed → converted `reader.py` to 4 spaces (PEP 8).
- `enumerate` returns `(index, item)` pairs → must unpack: `for row_number, row in enumerate(...)`.
- Row number: the header is line 1 and `DictReader` consumes it → `start=2` (matches Excel and my labels file).
- Checked on test files: header only → `[]`; wrong columns → `Missing column: ticket_id`;
  reordered + extra column → OK; BOM file → OK.

**Small fixes applied by Claude (I was short on time):** renamed `objects` → `row`; wrapped the manual
check call in `if __name__ == "__main__":` (code at module level runs on every `import`, so the output was
printed twice); absolute path → `data/sample_tickets.csv`. Run it with `python -m ticket_organizer.reader`.

**Still to do (me):** split rows into valid / rejected with row number + reason; handle `None` values;
duplicates; tests. Also convert tabs → spaces in `storage.py`.

**Verified by me:** _TODO_

---

## 2026-11-14 — Task 03: `validation` splits rows into valid / rejected

**What Claude wrote:** `validation(rows)` now returns `(valid, rejected)` — two lists of dicts
`{"row", "ticket_id", "message"}`; rejected ones also have `"reason"` (`empty ticket_id` / `empty message`).
`None` (row shorter than the header) is treated as empty. Tests: `tests/test_reader.py` (6 tests).

**Problems on the way:** `pytest` not found → venv not activated (`.venv\Scripts\Activate.ps1`).
Then `ModuleNotFoundError: ticket_organizer` → plain `pytest` puts `tests/` on `sys.path`, not the project
root → Claude added `pytest.ini` with `pythonpath = .`. Result: 6 passed.
Manual run on `data/sample_tickets.csv`: 15 valid + 4 rejected = 19 rows; rows 10–13 checked against the file.

**Change made by me:** added reason `empty ticket_id and message` + test (7 passed). First I put the check
as the last `elif` → it never ran (in `if/elif` only the first true branch runs) → moved it to the top.

**Verified by me:** _TODO_

---

## 2026-11-14 — Task 03: duplicates inside the file

**What Claude wrote:** `remove_duplicates(valid)` in `reader.py` → returns `(unique, skipped)`.
Duplicate = same `ticket_id` **and** same `message` after strip (decision 3). Skipped records get
`"reason": "duplicate of row N"` (N = row where it was first seen). Uses a dict `(ticket_id, message) → row`
as the "seen" set. Kept as a separate function, so `validation` and its tests did not change.
4 new tests: exact duplicate, duplicate after strip, same id + other message (follow-up → kept),
same message + other id (kept).

**Checked:** `python -m ticket_organizer.reader` → read 19 = accepted 14 + rejected 4 + skipped 1;
row 14 skipped as duplicate of row 8, row 15 (T0026 follow-up) accepted — matches `sample_tickets_labels.csv`.
11 tests pass (run without pytest on Linux — pytest was not installed there).

**Open question for me:** is the comparison case-sensitive on purpose? `"Hello"` vs `"hello"` is now *not* a duplicate.

**Verified by me:** _TODO_

---

## 2026-11-14 — Task 04: `categorizer.py`

**What Claude wrote:** `load_rules()` reads `keywords/<category>.txt` (file name = category,
`#` comments and empty lines skipped) → `compile_rules()` builds one case-insensitive regex per category →
`categorize(message)` returns all matching categories, no match → `["Other"]`.
11 tests in `tests/test_categorizer.py`.

**Decisions (to explain at the demo):**
- **Whole word, not substring:** `"charge" in text` would match `discharge` → wrong Billing.
  Regex `(?<!\w)keyword(?!\w)` (like `\b`, but also safe for keywords starting/ending with a non-letter).
- **Word forms:** no stemming — `charged`, `charges`, typos are listed in the keyword files.
- **Stable order:** categories sorted by file name → `["Account", "Billing"]`, not the order of words in the text.
  Tests compare lists, so a random order would make them flaky.

**Checked:** `python -m ticket_organizer.categorizer` on `data/sample_tickets.csv` → all categories match
`sample_tickets_labels.csv`. Only difference: row 7 is `Account|Billing` here vs `Billing|Account` in the labels
(order only) → I should update the labels file. pytest: 23 passed.

**Known effect:** `"Any update? I still cannot log in."` → `Account, Technical` (`update` is a Technical keyword).
Follows the rules, but worth mentioning.

**Verified by me:** _TODO_

---

## 2026-11-14 — Task 05: `storage.py` — saving messages

**What Claude wrote:** `save_messages(conn, records)` → `(saved, skipped)`; `count_per_category(conn)`;
`count_messages(conn)`. `db_creator` unchanged except tabs → 4 spaces. 9 tests in `tests/test_storage.py`
(in-memory DB).

**Decisions (to explain at the demo):**
- **Skipped once per message:** `SELECT 1 ... WHERE ticket_id = ? AND message = ?` before inserting.
  If found → the whole message is skipped and reported once (`"already in database"`), even with 2 categories.
  Chosen over `INSERT OR IGNORE` + `rowcount`: there a 2-category message gives 2 ignored inserts that would
  have to be merged back into one "skipped".
- **One row per category:** `executemany` with one `(ticket_id, message, category)` per category.
- **Transaction:** the whole `save_messages` call runs in `with conn:` → commit at the end, rollback on error.
  No half-saved message and no half-saved file; after a crash simply run again (idempotent).
- **Count messages, not rows:** SQLite has no `COUNT(DISTINCT a, b)` → `SELECT COUNT(*) FROM (SELECT DISTINCT ticket_id, message ...)`.
- **`?` placeholders only:** an f-string would put user text into the SQL itself (SQL injection).
  Test stores `x'); DROP TABLE messages; --` as plain text.

**Checked:** `python -m ticket_organizer.storage` twice on a fresh `output/tickets.db`:
run 1 → saved 14; run 2 → saved 0, already in DB 14; DB content the same (14 messages,
Account 4, Billing 4, Other 4, Technical 3 — sum 15 > 14 because T0147 has 2 categories). pytest: 32 passed.

**Verified by me:** _TODO_

---

## 2026-11-14 — Task 06: `summary.py`

**What Claude wrote:** `build_summary(...)` → dict, `format_summary` (terminal text), `save_summary_json`,
`save_rejected_csv` (`row, ticket_id, message, reason`, `utf-8-sig` for Excel). 7 tests in `tests/test_summary.py`.
README: new "Summary" section.

**Decisions (to explain at the demo):**
- **Categories: this run or whole DB?** Both. "This run" alone shows all zeros on a re-run;
  "whole DB" alone does not show what this file added.
- **Invariant checked in code:** `build_summary` raises `ValueError` if
  `rows_read != accepted + rejected + skipped` — a counting bug cannot silently produce a wrong report.
- **JSON** for the summary file: easy to test (`json.loads(...) == summary`).

**Checked:** `python -m ticket_organizer.summary` twice on a fresh DB:
run 1 → 19 = 14 + 4 + 1 (matches `sample_tickets_labels.csv`); run 2 → 19 = 0 + 4 + 15
(duplicate in file 1, already in DB 14). `output/rejected.csv` has rows 10–13. pytest: 39 passed.

**Verified by me:** _TODO_
