from telebot import TeleBot
import pandas as pd
import sqlite3
from datetime import datetime
from services.logger import logger

from config import BOT_TOKEN

bot = TeleBot(BOT_TOKEN)
now = datetime.now()
current_month = f"{now.month}.{now.year}"


def create_exel_file():
    """
    Создание Exel-таблицы из таблицы meters_data в БД
    :return: None
    """
    conn = None
    try:
        conn = sqlite3.connect('tsg_database.sql')
        parameters = 'apartment, type_water_meter, type_electricity_meter, cold_water_1,cold_water_2, cold_water_3, hot_water_1, hot_water_2, hot_water_3, electricity_1, electricity_2'
        df = pd.read_sql_query(f"SELECT {parameters} FROM meters_data", conn)
        df.rename(columns= {
            'apartment' : 'Квартира',
            'type_water_meter' : 'Счетчиков воды',
            'type_electricity_meter' : 'Счетчиков электричества',
            'cold_water_1' : 'ХВС-1',
            'cold_water_2' : 'ХВС-2',
            'cold_water_3' : 'ХВС-3',
            'hot_water_1' : 'ГВС-1',
            'hot_water_2' : 'ГВС-2',
            'hot_water_3' : 'ГВС-3',
            'electricity_1' : 'Электричество-1',
            'electricity_2' : 'Электричество-2'
        }, inplace=True)
    except Exception as e:
        logger.error(f'Ошибка создания Exel-файла: {e}')
        raise
    finally:
        df.to_excel(f"Показания счетчиков {current_month}.xlsx", index=False)
        conn.close()


def send_table(id):
    """
    Отправка таблицы пользователю по id
    :param id: Идентификатор получателя в Telegram
    :return:
    """
    create_exel_file()
    try:
        with open(f"Показания счетчиков {current_month}.xlsx", "rb") as f:
            bot.send_document(id, f)
    except Exception as e:
        bot.send_message(id, "Файл не найден")
        logger.error(f'Ошибка отправки Exel-файла: {e}')
