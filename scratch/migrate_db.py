import sqlite3
import psycopg2
import sys

# Remote Postgres Connection String
PG_URL = "postgresql://alphalens_40cn_user:X84HBncPa1FjZo7kLMlxHBEp2CLhaDpn@dpg-d88cl2cm0tmc738kku90.oregon-postgres.render.com/alphalens_40cn?sslmode=require"
# Local SQLite Path
SQLITE_PATH = "backend/news_cache.db"

def migrate():
    print("Connecting to databases...")
    try:
        sqlite_conn = sqlite3.connect(SQLITE_PATH)
        sqlite_cur = sqlite_conn.cursor()
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        return

    try:
        pg_conn = psycopg2.connect(PG_URL)
        pg_cur = pg_conn.cursor()
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sqlite_conn.close()
        return

    print("Connected successfully! Starting migration...")

    # 1. Migrate stock_universe
    print("\nMigrating table 'stock_universe'...")
    sqlite_cur.execute("SELECT ticker, symbol, name, exchange, source, updated_at FROM stock_universe")
    rows = sqlite_cur.fetchall()
    print(f"  Found {len(rows)} stock universe entries in SQLite.")
    
    pg_cur.executemany("""
        INSERT INTO stock_universe (ticker, symbol, name, exchange, source, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker) DO NOTHING
    """, rows)
    pg_conn.commit()
    print("  Stock universe migrated successfully.")

    # 2. Migrate news
    print("\nMigrating table 'news'...")
    # Get columns of news to make sure we select correctly
    sqlite_cur.execute("PRAGMA table_info(news)")
    news_cols = [r[1] for r in sqlite_cur.fetchall()]
    print(f"  News columns in SQLite: {news_cols}")
    
    # We want: id, headline, source, url, summary, sentiment, category, created_at, text_content, audio_path
    sqlite_cur.execute("SELECT id, headline, source, url, summary, sentiment, category, created_at, text_content, audio_path FROM news")
    news_rows = sqlite_cur.fetchall()
    print(f"  Found {len(news_rows)} news entries in SQLite.")
    
    pg_cur.executemany("""
        INSERT INTO news (id, headline, source, url, summary, sentiment, category, created_at, text_content, audio_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, news_rows)
    pg_conn.commit()
    print("  News migrated successfully.")

    # 3. Migrate stock_impact
    print("\nMigrating table 'stock_impact'...")
    sqlite_cur.execute("""
        SELECT id, news_id, ticker, impact_type, reasoning, change_pct, confidence_score, technical_context, ensemble_detail, created_at 
        FROM stock_impact
    """)
    impact_rows = sqlite_cur.fetchall()
    print(f"  Found {len(impact_rows)} stock impact entries in SQLite.")
    
    pg_cur.executemany("""
        INSERT INTO stock_impact (id, news_id, ticker, impact_type, reasoning, change_pct, confidence_score, technical_context, ensemble_detail, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, impact_rows)
    pg_conn.commit()
    print("  Stock impact migrated successfully.")

    # 4. Migrate historical_patterns
    print("\nMigrating table 'historical_patterns'...")
    sqlite_cur.execute("SELECT id, headline, ticker, direction, outcome, change_pct, created_at FROM historical_patterns")
    pattern_rows = sqlite_cur.fetchall()
    print(f"  Found {len(pattern_rows)} historical pattern entries in SQLite.")
    
    pg_cur.executemany("""
        INSERT INTO historical_patterns (id, headline, ticker, direction, outcome, change_pct, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """, pattern_rows)
    pg_conn.commit()
    print("  Historical patterns migrated successfully.")

    # Adjust auto-increment sequence in PostgreSQL for serial keys
    print("\nSyncing auto-increment primary key sequences...")
    for seq_table in ['news', 'stock_impact', 'historical_patterns']:
        try:
            pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{seq_table}', 'id'), COALESCE(MAX(id), 1) + 1) FROM {seq_table}")
            pg_conn.commit()
            print(f"  Synced sequence for {seq_table}.")
        except Exception as ex:
            pg_conn.rollback()
            print(f"  Could not sync sequence for {seq_table}: {ex}")

    sqlite_conn.close()
    pg_conn.close()
    print("\n🎉 Migration completed successfully!")

if __name__ == '__main__':
    migrate()
