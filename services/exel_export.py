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
    """
    Создание Exel-таблицы из таблицы meters_data в БД
    :return: None
    """
    conn = sqlite3.connect('tsg_database.sql')
    parameters = 'apartment, type_water_meter, type_electricity_meter, cold_water_1,cold_water_2, cold_water_3, hot_water_1, hot_water_2, hot_water_3, electricity_1, electricity_2'
    df = pd.read_sql_query(f"SELECT {parameters} FROM meters_data", conn)
    df.to_excel(f"Показания счетчиков {current_month}.xlsx", index=False)
    conn.close()


def send_table(id):
    """
    Отправка таблицы пользователю по id
    :param id: Идентификатор получателя в Telegram
    :return:
    """
    create_exel_file()
    with open(f"Показания счетчиков {current_month}.xlsx", "rb") as f:
        bot.send_document(id, f)
