import pandas as pd
import sqlite3
from datetime import datetime

def create_exel_file():
    now = datetime.now()
    current_month = f"{now.month}.{now.year}"
    conn = sqlite3.connect('meter_data.sql')
    df = pd.read_sql_query("SELECT * FROM meters_data", conn)
    df.to_excel(f"Показания счетчиков {current_month}.xlsx", index=False)
    conn.close()

