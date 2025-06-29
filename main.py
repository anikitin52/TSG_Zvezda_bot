from telebot import TeleBot, types
from config import *
from user import *
from utils import *
from data import *
from table_create import *
from database import *
from datetime import datetime
import threading
import sqlite3

bot = TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start'])  # Запуск бота
def start(message):
    tablename = 'users'
    user_id = message.from_user.id

    create_table(tablename, [
        "telegram_id INTEGER UNIQUE",
        "apartment INTEGER",
        "water_count INTEGER",
        "electricity_count INTEGER"
    ])

    user = find_user_by_id(tablename, user_id, '*')

    if user:
        apartment = user[1] # TODO: Проверить
        bot.send_message(message.chat.id, f"✅ Вы уже зарегистрированы! Квартира: {apartment}")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data='register'))
        bot.send_message(message.chat.id, "👋 Добро пожаловать! Для начала зарегистрируйтесь:", reply_markup=markup)


@bot.message_handler(commands=['export'])
def export_data(message):
    if message.chat.id != ACCOUNTANT_ID:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде")

    create_exel_file()
    with open("meter_data.xlsx", "rb") as f:
        bot.send_document(message.chat.id, f)


# Переход в профиль
@bot.message_handler(commands=['account'])
def account(message):
    telegram_id = message.from_user.id
    user_exists = find_user_by_id('users', telegram_id, 'COUNT(*)')[0] > 0 # TODO: Проверить

    if not user_exists:
        bot.send_message(
            message.chat.id,
            "❌ Вы не зарегистрированы. Для начала нажмите /start"
        )
        return

    result = find_user_by_id('users', telegram_id, 'apartment, water_count, electricity_count')

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
        bot.send_message(message.chat.id,
                         "❌ Прием показаний закрыт. Показания принимаются с 23 по 27 число каждого месяца")
        return

    telegram_id = message.from_user.id

    if telegram_id in temp_users:
        user = temp_users[telegram_id]
    else:

        user_data = find_user_by_id('users', telegram_id, 'apartment, water_count, electricity_count')

        if not user_data:
            bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
            return

        apartment, water_count, electricity_count = user_data
        user = User(telegram_id, apartment, water_count, electricity_count)
        temp_users[telegram_id] = user

    month, year = get_month()
    markup = create_meters_markup(user)
    bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)



# Обработка обращения
@bot.message_handler(commands=['manager'])
def address_manager(message):
    msg = bot.send_message(message.chat.id, "✉️ Напишите своё обращение к председателю ТСЖ")
    bot.register_next_step_handler(msg, send_address_manager)


def send_address_manager(message):
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


@bot.message_handler(commands=['accountant'])
def address_accountant(message):
    msg = bot.send_message(message.chat.id, "✉️ Напишите своё обращение к бухгалтеру")
    bot.register_next_step_handler(msg, send_address_accountant)


def send_address_accountant(message):
    text = message.text.strip()
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or ""
    sender_surname = message.from_user.last_name or ""

    result = find_user_by_id('users', sender_id, 'apartment')

    if result:
        apartment = result[0]
    else:
        apartment = "Неизвестна"

    # Отправка сообщения бухгалтеру
    bot.send_message(
        ACCOUNTANT_ID,
        f'📨 Обращение от жителя:\n'
        f'👤 {sender_name} {sender_surname}\n'
        f'🏠 Квартира: {apartment}\n\n'
        f'_{text}_',
        parse_mode="Markdown"
    )
    bot.send_message(message.chat.id, "✅ Обращение успешно отправлено бухгалтеру")
    print(f'{datetime.now()} Обращение отправлено. Кв. {apartment}, ID {sender_id}')


@bot.message_handler(commands=['electric'])
def address_electric(message):
    msg = bot.send_message(message.chat.id, "✉️ Напишите текст заявки на работу электрика")
    bot.register_next_step_handler(msg, send_address_electric)


def send_address_electric(message):
    text = message.text.strip()
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or ""
    sender_surname = message.from_user.last_name or ""

    result = find_user_by_id('users', sender_id, 'apartment')

    if result:
        apartment = result[0]
    else:
        apartment = "Неизвестна"

    bot.send_message(
        ELECTRIC_ID,
        f'📨 Новая заявка на работу:\n'
        f'👤 {sender_name} {sender_surname}\n'
        f'🏠 Квартира: {apartment}\n\n'
        f'_{text}_',
        parse_mode="Markdown"
    )
    bot.send_message(message.chat.id, "✅ Заявка на работу электрика успешно отправлена")
    print(f'{datetime.now()} Обращение отправлено. Кв. {apartment}, ID {sender_id}')


@bot.message_handler(commands=['plumber'])
def address_plumber(message):
    msg = bot.send_message(message.chat.id, "✉️ Напишите текст заявки на работу сантехника")
    bot.register_next_step_handler(msg, send_address_plumber)


