import sqlite3

def check_local_db():
    for path in ['.\\backend\\news_cache.db', '.\\news_cache.db']:
        try:
            conn = sqlite3.connect(path)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in c.fetchall()]
            if tables:
                print(f"Database: {path}")
                for t in tables:
                    try:
                        c.execute(f"SELECT count(*) FROM {t}")
                        print(f"  Table {t}: {c.fetchone()[0]} rows")
                    except Exception as ex:
                        print(f"  Table {t} error: {ex}")
            conn.close()
        except Exception as e:
            print(f"Could not read {path}: {e}")

if __name__ == '__main__':
    check_local_db()
