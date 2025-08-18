import sqlite3

from services.logger import logger

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
        logger.info(f'Добавлены данные в таблицу {tablename}')
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка вставки в таблицу {tablename}: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def delete_from_database(table_name, conditions):
    """
    Удаление записи из базы данных
    :param table_name: имя таблицы
    :param conditions: словарь условий {поле: значение}
    """
    where_clause = " AND ".join([f"{k} = ?" for k in conditions.keys()])
    values = tuple(conditions.values())

    with sqlite3.connect(db) as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE {where_clause}", values)
        conn.commit()


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
        logger.error(f"Ошибка поиска пользователя: {e}")
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
        logger.error(f"Ошибка в функции select_all: {e}")
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
        logger.error(f"Ошибка в функции select_all_where: {e}")
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
        logger.warning(f'Таблица {tablename} очищена, автоинкремент сброшен')
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
        logger.error(f"Ошибка в функции update_values: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def update_appeal_status(answer_text, appeal_id):
    """
    Обновление статуса обращения и записи ответа в БД
    :param answer_text: Текст ответа
    :param appeal_id: ID обращения
    """
    conn = None
    cur = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        # Получаем текущие ответы (если есть)
        cur.execute('SELECT answer_text FROM appeals WHERE id = ?', (appeal_id,))
        existing_answer = cur.fetchone()

        # Формируем новый ответ с сохранением истории
        new_answer = f"{existing_answer[0]}\n\n---\n\n{answer_text}" if existing_answer and existing_answer[
            0] else answer_text

        # Обновляем запись с сохранением даты ответа
        cur.execute('''
            UPDATE appeals SET 
                status = 'closed',
                answer_text = ?
            WHERE id = ?
        ''', (new_answer, appeal_id))

        conn.commit()
        logger.info(f"Обновлен ответ для обращения ID {appeal_id}")

    except Exception as e:
        logger.error(f"Ошибка при обновлении обращения {appeal_id}: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def check_appeal_status(appeal_id):
    cur = None
    conn = None
    try:
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        cur.execute('SELECT * FROM appeals WHERE id = ?', appeal_id)
        result = cur.fetchone()

    except Exception as e:
        logger.error(f"Ошибка в функции update_appeal_status: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return result[6] if result else None


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
        logger.error(f"Ошибка в функции find_staff_id: {e}")
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    return result[0] if result else None
