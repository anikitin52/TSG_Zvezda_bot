from telebot import TeleBot
import pandas as pd
import sqlite3
from datetime import datetime
import openpyxl

from config import BOT_TOKEN

bot = TeleBot(BOT_TOKEN)
now = datetime.now()
current_month = f"{now.month}.{now.year}"


def create_exel_file():
    conn = sqlite3.connect('tsg_database.sql')
    df = pd.read_sql_query("SELECT * FROM meters_data", conn)
    df.to_excel(f"Показания счетчиков {current_month}.xlsx", index=False)
    conn.close()


def send_table(id):
    create_exel_file()
    with open(f"Показания счетчиков {current_month}.xlsx", "rb") as f:
        bot.send_document(id, f)
