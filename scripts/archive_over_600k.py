import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('data/deals.db')
c = conn.cursor()
c.execute('SELECT id, title, price_pln, status FROM listings WHERE price_pln > 600000')
print('Found:', c.fetchall())
c.execute("""
    UPDATE listings 
    SET status = 'REJECTED', 
        is_active = 0,
        gate_1_decision = 'REJECTED'
    WHERE price_pln > 600000
""")
conn.commit()
print('Archived/Rejected count:', c.rowcount)
conn.close()
