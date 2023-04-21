import sqlite3


class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name

    def init_database(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute(
            "CREATE TABLE IF NOT EXISTS papers (entry_id TEXT PRIMARY KEY, timestamp DATETIME)"
        )
        conn.commit()
        conn.close()

    def add_paper(self, entry_id):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO papers (entry_id, timestamp) VALUES (?, datetime('now'))",
            (entry_id,),
        )
        conn.commit()
        conn.close()

    def get_excluded_papers(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT entry_id FROM papers")
        exclude_ids = [row[0] for row in c.fetchall()]
        conn.close()
        return exclude_ids
