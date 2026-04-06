import sqlite3
import json
from datetime import datetime

def connect_news_db():
    conn = sqlite3.connect('news_cache.db', timeout=20.0)
    conn.row_factory = sqlite3.Row
    return conn

def run_performance_check():
    """
    Analyzes the 'stock_impact' table to report prediction accuracy.
    """
    print("\n" + "="*50)
    print(" 📊 ALPHA LENS: STRATEGY PERFORMANCE REPORT")
    print("="*50)

    try:
        conn = connect_news_db()
        c = conn.cursor()

        # Get Total News Articles
        c.execute("SELECT COUNT(*) FROM news")
        total_news = c.fetchone()[0]

        # Get Counts by Status
        c.execute("""
            SELECT status, COUNT(*) as count 
            FROM stock_impact 
            GROUP BY status
        """)
        status_counts = {row['status']: row['count'] for row in c.fetchall()}

        hits = status_counts.get('Predicted Target Hit', 0)
        misses = status_counts.get('Reacted Against Prediction', 0)
        active = status_counts.get('Active View', 0)
        total_calls = hits + misses + active

        # Win Rate calculation (only on closed trades)
        closed_trades = hits + misses
        win_rate = 0
        if closed_trades > 0:
            win_rate = round((hits / closed_trades) * 100, 2)

        # Print the Report
        print(f"Total News Articles Analyzed:  {total_news}")
        print(f"Total Stock Calls Triggered:   {total_calls}")
        print("-" * 50)
        
        # Color coding in terminal (standard ANSI)
        GREEN = "\033[92m"
        RED = "\033[91m"
        CYAN = "\033[96m"
        RESET = "\033[0m"
        BOLD = "\033[1m"

        print(f"{GREEN}✅ TARGET HIT (Wins):             {hits}{RESET}")
        print(f"{RED}❌ REACTED AGAINST (Losses):     {misses}{RESET}")
        print(f"{CYAN}⏳ STILL RUNNING (Active):       {active}{RESET}")
        print("-" * 50)
        
        # Performance indicator
        if win_rate >= 70:
            rating = f"{GREEN}🔥 ELITE{RESET}"
        elif win_rate >= 50:
            rating = f"{CYAN}📈 DECENT{RESET}"
        else:
            rating = f"{RED}⚠️ VOLATILE{RESET}"

        print(f"{BOLD}🏆 AI STRATEGY WIN RATE:          {win_rate}%  ({rating}){RESET}")
        print("="*50 + "\n")

        conn.close()
    except Exception as e:
        print(f"❌ Error during performance check: {e}")

if __name__ == "__main__":
    run_performance_check()
