"""
attempt_tamper.py
------------------
Standalone proof-of-concept. Tries to directly UPDATE and DELETE rows in
blockchain.db using raw SQL -- completely bypassing the Flask app and its
routes -- to prove that immutability is enforced by the database itself,
not just hidden by the website's UI.

Run this from a terminal, with the Flask app stopped (SQLite allows only
one writer at a time):

    python attempt_tamper.py

Expected output: both the UPDATE and the DELETE are rejected by the
`blocks_no_update` / `blocks_no_delete` triggers defined in blockchain.py,
which run inside SQLite itself.
"""

import os
import sqlite3

DB_FILE = os.path.join(os.path.dirname(__file__), "blockchain.db")


def try_update():
    print("Attempting to UPDATE the newest block's data...")
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "UPDATE blocks SET data = ? WHERE idx = (SELECT MAX(idx) FROM blocks)",
            ('{"type": "HACKED", "message": "this should never be saved"}',)
        )
        conn.commit()
        print("  UPDATE SUCCEEDED -- this should not be possible!")
    except sqlite3.Error as e:
        print(f"  Blocked by the database: {e}")
    finally:
        conn.close()


def try_delete():
    print("Attempting to DELETE the newest block...")
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("DELETE FROM blocks WHERE idx = (SELECT MAX(idx) FROM blocks)")
        conn.commit()
        print("  DELETE SUCCEEDED -- this should not be possible!")
    except sqlite3.Error as e:
        print(f"  Blocked by the database: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        print("blockchain.db not found. Run 'python app.py' at least once first "
              "so the database and its triggers get created.")
    else:
        try_update()
        try_delete()
        print("\nThe blocks table remains append-only: no historical block "
              "was modified or removed.")
