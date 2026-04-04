import sqlite3

def view_all_users():
    print("\n" + "="*40)
    print("   ALPHA LENS: REGISTERED USERS")
    print("="*40)
    
    try:
        # Connect to your SQLite database
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        
        # Select all users, but don't select the passwords!
        c.execute("SELECT id, email FROM users")
        users = c.fetchall()
        
        if not users:
            print("No users found in the database.")
        else:
            for user in users:
                user_id = user[0]
                email = user[1]
                print(f"ID: {user_id} | Email: {email}")
                
        conn.close()
    except Exception as e:
        print(f"Error reading database: {e}")
        
    print("="*40 + "\n")

if __name__ == "__main__":
    view_all_users()
