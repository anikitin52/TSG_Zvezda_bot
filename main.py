from telebot import TeleBot, types
from config import BOT_TOKEN, ADMIN_ID, ADMIN_CODE
from user import User
from utils import *
from datetime import datetime
import threading
import time
import sqlite3


bot = TeleBot(BOT_TOKEN)

temp_users = {}  # временное хранилище User объектов, telegram_id -> User
current_editing = {}  # telegram_id -> текущий редактируемый счетчик

# Список счетчиков TODO: Заоплнить
meters5 = []
meters3 = []

notification_time = [25, 18, 00] # Время напоминания. День, час, минута

# Запуск бота
@bot.message_handler(commands=['start'])
def start(message):
    print(f'{datetime.now()} Пользователь {message.chat.id} запустил бота')
    # Создание базы данных
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    # Создание таблицы (если не существует)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        apartment INTEGER,
        meters_count INTEGER
    )
    """)
    print(f'{datetime.now()} Подключена база данных users')

    # Получение всех пользователей
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    conn.commit()
    cur.close()
    conn.close()

    user_id = message.from_user.id
    if user_id in users:
        bot.send_message(message.chat.id, f"Вы уже зарегистрированы! Квартира: {users[user_id].apartment}")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data='register'))
        bot.send_message(message.chat.id, "Добро пожаловать!", reply_markup=markup)

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
    cur.execute("""
        SELECT * FROM USERS
        """)
    print(f'{datetime.now()} Подключена база данных users')
    users = cur.fetchall()
    conn.commit()
    cur.close()
    conn.close()

    user_id = message.from_user.id
    if any(u[2] == apartment for u in users):
        bot.send_message(message.chat.id, "❌ Квартира уже зарегистрирована")
        return

    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("3 счетчика", callback_data=f"meters_3_{apartment}"),
        types.InlineKeyboardButton("5 счетчиков", callback_data=f"meters_5_{apartment}")
    )
    bot.send_message(message.chat.id, "Выберите количество счетчиков:", reply_markup=markup)

# Завершение настройки квартиры
@bot.callback_query_handler(func=lambda call: call.data.startswith('meters_'))
def select_meters(call):
    _, count, apartment = call.data.split('_')
    user_id = call.from_user.id

    # Добавляем пользователя в базу данных
    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (telegram_id, apartment, meters_count) VALUES (?, ?, ?)
    """, (user_id, int(apartment), int(count)))
    conn.commit()
    cur.close()
    conn.close()

    bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")
    bot.send_message(ADMIN_ID, f"Новый пользователь: кв. {apartment}, счетчиков: {count}")
    print(f'{datetime.now()} Новый пользователь. Квартира {apartment}')


# Переход в профиль
@bot.message_handler(commands=['account'])
def account(message):
    telegram_id = message.from_user.id

    conn = sqlite3.connect('users.sql')
    cur = conn.cursor()

    # Ищем пользователя по telegram_id
    cur.execute("""
        SELECT apartment, meters_count FROM users WHERE telegram_id = ?
    """, (telegram_id,))

    result = cur.fetchone()
    cur.close()
    conn.close()

    if result:
        apartment, meters_count = result
        bot.send_message(
            message.chat.id,
            f"🏠 Ваш профиль:\nКвартира: {apartment}\nСчётчиков: {meters_count}"
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Вы не зарегистрированы. Для начала нажмите /start"
        )

@bot.message_handler(commands=['send'])
def send_data(message):
    telegram_id = message.from_user.id

    if telegram_id in temp_users:
        user = temp_users[telegram_id]
    else:
        conn = sqlite3.connect('users.sql')
        cur = conn.cursor()
        cur.execute("SELECT apartment, meters_count FROM users WHERE telegram_id = ?", (telegram_id,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()

        if not user_data:
            bot.send_message(message.chat.id, "Вы не зарегистрированы")
            return

        apartment, meters_count = user_data
        user = User(telegram_id, apartment, meters_count)
        temp_users[telegram_id] = user

    month, year = get_month()
    markup = create_meters_markup(user)
    bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('meter_'))
def meter_input(call):
    meter = call.data.split('_')[1]
    current_editing[call.from_user.id] = meter
    msg = bot.send_message(call.message.chat.id, f"Введите показания для счетчика {meter}:")
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
    bot.send_message(message.chat.id, f"Показания для счетчика {meter} сохранены.\n📊 Показания за {month} {year}", reply_markup=markup)

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
    msg = bot.send_message(call.message.chat.id, f"Введите новое значение для счетчика {meter}:")
    bot.register_next_step_handler(msg, process_value)

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_all')
def confirm_all(call):
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return

    report = user.get_report()
    bot.send_message(ADMIN_ID, f"📨 Показания от кв. {user.apartment}:\n{report}")
    user.clear_metrics()
    temp_users.pop(call.from_user.id, None)
    bot.send_message(call.message.chat.id, "✅ Показания отправлены")

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


# Авторизация админа
@bot.message_handler()
def admin_auth(message):
    if message.text == ADMIN_CODE:
        global ADMIN_ID
        ADMIN_ID = message.chat.id
        bot.send_message(message.chat.id, "✅ Вы авторизованы как админ")
        print(f'{datetime.now()} Админ авторизован. ID = {message.chat.id}')


# Ежемесячное напоминание
def send_monthly_notifications():
    while True:
        now = datetime.now()
        if now.day == notification_time[0] and now.hour == notification_time[1] and now.minute == notification_time[2]:
            for user in users.values():
                try:
                    bot.send_message(user.telegram_id, "📢 Время передать показания! /send")
                    print(f'{now} Напоминание отправлено')
                except Exception as e:
                    print(f"{now} Ошибка отправки {user.telegram_id}: {e}")
            time.sleep(3600)  # 1 час паузы
        time.sleep(60)

# Запуск
if __name__ == '__main__':
    now = datetime.now()
    print(f"{now} Бот запущен")
    threading.Thread(target=send_monthly_notifications, daemon=True).start()
    bot.polling(none_stop=True)
