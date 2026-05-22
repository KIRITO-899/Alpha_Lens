import sys
import os

# Add backend directory to path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

class MockCursor:
    def __init__(self):
        self.last_sql = None
        self.last_params = None
        self.rowcount = 0
        self.description = []

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params
        return self

    def fetchone(self):
        # Mock fetching returned id if query ends with RETURNING id
        if self.last_sql and 'RETURNING id' in self.last_sql:
            return (42,)
        return None

    def fetchall(self):
        return []

    def close(self):
        pass


def test_translator():
    from app import CursorWrapper
    
    mock_inner_cursor = MockCursor()
    wrapper = CursorWrapper(mock_inner_cursor, is_postgres=True)
    
    # 1. Test placeholder replacement
    wrapper.execute("SELECT * FROM news WHERE id = ? AND category = ?", (1, 'General'))
    assert mock_inner_cursor.last_sql == "SELECT * FROM news WHERE id = %s AND category = %s"
    assert mock_inner_cursor.last_params == (1, 'General')
    print("[PASS] Placeholder replacement works.")

    # 2. Test AUTOINCREMENT replacement
    wrapper.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT)")
    assert mock_inner_cursor.last_sql == "CREATE TABLE users (id SERIAL PRIMARY KEY, email TEXT)"
    print("[PASS] AUTOINCREMENT replacement works.")

    # 3. Test INSERT OR IGNORE translation
    wrapper.execute("INSERT OR IGNORE INTO news (headline, category) VALUES (?, ?)", ('Tesla falls', 'Tech'))
    # Wait, it should translate to "INSERT INTO news (headline, category) VALUES (%s, %s) ON CONFLICT DO NOTHING"
    # And since it's an insert without RETURNING and not STOCK_UNIVERSE, it also appends RETURNING id!
    # So: "INSERT INTO news (headline, category) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id"
    expected = "INSERT INTO news (headline, category) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id"
    assert mock_inner_cursor.last_sql == expected
    # Since it fetched, lastrowid should be 42
    assert wrapper.lastrowid == 42
    print("[PASS] INSERT OR IGNORE and RETURNING id translation works.")

    # 4. Test dropping of PRAGMA
    mock_inner_cursor.last_sql = None
    wrapper.execute("PRAGMA journal_mode=WAL;")
    assert mock_inner_cursor.last_sql is None
    print("[PASS] PRAGMA commands are correctly dropped.")

    # 5. Test stock_universe exclusion from RETURNING id
    wrapper.execute("INSERT OR IGNORE INTO stock_universe (ticker, symbol) VALUES (?, ?)", ('AAPL', 'AAPL'))
    expected_universe = "INSERT INTO stock_universe (ticker, symbol) VALUES (%s, %s) ON CONFLICT DO NOTHING"
    assert mock_inner_cursor.last_sql == expected_universe
    print("[PASS] stock_universe is correctly excluded from RETURNING id.")

    print("\nALL POSTGRESQL TRANSLATION LAYER TESTS PASSED!")

if __name__ == '__main__':
    test_translator()
