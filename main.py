from telebot import TeleBot, types
from config import *
from user import *
from utils import *
from data import *
from table_create import *
from datetime import datetime
import threading
import time
import sqlite3

bot = TeleBot(BOT_TOKEN)

# Запуск бота
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    print(f'{datetime.now()} Пользователь {user_id} запустил бота')

    # Подключение к базе данных
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    # Создание таблицы, если не существует
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            apartment INTEGER,
            water_count INTEGER,
            electricity_count INTEGER
        )
    """)
    print(f'{datetime.now()} Таблица users проверена или создана')

    # Поиск пользователя по telegram_id
    cur.execute("SELECT apartment FROM users WHERE telegram_id = ?", (user_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result:
        apartment = result[0]
        bot.send_message(message.chat.id, f"✅ Вы уже зарегистрированы! Квартира: {apartment}")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data='register'))
        bot.send_message(message.chat.id, "👋 Добро пожаловать! Для начала зарегистрируйтесь:", reply_markup=markup)


# Регистрация пользователя
@bot.callback_query_handler(func=lambda call: call.data == 'register')
def register(call):
    msg = bot.send_message(call.message.chat.id, "Введите номер вашей квартиры (1–150):")
    bot.register_next_step_handler(msg, process_apartment)

# Настройка квартиры
def process_apartment(message):
    try:
        apartment = int(message.text.strip())
        if not 1 <= apartment <= 150:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 150")
        bot.register_next_step_handler(msg, process_apartment)
        return

    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()
    cur.execute("SELECT * FROM USERS")
    users = cur.fetchall()
    conn.commit()
    cur.close()
    conn.close()

    user_id = message.from_user.id
    if any(u[2] == apartment for u in users):
        bot.send_message(message.chat.id, "❌ Квартира уже зарегистрирована")
        return

    # Сохраняем квартиру во временные данные
    user_data[user_id] = {'apartment': apartment}

    msg = bot.send_message(message.chat.id, "Введите количество счетчиков холодной воды (от 1 до 3):")
    bot.register_next_step_handler(msg, check_water_meters)

def check_water_meters(message):
    try:
        water_meters = int(message.text.strip())
        if not 1 <= water_meters <= 3:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
        bot.register_next_step_handler(msg, check_water_meters)
        return

    user_id = message.from_user.id
    # Получаем сохраненный номер квартиры из user_data
    apartment = user_data[user_id]['apartment']

    # Обновляем данные в user_data
    user_data[user_id] = {
        'water_count': water_meters,
        'apartment': apartment  # Используем сохраненное значение квартиры
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('Однотарифный', callback_data=f'elec_1_{water_meters}_{apartment}'),
        types.InlineKeyboardButton('Двухтарифный', callback_data=f'elec_2_{water_meters}_{apartment}')
    )
    bot.send_message(message.chat.id, "Выберите тип счетчика электричества", reply_markup=markup)


# Завершение настройки квартиры
@bot.callback_query_handler(func=lambda call: call.data.startswith('elec_'))
def select_meters(call):
    parts = call.data.split('_')
    elec_type = parts[1]  # 1 или 2
    water_count = parts[2]
    user_id = call.from_user.id

    # Получаем сохраненные данные
    apartment = user_data[user_id]['apartment']

    # Добавляем пользователя в базу данных
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (telegram_id, apartment, water_count, electricity_count) 
        VALUES (?, ?, ?, ?)
    """, (user_id, int(apartment), int(water_count), int(elec_type)))
    conn.commit()
    cur.close()
    conn.close()

    # Удаляем временные данные
    del user_data[user_id]

    bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")
    bot.send_message(ADMIN_ID,
                     f"Новый пользователь: кв. {apartment}, "
                     f"счетчиков воды: {water_count}, "
                     f"тип счетчика электричества: {'двухтарифный' if elec_type == '2' else 'однотарифный'}")
    print(f'{datetime.now()} Новый пользователь. Квартира {apartment}')

@bot.message_handler(commands=['export'])
def export_data(message):
    if message.chat.id != ACCOUNTANT_ID:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде")

    send_exel_file()
    with open("meter_data.xlsx", "rb") as f:
        bot.send_document(message.chat.id, f)


