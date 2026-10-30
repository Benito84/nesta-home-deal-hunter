import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'deals.db')
if not os.path.exists(DB_PATH):
    # Try current directory or parent
    DB_PATH = 'data/deals.db'

print(f"Connecting to database at {DB_PATH}...")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Update scraper_sources
c.execute("""
    UPDATE scraper_sources 
    SET is_active = 0, status = 'DISABLED', notes = 'Wyłączone: Program "Mieszkanie za remont" dotyczy najmu komunalnego, brak możliwości zakupu/flipa.' 
    WHERE code = 'zbilk'
""")
print(f"Disabled 'zbilk' in scraper_sources.")

# 2. Identify bogus IDs
bogus_ids = set()

# Spółdzielnie tenders and garages
c.execute("SELECT id FROM listings WHERE source = 'spoldzielnie'")
bogus_ids.update(r[0] for r in c.fetchall())

# ZBiLK municipal rental flats
c.execute("SELECT id FROM listings WHERE source = 'zbilk'")
bogus_ids.update(r[0] for r in c.fetchall())

# E-licytacje anomalies (commercial, land, shares 1/2, personal servitude, Szczecinek)
elicytacje_bogus = [47, 48, 50, 51, 53, 55, 56, 57, 59]
bogus_ids.update(elicytacje_bogus)

# Infoludek out of town (Police)
infoludek_bogus = [31, 32]
bogus_ids.update(infoludek_bogus)

# Lento (syndyk 1/2 share)
lento_bogus = [144]
bogus_ids.update(lento_bogus)

print(f"Found {len(bogus_ids)} bogus listing IDs to purge.")

# Delete bogus listings
placeholders = ','.join('?' for _ in bogus_ids)
c.execute(f"DELETE FROM listings WHERE id IN ({placeholders})", list(bogus_ids))
deleted_count = c.rowcount
conn.commit()

print(f"Successfully deleted {deleted_count} bogus records from listings.")

# Verification
c.execute("SELECT COUNT(*) FROM listings")
total_remaining = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM listings WHERE is_active = 1 AND gate_1_decision = 'DO POCZEKALNI'")
active_deals = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM listings WHERE is_active = 1 AND gate_1_decision != 'DO POCZEKALNI'")
stopped = c.fetchone()[0]

print(f"\nAudit after purge:")
print(f"  Total listings in database: {total_remaining}")
print(f"  Active 'DO POCZEKALNI' deals: {active_deals}")
print(f"  Active 'STOP' / archived: {stopped}")

c.execute("SELECT source, COUNT(*) FROM listings GROUP BY source")
print("\nListings breakdown by source:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()
print("\nDone!")
