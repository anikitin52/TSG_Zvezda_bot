import pandas as pd
import sqlite3

def send_exel_file():
    conn = sqlite3.connect('meter_data.sql')
    df = pd.read_sql_query("SELECT * FROM meters_data", conn)
    df.to_excel("meter_data.xlsx", index=False)
    conn.close()