def send_address_plumber(message):
    text = message.text.strip()
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or ""
    sender_surname = message.from_user.last_name or ""

    result = find_user_by_id('users', sender_id, 'apartment')

    if result:
        apartment = result[0]
    else:
        apartment = "Неизвестна"

    bot.send_message(
        PLUMBER_ID,
        f'📨 Новая заявка на работу:\n'
        f'👤 {sender_name} {sender_surname}\n'
        f'🏠 Квартира: {apartment}\n\n'
        f'_{text}_',
        parse_mode="Markdown"
    )
    bot.send_message(message.chat.id, "✅ Заявка на работу сантехника успешно отправлена")
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

    if message.text == ELECTRIC_CODE:
        global ELECTRIC_ID
        ELECTRIC_ID = message.chat.id
        electric = message.from_user
        bot.send_message(message.chat.id, "✅ Вы авторизованы как Электрик")

        bot.send_message(ADMIN_ID,
                         f'‼ Пользователь {electric.first_name} {electric.last_name} авторизоан как Электрик')
        print(
            f'{datetime.now()} Электрик авторизован. ID = {message.chat.id}: {message.from_user.first_name} {message.from_user.last_name}')

    if message.text == PLUMBER_CODE:
        global PLUMBER_ID
        PLUMBER_ID = message.chat.id
        plumber = message.from_user
        bot.send_message(message.chat.id, "✅ Вы авторизованы как Сантехник")

        bot.send_message(ADMIN_ID,
                         f'‼ Пользователь {plumber.first_name} {plumber.last_name} авторизоан как Электрик')
        print(
            f'{datetime.now()} Сантехник авторизован. ID = {message.chat.id}: {message.from_user.first_name} {message.from_user.last_name}')


def notifications():
    pass
    '''
    while True:
        now = datetime.now()
        current_month = f"{now.month}.{now.year}"

        # Получаем всех пользователей из базы users.sql
        try:
            conn_users = sqlite3.connect('users.sql')
            cur_users = conn_users.cursor()
            cur_users.execute("SELECT telegram_id, apartment, water_count, electricity_count FROM users")
            users = cur_users.fetchall()
        finally:
            cur_users.close()
            conn_users.close()

        try:
            # Подключение к базе с показаниями
            conn_data = sqlite3.connect('meter_data.sql')
            cur_data = conn_data.cursor()

            # ⏰ Уведомление о начале сбора показаний
            if now.day == day_start_collection and now.hour == 8 and now.minute == 00:
                print(f"{now} Уведомление о начале сбора показаний")
                for telegram_id, _, _, _ in users:
                    try:
                        bot.send_message(telegram_id, "📬 Открыт сбор показаний счетчиков")
                        print(f"{now} Уведомление отправлено {telegram_id}")
                    except Exception as e:
                        print(f"{now} Ошибка отправки {telegram_id}: {e}")
                time.sleep(60)

            # ⏰ Уведомление о завершении сбора показаний
            if now.day == day_end_collection and now.hour == 17 and now.minute == 36:
                print(f"{now} Уведомление о завершении сбора")

                # Создаём и отправляем Excel-файл
                create_exel_file()
                with open(f"Показания счетчиков {current_month}.xlsx", "rb") as f:
                    bot.send_document(ACCOUNTANT_ID, f)

                for telegram_id, apartment, water_count, electricity_count in users:
                    cur_data.execute(
                        "SELECT 1 FROM meters_data WHERE telegram_id = ? AND month = ?",
                        (telegram_id, current_month)
                    )
                    if cur_data.fetchone():
                        print(f"{now} Уже передавал: {telegram_id}")
                        continue

                    if telegram_id not in temp_users:
                        temp_users[telegram_id] = User(telegram_id, apartment, water_count, electricity_count)

                    try:
                        bot.send_message(telegram_id, "Прием показаний закрыт /send")
                        print(f"{now} Напоминание отправлено {telegram_id}")
                    except Exception as e:
                        print(f"{now} Ошибка отправки {telegram_id}: {e}")

            # ⏰ Ежемесячное напоминание
            if now.day == notification_time[0] and now.hour == notification_time[1] and now.minute == notification_time[2]:
                print(f"{now} Ежемесячное напоминание о передаче показаний")
                for telegram_id, apartment, water_count, electricity_count in users:
                    cur_data.execute(
                        "SELECT 1 FROM meters_data WHERE telegram_id = ? AND month = ?",
                        (telegram_id, current_month)
                    )
                    if cur_data.fetchone():
                        print(f"{now} Уже передавал: {telegram_id}")
                        continue

                    if telegram_id not in temp_users:
                        temp_users[telegram_id] = User(telegram_id, apartment, water_count, electricity_count)

                    try:
                        bot.send_message(telegram_id, "📢 Время передать показания! /send")
                        print(f"{now} Напоминание отправлено {telegram_id}")
                    except Exception as e:
                        print(f"{now} Ошибка отправки {telegram_id}: {e}")

                time.sleep(3600)

        finally:
            cur_data.close()
            conn_data.close()

        time.sleep(60)
        '''


# Запуск
if __name__ == '__main__':
    from registration import *
    from send_data import *
    now = datetime.now()
    print(f"{now} Бот запущен")
    threading.Thread(target=notifications, daemon=True).start()
    bot.polling(none_stop=True)
