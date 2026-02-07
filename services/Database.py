import sqlite3
import random

from utils.logger import logger

db = 'tsg_database.sql'


def init_db():
    """
    Инициализация БД при запуске бота
    :return: None
    """
    try:
        create_table('users', [
            "telegram_id INTEGER UNIQUE",
            "name TEXT",
            "apartment INTEGER",
            "water_count INTEGER",
            "electricity_count INTEGER"
        ])
        create_table('meters_data', [
            "telegram_id INTEGER",
            "apartment INTEGER",
            "month VARCHAR",
            "type_water_meter INTEGER",
            "type_electricity_meter INTEGER",
            "cold_water_1 INTEGER",
            "cold_water_2 INTEGER",
            "cold_water_3 INTEGER",
            "hot_water_1 INTEGER",
            "hot_water_2 INTEGER",
            "hot_water_3 INTEGER",
            "electricity_1 INTEGER",
            "electricity_2 INTEGER"
        ])
        create_table('appeals', [
            'sender_id INTEGER',
            'apartment INTEGER',
            'name TEXT',
            'message_text TEXT',
            'recipient_post TEXT',
            'answer_text TEXT',
            "status TEXT DEFAULT 'open'",
        ])
        create_table('staff', [
            'post TEXT UNIQUE',
            'telegram_id INTEGER',
            'name TEXT',
            'auth_code TEXT'
        ])
    except Exception as e:
        logger.error(f"Ошибка в /init db: {e}", exc_info=True)


def init_staff():
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute('''
        INSERT OR IGNORE INTO staff (post, telegram_id, name) VALUES 
                    ('admin', NULL, 'Администратор'),
                    ('manager', NULL, 'Председатель'),
                    ('accountant', NULL, 'Бухгалтер'),
                    ('plumber', NULL, 'Сантехник'),
                    ('electric', NULL, 'Электрик');
                    ''')
        conn.commit()
    except Exception as e:
        raise DatabaseError
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def select_query(query, params):
    """
    Выполняет SELECT запрос к базе данных
    Args:
        query: SQL-запрос
        params: Параметры запроса

    Returns:
        Полученные данные в виде словаря
    """
    if "SELECT" not in query:
        raise QueryError
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(query, params)
        result = cur.fetchall()
        return [dict(row) for row in result]
    except Exception as e:
        logger.error(
            f'''
            DB_ERROR: Ошибка выполения SQL-запроса. 
            Запрос: {query}
            Параметры: {params}
            Ошибка: {e.__class__.__name__}
            '''
        )
        raise DatabaseError
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def insert_query(query, params):
    """
    Выполняет INSERT запрос к базе данных
    Args:
        query: SQL-запрос
        params: Параметры запроса

    Returns: ID вставленной записи

    """
    if "INSERT" not in query:
        return None
    cur = None
    conn = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(query, params)
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error(
            f'''
            DB_ERROR: Ошибка выполения SQL-запроса. 
            Запрос: {query}
            Параметры: {params}
            Ошибка: {e.__class__.__name__}
            '''
        )
        raise DatabaseError
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def update_query(query, params):
    """
    Выполняет UPDATE запрос к базе данных
    Args:
        query: SQL-запрос
        params: Параметры запроса

    Returns: True, если данные успешно обновлены

    """
    if 'UPDATE' not in query:
        return None
    cur = None
    conn = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(query, params)
        conn.commit()

        return cur.rowcount > 0
    except Exception as e:
        logger.error(
            f'''
            DB_ERROR: Ошибка выполения SQL-запроса. 
            Запрос: {query}
            Параметры: {params}
            Ошибка: {e.__class__.__name__}
            '''
        )
        raise DatabaseError
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def create_table(table_name, table_columns):
    """
    Создание таблицы с заданным названием и колонками
    :param table_name: Строка - Название таблицы
    :param table_columns: Строка - Список колонок
    :return: None
    """
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        columns_str = ", ".join(table_columns)

        # Внимание: имя таблицы и колонки нельзя параметризовать в sqlite,
        # поэтому убеждайся, что table_name и table_columns контролируются в коде и безопасны
        cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {columns_str}
                )
            """)
        logger.info(f'Создана таблица {table_name}')
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка создания таблицы {table_name}: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def delete_query(query, params):
    """Выполняет DELETE запрос к базе данных"""
    if 'DELETE' not in query:
        return None
    cur = None
    conn = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(query, params)
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        logger.error(
            f'''
            DB_ERROR: Ошибка выполения SQL-запроса. 
            Запрос: {query}
            Параметры: {params}
            Ошибка: {e.__class__.__name__}
            '''
        )
        raise DatabaseError
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


class DatabaseError(Exception):
    pass


class QueryError(Exception):
    pass
