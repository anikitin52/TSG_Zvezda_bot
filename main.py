from telebot import TeleBot, types
from datetime import datetime
import threading
import time

from config import *
from data.models import User
from services.utils import *
from data.data import *
from services.exel_export import send_table
from data.database import *


bot = TeleBot(BOT_TOKEN)
now = datetime.now()

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
        apartment = user[2]  # TODO: Проверить
        bot.send_message(message.chat.id, f"✅ Вы уже зарегистрированы! Квартира: {apartment}")

    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data='register'))
        print(f"{now} Пользователь {user_id} запустил бота")
        bot.send_message(message.chat.id, "👋 Добро пожаловать! Для начала зарегистрируйтесь:", reply_markup=markup)


@bot.message_handler(commands=['export'])
def export_data(message):
    if message.chat.id != ACCOUNTANT_ID:
        bot.send_message(message.chat.id, "У вас нет доступа к этой команде")
        return
    else:
        print(f'{now} Пользоватлель {message.chat.id} экспортировал Exel-таблицу')
        send_table(message.chat.id)



@bot.callback_query_handler(func=lambda call: call.data == 'register')
def register(call):
    msg = bot.send_message(call.message.chat.id, "Введите номер вашей квартиры (1–150):")
    bot.register_next_step_handler(msg, process_apartment)


def process_apartment(message):
    tablename = 'users'
    try:
        apartment = int(message.text.strip())
        if not 1 <= apartment <= 150:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 150")
        bot.register_next_step_handler(msg, process_apartment)
        return

    users = select_all(tablename)

    user_id = message.from_user.id
    if any(u[2] == apartment for u in users):
        bot.send_message(message.chat.id, "❌ Квартира уже зарегистрирована")
        return

    user_data[user_id] = {'apartment': apartment}
    msg = bot.send_message(message.chat.id, "Введите количество счетчиков холодной воды (от 1 до 3):")
    bot.register_next_step_handler(msg, check_water_meters)


def check_water_meters(message):
    try:  # TODO: Вынести в отдельную функцию
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


@bot.callback_query_handler(func=lambda call: call.data.startswith('elec_'))
def select_meters(call):
    parts = call.data.split('_')
    elec_type = parts[1]  # 1 или 2
    water_count = parts[2]
    user_id = call.from_user.id
    tablename = 'users'

    # Получаем сохраненные данные
    apartment = user_data[user_id]['apartment']

    insert_to_database(tablename,
                       ['telegram_id', 'apartment', 'water_count', 'electricity_count'],
                       [user_id, int(apartment), int(water_count), int(elec_type)])

    print('OK')
    del user_data[user_id]
    bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")
    bot.send_message(ADMIN_ID,
                     f"Новый пользователь: кв. {apartment}, "
                     f"счетчиков воды: {water_count}, "
                     f"тип счетчика электричества: {'двухтарифный' if elec_type == '2' else 'однотарифный'}")
    print(f'{datetime.now()} Новый пользователь. Квартира {apartment}')



# Переход в профиль
@bot.message_handler(commands=['account'])
def account(message):
    telegram_id = message.from_user.id
    user_exists = find_user_by_id('users', telegram_id, 'COUNT(*)')[0] > 0  # TODO: Проверить

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
    if now.day < start_collection[0] or now.day > end_collection[0]:
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

    # Создаем таблицу (если не существует)
    columns = [
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
    ]
    create_table('meters_data', columns)

    # Вставляем данные
    columns = [
        'telegram_id', 'apartment', 'month',
        'type_water_meter', 'type_electricity_meter',
        'cold_water_1', 'cold_water_2', 'cold_water_3',
        'hot_water_1', 'hot_water_2', 'hot_water_3',
        'electricity_1', 'electricity_2'
    ]
    values = [
        user.telegram_id,
        user.apartment,
        month,
        user.water_count,
        user.electricity_type,
        cw1, cw2, cw3,
        hw1, hw2, hw3,
        el1, el2
    ]
    insert_to_database('meters_data', columns, values)

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


