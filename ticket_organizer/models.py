"""Data models (Pydantic): what a ticket, a rejected / skipped row and a summary look like.

The rules live here, in one place: Pydantic checks the data when an object is created.
Before (branch `main`) the same rules were `if` checks on plain dicts in reader.py / summary.py.
"""
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class Ticket(BaseModel):
    """A valid message from the CSV. Creating one checks it: both texts stripped and not empty."""

    # str_strip_whitespace: "  T1 " -> "T1" before the checks run.
    model_config = ConfigDict(str_strip_whitespace=True)

    row: int = Field(ge=2)  # line number in the file; line 1 is the header
    ticket_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    categories: list[str] = Field(default_factory=list)

    @field_validator("ticket_id", "message", mode="before")
    @classmethod
    def missing_value_is_empty(cls, value):
        # csv.DictReader gives None when a row has fewer columns than the header.
        return "" if value is None else value

    @property
    def key(self):
        """What makes two messages the same: same ticket_id AND same message."""
        return (self.ticket_id, self.message)


class RejectedRow(BaseModel):
    """A row that cannot be used, with its line number and the reason (for rejected.csv)."""

    row: int
    ticket_id: str
    message: str
    reason: str


class SkippedRow(RejectedRow):
    """A valid message that is not saved: duplicate in the file or already in the database."""


def parse_row(row_number, row):
    """One CSV row -> Ticket, or RejectedRow with the reason if Pydantic says it is invalid."""
    try:
        return Ticket(row=row_number, ticket_id=row.get("ticket_id"), message=row.get("message"))
    except ValidationError as error:
        # Which fields failed -> the same reasons as before: "empty ticket_id", "empty message", or both.
        failed = {e["loc"][0] for e in error.errors()}
        if failed >= {"ticket_id", "message"}:
            reason = "empty ticket_id and message"
        elif "ticket_id" in failed:
            reason = "empty ticket_id"
        else:
            reason = "empty message"
        return RejectedRow(
            row=row_number,
            ticket_id=(row.get("ticket_id") or "").strip(),
            message=(row.get("message") or "").strip(),
            reason=reason,
        )


class SkippedCounts(BaseModel):
    duplicate_in_file: int = Field(ge=0)
    already_in_db: int = Field(ge=0)
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def total_is_the_sum(self):
        if self.total != self.duplicate_in_file + self.already_in_db:
            raise ValueError("skipped.total must be duplicate_in_file + already_in_db")
        return self


class Summary(BaseModel):
    """The numbers of one run. The invariant is checked by the model itself."""

    rows_read: int = Field(ge=0)
    accepted: int = Field(ge=0)
    rejected: int = Field(ge=0)
    skipped: SkippedCounts
    # Can be bigger than "accepted": a message may have several categories.
    categories_this_run: dict[str, int]
    categories_in_db: dict[str, int]

    @model_validator(mode="after")
    def counts_add_up(self):
        if self.rows_read != self.accepted + self.rejected + self.skipped.total:
            raise ValueError(
                f"Counts do not add up: rows_read={self.rows_read}, accepted={self.accepted}, "
                f"rejected={self.rejected}, skipped={self.skipped.total}"
            )
        return self
