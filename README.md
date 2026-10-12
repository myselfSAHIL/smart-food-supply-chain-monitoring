# Smart Food Supply Chain Monitoring — Course Project

A simple, working demo of blockchain-based food supply chain traceability,
built for BCSE209L (Blockchain and Distributed Ledger Technology).

It implements the core ideas from the project presentation:

- An immutable, hash-linked blockchain (`blockchain.py`) with proof-of-work
  style mining, stored in a **SQLite database that is append-only by
  design** — registered data can never be edited or deleted (see
  [Immutability](#immutability-how-its-enforced) below)
- "Smart contract" style functions: `registerProduct`, `transferOwnership`,
  `validateConditions`, `triggerAlert`, `verifyProvenance`
- IoT sensor data simulation (temperature/humidity readings) that
  auto-triggers on-chain alerts when safe thresholds are exceeded
- Role-based event logging across supply-chain stages (Processing,
  Packaging, Transportation, Storage, Retail)
- A QR code per product batch for consumer-facing provenance verification
- A blockchain explorer page showing every block and its hash chain

## Project structure

```
foodchain-project/
├── app.py                 # Flask app / website routes
├── blockchain.py          # The blockchain itself (this is the "Python code")
├── attempt_tamper.py       # Standalone script that proves the DB rejects edits
├── requirements.txt
├── templates/              # HTML pages
│   ├── base.html
│   ├── index.html            # Producer/stakeholder dashboard
│   ├── product_detail.html   # Manage a batch: add events, sensor data, transfer, QR
│   ├── verify.html           # Public consumer verification page (QR target)
│   └── chain.html            # Blockchain explorer
└── static/
    └── style.css
```

`blockchain.db` is created automatically the first time you run the app.

## Setup

```bash
cd foodchain-project
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

## How to demo it

1. **Register a product** on the Dashboard (producer, product name, origin).
   This mines a `REGISTER_PRODUCT` block.
2. Click **Manage** on the batch to open its detail page.
3. **Add a supply chain event** (stage, location, handler, role) — mines a
   `SUPPLY_CHAIN_EVENT` block.
4. **Submit an IoT sensor reading.** Try a normal value (e.g. 4°C, 55%
   humidity) — recorded, no alert. Try an out-of-range value (e.g. 15°C) —
   a `SENSOR_READING` block **and** an automatic `ALERT` block are mined.
5. **Transfer ownership** to simulate custody changing hands (producer →
   transporter → retailer).
6. See the full **on-chain history** for the batch, and the **QR code** a
   consumer would scan.
7. Open the QR link to see the read-only **consumer verification page**.
8. Go to **Blockchain Explorer** to see every block: its hash, previous-hash
   link, and nonce.

## Immutability: how it's enforced

Registered data can never be adjusted or deleted, for two independent reasons:

1. **Database-level enforcement.** The `blocks` table in `blockchain.db`
   has two SQL triggers, `blocks_no_update` and `blocks_no_delete`
   (defined in `blockchain.py`), that reject any `UPDATE` or `DELETE` on
   that table — no matter who issues it. This isn't just missing buttons
   in the UI; it's the database engine itself refusing the operation. The
   only write path exposed by the code is `add_block()`, which always
   `INSERT`s a new row.

2. **Hash chaining.** Every block stores the SHA-256 hash of the block
   before it. If someone bypassed the triggers entirely (e.g. by editing
   the raw `.db` file with a hex editor), the edited block's hash would no
   longer match its contents, and `is_chain_valid()` (shown on the
   Blockchain Explorer page) would immediately flag it.

**To see this proven directly:** stop the Flask app and run:

```bash
python attempt_tamper.py
```

This script connects straight to `blockchain.db` with raw SQL — no Flask,
no app code — and tries to `UPDATE` and `DELETE` the newest block. Both
attempts are rejected by the database itself, and it prints the exact
error each time.

## Notes on scope (kept intentionally simple)

This is a single-node blockchain (no peer-to-peer network) with a low
proof-of-work difficulty, running on one local SQLite database rather than
data replicated across many independent nodes the way a production
blockchain would be. Digital signatures, permissioned access control, and
off-chain cloud storage are represented conceptually (actor role fields,
hash-only anchoring pattern) rather than fully implemented, since the goal
is to clearly demonstrate the blockchain concepts for a course project.

Good directions to extend further (see "Future Scope" in the slides): real
public/private key signatures per stakeholder, a proper multi-node network,
and AI-based spoilage prediction from the sensor history.
