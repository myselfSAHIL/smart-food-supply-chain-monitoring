"""
blockchain.py
--------------
A simple, educational blockchain implementation for the
Smart Food Supply Chain Monitoring course project (BCSE209L).

Storage: SQLite (blockchain.db). The `blocks` table is APPEND-ONLY --
two database triggers (blocks_no_update, blocks_no_delete) make UPDATE
and DELETE on that table fail at the database engine level, no matter
who or what tries it (the Flask app, a Python shell, or raw SQL from
the sqlite3 command line). See attempt_tamper.py for a standalone proof.

On top of that database-level guarantee, the usual blockchain
hash-chaining is still used (SHA-256, proof-of-work mining, and
is_chain_valid()) as a second, independent line of defense: even if
someone bypassed the triggers by editing the .db file with a raw disk
editor, recomputing the hashes would reveal the change.

"Smart contract" style functions, matching the ones from the project's
system architecture slide:
    registerProduct()
    transferOwnership()
    validateConditions()
    triggerAlert()
    verifyProvenance()
"""

import hashlib
import json
import time
import os
import sqlite3
import uuid

DB_FILE = os.path.join(os.path.dirname(__file__), "blockchain.db")
DIFFICULTY = 3  # number of leading zeros required in a valid block hash

# Safe environmental thresholds used by validateConditions() (cold-chain demo)
SAFE_TEMP_MIN = 0.0
SAFE_TEMP_MAX = 8.0
SAFE_HUMIDITY_MIN = 30.0
SAFE_HUMIDITY_MAX = 70.0


class Block:
    def __init__(self, index, timestamp, data, previous_hash, nonce=0, hash_=None):
        self.index = index
        self.timestamp = timestamp
        self.data = data                    # dict describing the event
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash_ or self.compute_hash()

    def compute_hash(self):
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True)
        return hashlib.sha256(block_string.encode()).hexdigest()

    def mine(self, difficulty=DIFFICULTY):
        """Very small proof-of-work: find a nonce whose hash starts with N zeros."""
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()
        return self.hash

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }


class Blockchain:
    def __init__(self):
        self._init_db()
        self._ensure_genesis()

    # ---------------- database setup ----------------
    def _connect(self):
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self):
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS blocks (
                idx           INTEGER PRIMARY KEY,
                timestamp     REAL    NOT NULL,
                data          TEXT    NOT NULL,
                previous_hash TEXT    NOT NULL,
                nonce         INTEGER NOT NULL,
                hash          TEXT    NOT NULL UNIQUE
            );

            -- These two triggers are what make the ledger append-only:
            -- no UPDATE or DELETE on `blocks` can ever succeed, from any
            -- caller, including direct SQL. This is enforced by SQLite
            -- itself, not by application code.
            CREATE TRIGGER IF NOT EXISTS blocks_no_update
            BEFORE UPDATE ON blocks
            BEGIN
                SELECT RAISE(ABORT, 'Blockchain violation: blocks table is append-only, UPDATE is not permitted');
            END;

            CREATE TRIGGER IF NOT EXISTS blocks_no_delete
            BEFORE DELETE ON blocks
            BEGIN
                SELECT RAISE(ABORT, 'Blockchain violation: blocks table is append-only, DELETE is not permitted');
            END;
        """)
        conn.commit()
        conn.close()

    def _ensure_genesis(self):
        conn = self._connect()
        count = conn.execute("SELECT COUNT(*) AS c FROM blocks").fetchone()["c"]
        conn.close()
        if count == 0:
            genesis = Block(0, time.time(),
                             {"type": "GENESIS", "message": "Genesis Block - Smart Food Supply Chain"},
                             "0")
            genesis.mine()
            self._insert_block(genesis)

    def _insert_block(self, block):
        conn = self._connect()
        conn.execute(
            "INSERT INTO blocks (idx, timestamp, data, previous_hash, nonce, hash) VALUES (?, ?, ?, ?, ?, ?)",
            (block.index, block.timestamp, json.dumps(block.data),
             block.previous_hash, block.nonce, block.hash)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _row_to_block(row):
        return Block(row["idx"], row["timestamp"], json.loads(row["data"]),
                     row["previous_hash"], row["nonce"], row["hash"])

    # ---------------- core chain mechanics ----------------
    def get_all_blocks(self):
        conn = self._connect()
        rows = conn.execute("SELECT * FROM blocks ORDER BY idx ASC").fetchall()
        conn.close()
        return [self._row_to_block(r) for r in rows]

    def get_latest_block(self):
        conn = self._connect()
        row = conn.execute("SELECT * FROM blocks ORDER BY idx DESC LIMIT 1").fetchone()
        conn.close()
        return self._row_to_block(row)

    def add_block(self, data):
        """The ONLY way data ever enters the ledger: mine a new block and
        INSERT it. There is no update/delete path anywhere in this class."""
        latest = self.get_latest_block()
        new_block = Block(
            index=latest.index + 1,
            timestamp=time.time(),
            data=data,
            previous_hash=latest.hash
        )
        new_block.mine()
        self._insert_block(new_block)
        return new_block

    def is_chain_valid(self):
        """Walks the chain and checks hashes/links. This is the second,
        independent guarantee of immutability (on top of the DB triggers):
        changing any block's data changes its hash, which breaks the
        previous_hash link in the next block."""
        blocks = self.get_all_blocks()
        for i in range(1, len(blocks)):
            current = blocks[i]
            previous = blocks[i - 1]

            if current.hash != current.compute_hash():
                return False, f"Block {current.index} data has been tampered with."
            if current.previous_hash != previous.hash:
                return False, f"Block {current.index} is not correctly linked to block {previous.index}."
            if not current.hash.startswith("0" * DIFFICULTY):
                return False, f"Block {current.index} does not satisfy proof-of-work."
        return True, f"Blockchain is valid. All {len(blocks)} blocks are immutable and correctly linked."

    # ---------------- "smart contract" style functions ----------------
    def register_product(self, producer, product_name, origin):
        """registerProduct(batchID, producer) from the system architecture slide."""
        batch_id = "BATCH-" + uuid.uuid4().hex[:8].upper()
        data = {
            "type": "REGISTER_PRODUCT",
            "batch_id": batch_id,
            "producer": producer,
            "product_name": product_name,
            "origin": origin,
            "current_owner": producer
        }
        block = self.add_block(data)
        return batch_id, block

    def add_event(self, batch_id, stage, location, handler, actor_role):
        """Records a supply-chain event (processing, packaging, transport, ...)."""
        data = {
            "type": "SUPPLY_CHAIN_EVENT",
            "batch_id": batch_id,
            "stage": stage,
            "location": location,
            "handler": handler,
            "actor_role": actor_role
        }
        return self.add_block(data)

    def transfer_ownership(self, batch_id, new_owner, actor_role):
        """transferOwnership(batchID, newOwner)."""
        data = {
            "type": "TRANSFER_OWNERSHIP",
            "batch_id": batch_id,
            "new_owner": new_owner,
            "actor_role": actor_role
        }
        return self.add_block(data)

    @staticmethod
    def validate_conditions(temperature, humidity):
        """validateConditions(temp, humidity) -> list of violated rules."""
        violations = []
        if not (SAFE_TEMP_MIN <= temperature <= SAFE_TEMP_MAX):
            violations.append("TEMPERATURE_VIOLATION")
        if not (SAFE_HUMIDITY_MIN <= humidity <= SAFE_HUMIDITY_MAX):
            violations.append("HUMIDITY_VIOLATION")
        return violations

    def trigger_alert(self, batch_id, violation_type, details):
        """triggerAlert(violationType) -- written on-chain for auditability."""
        data = {
            "type": "ALERT",
            "batch_id": batch_id,
            "violation_type": violation_type,
            "details": details
        }
        return self.add_block(data)

    def record_sensor_reading(self, batch_id, temperature, humidity, location):
        """IoT sensor data ingestion: stores the reading on-chain, then runs
        validateConditions() and automatically fires triggerAlert() on violations."""
        data = {
            "type": "SENSOR_READING",
            "batch_id": batch_id,
            "temperature": temperature,
            "humidity": humidity,
            "location": location
        }
        block = self.add_block(data)

        violations = self.validate_conditions(temperature, humidity)
        alert_blocks = []
        for v in violations:
            details = f"temperature={temperature}C, humidity={humidity}%"
            alert_blocks.append(self.trigger_alert(batch_id, v, details))
        return block, violations, alert_blocks

    def verify_provenance(self, batch_id):
        """verifyProvenance(batchID) -> full ordered history for a batch."""
        return [b.to_dict() for b in self.get_all_blocks() if b.data.get("batch_id") == batch_id]

    def get_all_batches(self):
        batches = {}
        for block in self.get_all_blocks():
            if block.data.get("type") == "REGISTER_PRODUCT":
                batches[block.data["batch_id"]] = block.data
        return batches

    def get_recent_alerts(self, limit=5):
        alerts = [b.data for b in self.get_all_blocks() if b.data.get("type") == "ALERT"]
        return list(reversed(alerts))[:limit]
