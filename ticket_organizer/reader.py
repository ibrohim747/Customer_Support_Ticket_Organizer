import os
import csv

def read_csv(file_path):
    if not file_path.endswith('.csv'):
        raise ValueError("The file must be a CSV file.")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file {file_path} does not exist.")
    if os.path.getsize(file_path) == 0:
        raise ValueError("The file is empty.")

    with open(file_path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if "ticket_id" not in reader.fieldnames:
            raise ValueError("Missing column: ticket_id")
        if "message" not in reader.fieldnames:
            raise ValueError("Missing column: message")
        return list(reader)


def validation(rows):
    valid = []
    rejected = []
    # Line 1 of the file is the header, so the first data row is line 2.
    for row_number, row in enumerate(rows, start=2):
        # A short row gives None instead of "" -> "or ''" turns it into "".
        ticket_id = (row["ticket_id"] or "").strip()
        message = (row["message"] or "").strip()

        if ticket_id == "" and message == "":
            reason = "empty ticket_id and message"
        elif ticket_id == "":
            reason = "empty ticket_id"
        elif message == "":
            reason = "empty message"
        else:
            reason = None

        record = {"row": row_number, "ticket_id": ticket_id, "message": message}
        if reason is None:
            valid.append(record)
        else:
            record["reason"] = reason
            rejected.append(record)
    return valid, rejected


if __name__ == "__main__":
    res = read_csv("data/sample_tickets.csv")
    valid, rejected = validation(res)
    print(f"valid: {len(valid)}, rejected: {len(rejected)}")
    for record in rejected:
        print(record)