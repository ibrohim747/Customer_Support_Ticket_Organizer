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
    for row_number, row in enumerate(rows, start=2):
        ticket_id = row['ticket_id'].strip()
        message = row['message'].strip()
        print(f"Row {row_number}: ticket_id = {ticket_id}, message = {message}")
    return rows


if __name__ == "__main__":
    res = read_csv("data/sample_tickets.csv")
    validation(res)