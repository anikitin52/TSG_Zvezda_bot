import sqlite3
from datetime import datetime

db = 'tsg_database.sql'


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
        conn.commit()
    except Exception as e:
        print(f"Ошибка в create_table: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def insert_to_database(tablename, columns, values):
    """
    Вставка значений в таблицу
    :param tablename: Строка - название таблицы
    :param columns: Строка - названия колонок
    :param values: Строка - значения, соответствующие колонкам
    :return: None
    """
    if len(columns) != len(values):
        raise ValueError("Количество колонок и значений должно совпадать")

    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        columns_str = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(values))

        cur.execute(
            f"INSERT INTO {tablename} ({columns_str}) VALUES ({placeholders})",
            values
        )
        conn.commit()
    except Exception as e:
        print(f"Ошибка в insert_to_database: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def find_user_by_id(table_name, user_id, parameter='*'):
    """
    Поиск пользователя по id в заданной таблице
    :param table_name: Строка - название таблицы
    :param user_id: Целое число - id пользователя
    :param parameter: Строка - параметры посика. По умлочанию: * (все)
    :return: Результат - данные о конкретном пользователе (если пользователь не найден - None)
    """
    conn = None
    cur = None
    result = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(
            f"SELECT {parameter} FROM {table_name} WHERE telegram_id = ?",
            (user_id,)
        )
        result = cur.fetchone()
    except Exception as e:
        print(f"Ошибка в find_user_by_id: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return result


def select_all(tablename):
    """
    Выбор всех строк в заданной таблице
    :param tablename: Строка - название таблицы
    :return: Результат - все данные из таблицы (если таблица не найдена - None)
    """
    conn = None
    cur = None
    result = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {tablename}")
        result = cur.fetchall()
    except Exception as e:
        print(f"Ошибка в select_all: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return result


def select_all_where(table_name, where_condition):
    """
    Поиск всех значений в таблице при заданном условии
    :param table_name: Строка - название таблицы
    :param where_condition: Строка - условие поиска
    :return: Все строки таблицы, соответствующие заданному условию
    """
    conn = None
    cur = None
    result = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(f"SELECT * FROM {table_name} WHERE {where_condition}")
        result = cur.fetchall()
    except Exception as e:
        print(f"Ошибка в select_all_where: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    return result


def clear_table(tablename):
    """
    Очистка данных в таблиуе
    :param tablename: Строка - название таблицы
    :return: None
    """
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(f"DELETE FROM {tablename}")
        cur.execute("DELETE FROM sqlite_sequence WHERE name = ?", (tablename,))
        conn.commit()
        print(f'{datetime.now()} Таблица {tablename} очищена, автоинкремент сброшен')
    except Exception as e:
        print(f"Ошибка в clear_table: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def update_values(table_name, set_values, where_conditions):
    """
    Изменение значений в таблице
    :param table_name: Строка - название таблицы
    :param set_values: Значения, которые нужно обновить
    :param where_conditions: Новые значеиня
    :return: None
    """
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        set_clause = ", ".join([f"{k} = ?" for k in set_values.keys()])
        where_clause = " AND ".join([f"{k} = ?" for k in where_conditions.keys()])

        parameters = list(set_values.values()) + list(where_conditions.values())

        cur.execute(
            f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}",
            parameters
        )
        conn.commit()
    except Exception as e:
        print(f"Ошибка в update_values: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def find_staff_id(role, table_name='staff'):
    """
    Поиск сотрудника по id
    :param role: Строка - должность сотрудника
    :param table_name: Название таблицы (по умолчанию "staff")
    :return: id сотрудника в Telegram (если сотрудник не найден - None)
    """
    cur = None
    conn = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute(f"SELECT telegram_id FROM {table_name} WHERE post = ?", (role,))
        result = cur.fetchone()

    except Exception as e:
        print(f"Ошибка в find_staff_id: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return result[0] if result else None