@bot.message_handler(commands=['manager', 'accountant', 'electric', 'plumber'])
def handle_address_request(message):
    # Определяем тип получателя и текст запроса
    command = message.text.split('@')[0]
    recipient_data = {
        '/manager': {
            'id': MANAGER_ID,
            'request_text': "✉️ Напишите своё обращение к председателю ТСЖ",
            'message_type': 'Обращение председателю',
            'response_success': "✅ Обращение успешно отправлено председателю"
        },
        '/accountant': {
            'id': ACCOUNTANT_ID,
            'request_text': "✉️ Напишите своё обращение к бухгалтеру",
            'message_type': 'Обращение бухгалтеру',
            'response_success': "✅ Обращение успешно отправлено бухгалтеру"
        },
        '/electric': {
            'id': ELECTRIC_ID,
            'request_text': "✉️ Напишите текст заявки на работу электрика",
            'message_type': 'Новая заявка на работу слектрика',
            'response_success': "✅ Заявка на работу электрика успешно отправлена"
        },
        '/plumber': {
            'id': PLUMBER_ID,
            'request_text': "✉️ Напишите текст заявки на работу сантехника",
            'message_type': 'Новая заявка на работу сантехника',
            'response_success': "✅ Заявка на работу сантехника успешно отправлена"
        }
    }

    msg = bot.send_message(message.chat.id, recipient_data[command]['request_text'])
    bot.register_next_step_handler(msg, lambda m: send_address(m, recipient_data[command]))


def send_address(message, recipient_info):
    text = message.text.strip()
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or ""
    sender_surname = message.from_user.last_name or ""

    # Получаем номер квартиры из базы данных
    result = find_user_by_id("users", sender_id, "apartment")
    apartment = result[0] if result else "Неизвестна"

    # Формируем и отправляем сообщение
    bot.send_message(
        recipient_info['id'],
        f'📨 {recipient_info["message_type"]}:\n'
        f'👤 [{sender_name} {sender_surname}](tg://user?id={sender_id})\n'
        f'🏠 Квартира: {apartment}\n\n'
        f'_{text}_',
        parse_mode="Markdown"
    )

    # Отправляем подтверждение пользователю
    bot.send_message(message.chat.id, recipient_info['response_success'])

    # Логируем действие
    print(f'{datetime.now()} {recipient_info["message_type"]} отправлено. Кв. {apartment}, ID {sender_id}')



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
    while True:
        now = datetime.now()
        current_month = f"{now.month}.{now.year}"

        # Получаем всех пользователей из базы данных
        try:
            users = select_all("users")  # Используем функцию select_all из database.py
        except Exception as e:
            print('БД еще не создана')

        # ⏰ Уведомление о начале сбора показаний
        if now.day == start_collection[0] and now.hour == 8 and now.minute == 00:
            print(f"{now} Уведомление о начале сбора показаний")
            for user in users:
                telegram_id = user[0]  # Предполагаем, что telegram_id - первый столбец
                try:
                    bot.send_message(telegram_id, "📬 Открыт сбор показаний счетчиков")
                    print(f"{now} Уведомление отправлено {telegram_id}")
                except Exception as e:
                    print(f"{now} Ошибка отправки {telegram_id}: {e}")
            time.sleep(60)

        # ⏰ Уведомление о завершении сбора показаний
        if now.day == end_collection[0] and now.hour == end_collection[1] and now.minute == end_collection[2]:
            print(f"{now} Уведомление о завершении сбора")

            send_table(ACCOUNTANT_ID)


            for user in users:
                telegram_id, apartment, water_count, electricity_count = user[0], user[1], user[2], user[3]

                # Проверяем, передавал ли пользователь показания
                result = find_user_by_id("meters_data", telegram_id,
                                         "1")  # Используем функцию find_user_by_id из database.py
                if result:
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
            for user in users:
                telegram_id, apartment, water_count, electricity_count = user[0], user[1], user[2], user[3]

                # Проверяем, передавал ли пользователь показания
                result = find_user_by_id("meters_data", telegram_id,
                                         "1")  # Используем функцию find_user_by_id из database.py
                if result:
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

        time.sleep(60)

# Запуск
if __name__ == '__main__':

    now = datetime.now()
    print(f"{now} Бот запущен")
    threading.Thread(target=notifications, daemon=True).start()
    bot.polling(none_stop=True)
