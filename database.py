import sqlite3

db = 'tsg_database.sql'


def create_table(table_name, table_columns):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    columns_str = ", ".join(table_columns)

    cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                {columns_str}
            )
        """)

    conn.commit()
    cur.close()
    conn.close()


def insert_to_database(tablename, columns, values):
    if len(columns) != len(values):
        raise ValueError("Количество колонок и значений должно совпадать")

    columns_str = ", ".join(columns)
    placeholders = ", ".join(["?"] * len(values))

    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute(f"""
            INSERT INTO {tablename} ({columns_str}) 
            VALUES ({placeholders})
            """, values)
    conn.commit()
    cur.close()
    conn.close()



def find_user_by_id(table_name, user_id, parameter):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute(f"SELECT {parameter} FROM {table_name} WHERE telegram_id = ?", (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result


def select_all(tablename):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {tablename}")
    result = cur.fetchall()
    conn.commit()
    cur.close()
    conn.close()
    return result
