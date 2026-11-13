import sqlite3
from pathlib import Path

def db_creator(db_path):
	Path(db_path).parent.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(db_path)
	conn.execute("CREATE TABLE IF NOT EXISTS messages (ticket_id TEXT, message TEXT, category TEXT, UNIQUE(ticket_id, message, category))")
	conn.commit()
	return conn