# Переход в профиль
@bot.message_handler(commands=['account'])
def account(message):
    telegram_id = message.from_user.id
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    # Сначала проверяем, есть ли пользователь в базе
    cur.execute("SELECT COUNT(*) FROM users WHERE telegram_id = ?", (telegram_id,))
    user_exists = cur.fetchone()[0] > 0

    if not user_exists:
        cur.close()
        conn.close()
        bot.send_message(
            message.chat.id,
            "❌ Вы не зарегистрированы. Для начала нажмите /start"
        )
        return

    # Если пользователь есть - получаем его данные
    cur.execute("""
        SELECT apartment, water_count, electricity_count FROM users WHERE telegram_id = ?
    """, (telegram_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if result:
        apartment, water_count, electricity_type = result
        rate = "Однотарифный" if electricity_type == "one_rate" else "Двухтарифный"
        bot.send_message(
            message.chat.id,
            f"🏠 Ваш профиль:\nКвартира: {apartment}\n"
            f"Счётчиков воды: {water_count}\n"
            f"Счетчик электричества: {rate}"
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при получении данных профиля"
        )


@bot.message_handler(commands=['send'])
def send_data(message):
    now = datetime.now()
    if now.day < day_start_collection or now.day > day_end_collection:
        bot.send_message(message.chat.id, "❌ Прием показаний закрыт. Показания принимаются с 23 по 27 число каждого месяца")
        return

    telegram_id = message.from_user.id

    if telegram_id in temp_users:
        user = temp_users[telegram_id]
    else:
        conn = sqlite3.connect('users.sql')
        cur = conn.cursor()
        cur.execute("SELECT apartment, water_count, electricity_count FROM users WHERE telegram_id = ?", (telegram_id,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()

        if not user_data:
            bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
            return

        apartment, water_count, electricity_count = user_data
        user = User(telegram_id, apartment, water_count, electricity_count)
        temp_users[telegram_id] = user

    month, year = get_month()
    markup = create_meters_markup(user)
    bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('meter_'))
def meter_input(call):
    meter = call.data.split('_')[1]
    current_editing[call.from_user.id] = meter
    msg = bot.send_message(call.message.chat.id, f"Введите показания для выбранного счетчика:")
    bot.register_next_step_handler(msg, process_value)


def process_value(message):
    telegram_id = message.from_user.id
    user = temp_users.get(telegram_id)
    meter = current_editing.get(telegram_id)

    if not user or not meter:
        bot.send_message(message.chat.id, "Ошибка: пользователь или счётчик не найдены")
        return

    try:
        value = int(message.text.strip())
        if value < 0:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите положительное число")
        bot.register_next_step_handler(msg, process_value)
        return

    user.add_metric(meter, value)

    month, year = get_month()
    markup = create_meters_markup(user)
    bot.send_message(message.chat.id, f"📊 Показания за {month} {year}",
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'review')
def review(call):
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return
    markup = create_review_markup(user)
    month, year = get_month()
    bot.send_message(call.message.chat.id, f"📝 Проверка за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_value(call):
    meter = call.data.split('_')[1]
    current_editing[call.from_user.id] = meter
    msg = bot.send_message(call.message.chat.id, f"Введите новое значение для выбранного счетчика")
    bot.register_next_step_handler(msg, process_value)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_all')
def confirm_all(call):
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return

    report = user.get_report()

    # Получаем реальные имена счетчиков
    cold_list = cold_water_meters[user.water_count]
    hot_list = hot_water_meters[user.water_count]
    elec_list = electricity_meters[user.electricity_type]

    # Получаем показания из current_meters
    data = current_meters.get(user.telegram_id, {})
    # ХВС
    cw1 = int(data.get(cold_list[0], 0)) if len(cold_list) > 0 else 0
    cw2 = int(data.get(cold_list[1], 0)) if len(cold_list) > 1 else 0
    cw3 = int(data.get(cold_list[2], 0)) if len(cold_list) > 2 else 0

    # ГВС
    hw1 = int(data.get(hot_list[0], 0)) if len(hot_list) > 0 else 0
    hw2 = int(data.get(hot_list[1], 0)) if len(hot_list) > 1 else 0
    hw3 = int(data.get(hot_list[2], 0)) if len(hot_list) > 2 else 0

    # Электричество
    el1 = int(data.get(elec_list[0], 0)) if len(elec_list) > 0 else 0
    el2 = int(data.get(elec_list[1], 0)) if len(elec_list) > 1 else 0
    now = datetime.now()
    month = now.strftime('%m.%Y')

    conn = sqlite3.connect('meter_data.sql')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS meters_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            apartment INTEGER,
            month VARCHAR,
            type_water_meter INTEGER,
            type_electricity_meter INTEGER,
            cold_water_1 INTEGER,
            cold_water_2 INTEGER,
            cold_water_3 INTEGER,
            hot_water_1 INTEGER,
            hot_water_2 INTEGER,
            hot_water_3 INTEGER,
            electricity_1 INTEGER,
            electricity_2 INTEGER
        )
    ''')

    cur.execute('''
        INSERT INTO meters_data (
            telegram_id, 
            apartment, 
            month, 
            type_water_meter, 
            type_electricity_meter, 
            cold_water_1, 
            cold_water_2,
            cold_water_3,
            hot_water_1,
            hot_water_2,
            hot_water_3,
            electricity_1,
            electricity_2) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (user.telegram_id,
         user.apartment,
         month,
         user.water_count,
         user.electricity_type,
         cw1, cw2, cw3, hw1, hw2, hw3, el1, el2)
    )

    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(ACCOUNTANT_ID, f"📨 Показания от кв. {user.apartment}:\n{report}")
    user.clear_metrics()
    temp_users.pop(call.from_user.id, None)
    bot.send_message(call.message.chat.id, "✅ Показания отправлены")
    print(f'{datetime.now()} Показания переданы. Квартира {user.apartment}')

@bot.callback_query_handler(func=lambda call: call.data == 'back_edit')
def back_edit(call):
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return

    markup = create_meters_markup(user)
    month, year = get_month()
    bot.send_message(call.message.chat.id, f"📊 Возврат к редактированию за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel(call):
    user = temp_users.get(call.from_user.id)
    if user:
        user.clear_metrics()
        temp_users.pop(call.from_user.id, None)
    bot.send_message(call.message.chat.id, "🚫 Ввод отменён")


# Обработка обращения
@bot.message_handler(commands=['address'])
def address(message):
    msg = bot.send_message(message.chat.id, "✉️ Напишите своё обращение к председателю ТСЖ")
    bot.register_next_step_handler(msg, send_address)


def send_address(message):
    text = message.text.strip()
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or ""
    sender_surname = message.from_user.last_name or ""

    # Получаем номер квартиры из базы данных
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()
    cur.execute("SELECT apartment FROM users WHERE telegram_id = ?", (sender_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()

    if result:
        apartment = result[0]
    else:
        apartment = "Неизвестна"

    # Отправка сообщения председателю
    bot.send_message(
        MANAGER_ID,
        f'📨 Обращение от жителя:\n'
        f'👤 {sender_name} {sender_surname}\n'
        f'🏠 Квартира: {apartment}\n\n'
        f'_{text}_',
        parse_mode="Markdown"
    )
    bot.send_message(message.chat.id, "✅ Обращение успешно отправлено председателю")
    print(f'{datetime.now()} Обращение отправлено. Кв. {apartment}, ID {sender_id}')


# Авторизация привелегированных пользователей
@bot.message_handler()
def auth(message):
    if message.text == ADMIN_CODE:
        global ADMIN_ID
        ADMIN_ID = message.chat.id
        bot.send_message(message.chat.id, "✅ Вы авторизованы как админ")
        print(
            f'{datetime.now()} Админ авторизован. ID = {message.chat.id}: {message.from_user.first_name} {message.from_user.last_name}')

    if message.text == MANAGER_CODE:
        global MANAGER_ID
        MANAGER_ID = message.chat.id
        manager = message.from_user
        bot.send_message(message.chat.id, "✅ Вы авторизованы как председатель")
        bot.send_message(ADMIN_ID,
                         f'‼ Пользователь {manager.first_name} {manager.last_name} авторизоан как Председатель')
        print(
            f'{datetime.now()} Председатель авторизован. ID = {message.chat.id}: {message.from_user.first_name} {message.from_user.last_name}')

    if message.text == ACCOUNTANT_CODE:
        global ACCOUNTANT_ID
        ACCOUNTANT_ID = message.chat.id
        accountant = message.from_user
        bot.send_message(message.chat.id, "✅ Вы авторизованы как Бухгалтер")

        bot.send_message(ADMIN_ID,
                         f'‼ Пользователь {accountant.first_name} {accountant.last_name} авторизоан как Бухгалтер')
        print(
            f'{datetime.now()} Бухгалтер авторизован. ID = {message.chat.id}: {message.from_user.first_name} {message.from_user.last_name}')



# Ежемесячное напоминание
def send_monthly_notifications():
    while True:
        now = datetime.now()
        if now.day == notification_time[0] and now.hour == notification_time[1] and now.minute == notification_time[2]:
            conn = sqlite3.connect('users.sql')
            cur = conn.cursor()
            cur.execute("SELECT telegram_id, apartment, meters_count FROM users")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            # TODO: Если пользователь уже отправлял в этом месяце, то не отправлять
            for row in rows:
                telegram_id, apartment, meters_count = row
                # Кэшируем пользователя, если ещё нет
                if telegram_id not in temp_users:
                    temp_users[telegram_id] = User(telegram_id, apartment, meters_count)

                try:
                    bot.send_message(telegram_id, "📢 Время передать показания! /send")
                    print(f'{now} Напоминание отправлено пользователю {telegram_id}')
                except Exception as e:
                    print(f"{now} Ошибка отправки {telegram_id}: {e}")

            time.sleep(3600)  # Пауза 1 час, чтобы не слать много раз в минуту
        time.sleep(60)


# Запуск
if __name__ == '__main__':
    now = datetime.now()
    print(f"{now} Бот запущен")
    threading.Thread(target=send_monthly_notifications, daemon=True).start()
    bot.polling(none_stop=True)
