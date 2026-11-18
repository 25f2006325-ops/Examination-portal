import sqlite3
import sys

DB_PATH = 'instance/emp.db'

def view_database(target_table=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    # Get all user tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]

    if not tables:
        print(f"No tables found in {DB_PATH}.")
        return

    if target_table:
        if target_table not in tables:
            print(f"Table '{target_table}' not found. Available tables: {', '.join(tables)}")
            return
        tables = [target_table]

    print(f"\n📁 SQLite Database: {DB_PATH}")
    print(f"📋 Tables found ({len(tables)}): {', '.join(tables)}\n")

    for table in tables:
        print("=" * 70)
        print(f" TABLE: {table.upper()}")
        print("=" * 70)

        # Get column information
        cursor.execute(f"PRAGMA table_info({table})")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]

        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()

        if not rows:
            print(f"Columns: {' | '.join(column_names)}")
            print("  (Empty table - 0 records)")
        else:
            # Print column headers
            header = " | ".join(column_names)
            print(header)
            print("-" * min(len(header) + 10, 100))

            # Print each row
            for row in rows:
                row_str = " | ".join(str(val) if val is not None else "NULL" for val in row)
                print(row_str)
            print(f"\nTotal: {len(rows)} record(s)")

        print()

    conn.close()

if __name__ == '__main__':
    selected = sys.argv[1] if len(sys.argv) > 1 else None
    view_database(selected)
