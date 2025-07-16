from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import threading
import time
import shutil
import os

from config import *
from data.models import User, Appeal
from services.utils import *
from data.data import *
from services.exel_export import send_table
from data.database import *
from services.logger import logger

bot = TeleBot(BOT_TOKEN)
now = datetime.now()


@bot.message_handler(commands=['start'])  # Запуск бота
def start(message):
    """
    Обработка команды /start -> Запуск бота. Начало регистрации пользователя.
    :param message: Сообщение от пользователя - Команда /start
    :return: None
    """

    tablename = 'users'
    user_id = message.from_user.id

    # Проверяем наличие пользователя
    user = find_user_by_id(tablename, user_id)
    if user:
        apartment = user[2]
        bot.send_message(message.chat.id, f"✅ Вы уже зарегистрированы! Квартира: {apartment}")
    else:
        # Пользователь не найден. Начинаем регистрацию
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data='register'))
        bot.send_message(message.chat.id, "👋 Добро пожаловать! Для начала зарегистрируйтесь:", reply_markup=markup)
        logger.info(f'Пользователь {message.from_user.id} запустил бота')


@bot.callback_query_handler(func=lambda call: call.data == 'register')
def add_apartment_number(call):
    """
    Обработка нажатия кнопки "Зарегистрироваться" -> Требование ввода номера квартиры
    :param call: Обработчик запроса
    :return: None
    """

    # Ввод номера квартиры
    msg = bot.send_message(call.message.chat.id, "Введите номер вашей квартиры (1–150):")
    bot.register_next_step_handler(msg, register_apartment)


def register_apartment(message):
    """
    Проверка корректности ввода номера квартиры
    Проверка наличия квартиры в БД -> Запрос ввода колисества счетчиков
    :param message: Сообщение, введенное пользователем
    :return: None
    """
    # Проверка корректности номера квартиры
    try:
        apartment = int(message.text.strip())
        if not 1 <= apartment <= 150:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 150")
        bot.register_next_step_handler(msg, add_apartment_number)
        return

    # Проверка наличия квартиры в БД
    tablename = 'users'
    users = select_all(tablename)
    user_id = message.from_user.id
    if any(u[2] == apartment for u in users):
        bot.send_message(message.chat.id, "❌ Квартира уже зарегистрирована")
        return

    # Ввод количества счетчиков воды
    user_data[user_id] = {'apartment': apartment}
    msg = bot.send_message(message.chat.id, "Введите количество счетчиков холодной воды (от 1 до 3):")
    bot.register_next_step_handler(msg, check_water_meters)


def check_water_meters(message):
    """
    Проверка корректности ввода количества счетчиков воды
    Создание кнопок выбора типа электрочсетчика
    :param message: Сообщение от пользователя
    :return: None
    """
    # Проверка корректности ввода счетчиков
    try:
        water_meters = int(message.text.strip())
        if not 1 <= water_meters <= 3:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
        bot.register_next_step_handler(msg, check_water_meters)
        return

    # Сохраняем данные о квартире
    user_id = message.from_user.id
    apartment = user_data[user_id]['apartment']
    user_data[user_id] = {
        'water_count': water_meters,
        'apartment': apartment
    }

    # Кнопки выбора счетчика электричества
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton('Однотарифный', callback_data=f'elec_1_{water_meters}_{apartment}'),
        types.InlineKeyboardButton('Двухтарифный', callback_data=f'elec_2_{water_meters}_{apartment}')
    )
    bot.send_message(message.chat.id, "Выберите тип счетчика электричества", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('elec_'))
def select_meters(call):
    """
    Завершение регистрации польщователя, добавление в БД
    :param call: Обработчик запроса
    :return: None
    """
    parts = call.data.split('_')
    elec_type = parts[1]  # 1 или 2
    water_count = parts[2]
    user_id = call.from_user.id
    tablename = 'users'

    # Получаем сохраненные данные
    apartment = user_data[user_id]['apartment']

    # Вставляем запись о квартире в БД
    insert_to_database(tablename,
                       ['telegram_id', 'apartment', 'water_count', 'electricity_count'],
                       [user_id, int(apartment), int(water_count), int(elec_type)])

    del user_data[user_id]
    logger.info(f'Новый пользователь: {user_id}. Квартира {apartment}')
    bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")
    ADMIN_ID = find_staff_id('Админ')
    bot.send_message(ADMIN_ID,
                     f"Новый пользователь: кв. {apartment}, \n"
                     f"счетчиков воды: {water_count}, \n"
                     f"тип счетчика электричества: {'двухтарифный' if elec_type == '2' else 'однотарифный'}")


@bot.message_handler(commands=['export'])
def export_data(message):
    """
    Обработка команды /export -> Отправка пользователю таблицы с данными
    :param message: Сообщение от пользователя - команда -> /export
    :return: None
    """
    ACCOUNTANT_ID = find_staff_id('Бухгалтер')
    if message.chat.id != ACCOUNTANT_ID:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
        return
    else:
        logger.info(f'Пользоватлель {message.chat.id} экспортировал Exel-таблицу')
        send_table(message.chat.id)

@bot.message_handler(commands=['backup'])
def backup(message):
    admin = find_staff_id('Админ')
    if message.from_user.id != admin:
        bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
        return
    else:
        backup_daily()
        backup_monthly()

@bot.message_handler(commands=['info'])
def info(message):
    """
    Выводит информацию о доступных польщователю командах
    :param message: Сообщение от пользователя - команда /info
    :return: None
    """
    result = "Список доступных вам команд: \n"
    user_status = 'user'
    result += '''
    /send - Передать показания счетчиков \n
    /manager - Отправить обращение к председателю \n
    /accountant - Отправить обращение к бухгалтеру \n
    /electric - Подать заявки на работу электрика \n
    /plumber - Подать заявки на работу сантехника \n
    /account - Переход в профиль квартиры \n
    '''
    staff_id = [
        find_staff_id('Админ'),
        find_staff_id('Председатель'),
        find_staff_id('Бухгалтер')
    ]
    for id in staff_id:
        if message.from_user.id == id:
            user_status = 'staff'

    if user_status == 'staff':
        result += "Специальные команды, доступныке вам \n"
        if message.from_user.id == staff_id[0]:
            result += "/backup - Сохранить резервную копию базы данных \n"
        if message.from_user.id == staff_id[1]:
            pass
        if message.from_user.id == staff_id[2]:
            result += '/export - Получить Exel-таблицу с показаниями счетчиков \n'

    bot.send_message(message.chat.id, result)


@bot.message_handler(commands=['account'])
def account(message):
    """
    Обработка команды /account -> Вывод данных об акаунте пользователя
    :param message: Сообщение от ползователя - команда /account
    :return: None
    """
    # Проверка наличия пользователя
    telegram_id = message.from_user.id
    user_exists = find_user_by_id('users', telegram_id, 'COUNT(*)')[0] > 0
    if not user_exists:
        bot.send_message(
            message.chat.id,
            "❌ Вы не зарегистрированы. Для начала нажмите /start"
        )
        return

    # Вывод информации о пользователе
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
        logger.info(f'Пользователь {message.from_user.id} Просматривает профиль')
    else:
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при получении данных профиля"
        )


@bot.message_handler(commands=['auth'])
def auth(message):
    """
    Обработка команды /aunh -> Запуск процесса авторизации сотрудника
    :param message: Сообщение от пользователя - команда /auth
    :return: None
    """
    msg = bot.send_message(message.chat.id, 'Введите код авторизации')
    bot.register_next_step_handler(msg, enter_auth_code)


def enter_auth_code(message):
    """
    Проверка кода авторизации -> атворизация сотруудника
    :param message: Сообщение от пользователя - код авторицации
    :return: None
    """
    user_id = message.from_user.id
    user_name = f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}'
    auth_code = message.text.strip()

    # Получение кода авторизации из БД
    staff_list = select_all('staff')
    for post in staff_list:
        staff_post = post[1]
        code = post[4]
        if auth_code == code:
            update_values('staff',
                          {'telegram_id': user_id, 'name': user_name},
                          {'auth_code': auth_code}
                          )
            bot.send_message(message.chat.id, f'Вы успешно авторизованы как {staff_post}')
            logger.info(f'Пользоватлеь {message.chat.id} авторизован как {staff_post}')
            bot.send_message(find_staff_id('Админ'),
                             f"⚠️Пользователь {message.from_user.id}: {message.from_user.first_name} {message.from_user.last_name} авторизован как {staff_post}")
            return
        else:
            continue
    else:
        msg = bot.send_message(message.chat.id, "Неверный код авторизации")
        logger.info(f'Пользователь {message.from_user.id} ввел неверный код авторизации')
        bot.register_next_step_handler(msg, enter_auth_code)


@bot.message_handler(commands=['send'])
def send_data(message):
    """
    Запуск процесса отправки показаний
    :param message: Сообщение от пользователя - команда /send
    :return: None
    """
    # Проверка времени отправки
    if not (start_collection[0] <= now.day <= end_collection[0] and
            not (now.day == end_collection[0] and
                 (now.hour > end_collection[1] or
                  (now.hour == end_collection[1] and now.minute > end_collection[2])))):
        bot.send_message(message.chat.id,
                         "❌ Прием показаний закрыт. Показания принимаются с 23 по 27 число каждого месяца")
        return

    # Проверка того, что пользователь еще не отправлял показания в этом месяце
    telegram_id = message.from_user.id
    user = find_user_by_id('meters_data', telegram_id)
    if user:
        bot.send_message(message.chat.id, '✅ Вы уже передали показания в этом месяце')
        return

    # Проверка зарегистрирован ли пользователь
    if telegram_id in temp_users:
        user = temp_users[telegram_id]
    else:
        # Пользователь не зарегистрирован
        user_data = find_user_by_id('users', telegram_id, 'apartment, water_count, electricity_count')
        if not user_data:
            bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
            return

        # Пользователь зарегистрирован. Принимаем данные
        apartment, water_count, electricity_count = user_data
        user = User(telegram_id, apartment, water_count, electricity_count)
        temp_users[telegram_id] = user

    # Кнопки для вывбора счетчика
    month, year = get_month()
    markup = create_meters_markup(user)
    bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('meter_'))
def meter_input(call):
    """
    Ввод показаний для выбранного счетчика
    :param call: Вызов функции для конкретного счетчика
    :return: None
    """
    # Ввод показаний для выбранного счетчика
    meter = call.data.split('_')[1]
    current_editing[call.from_user.id] = meter
    msg = bot.send_message(call.message.chat.id, f"Введите показания для выбранного счетчика:")
    bot.register_next_step_handler(msg, process_value)


def process_value(message):
    """
    Обработка ввода данных
    :param message: Сообщение от пользователя - целое число
    :return: None
    """
    telegram_id = message.from_user.id
    user = temp_users.get(telegram_id)
    meter = current_editing.get(telegram_id)

    # Проверка на наличие ошибки
    if not user or not meter:
        bot.send_message(message.chat.id, "Ошибка: пользователь или счётчик не найдены")
        return

    # Проверка корректности ввода
    try:
        value = int(message.text.strip())
        if value < 0:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Введите положительное число")
        bot.register_next_step_handler(msg, process_value)
        return

    # Ввод данных
    user.add_metric(meter, value)
    # Создание нового сообщения с кнопками
    month, year = get_month()
    markup = create_meters_markup(user)
    bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'review')
def review(call):
    """
    Проверка введенных данных
    :param call: Вызов функции с требованием проверки данных
    :return: None
    """
    # Проверка наличия пользователя
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return

    # Создание сообщения с проверкой
    markup = create_review_markup(user)
    month, year = get_month()
    bot.send_message(call.message.chat.id, f"📝 Проверка за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_value(call):
    """
    Изменение значений
    :param call: Вызов функции с требованием изменить ранее введенные значения
    :return: None
    """
    # Корректировка значений
    meter = call.data.split('_')[1]
    current_editing[call.from_user.id] = meter
    msg = bot.send_message(call.message.chat.id, f"Введите новое значение для выбранного счетчика")
    bot.register_next_step_handler(msg, process_value)


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_all')
def confirm_all(call):
    """
    Обработка введенных показаний. Запись в БД
    :param call: вызов функции с требованием записать данные
    :return: None
    """
    # Проверка существования пользователя
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return

    # Получение отчета
    report = user.get_report()

    # Получаем имена счетчиков
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

    month = now.strftime('%m.%Y')

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

    # Отправка отчета
    ACCOUNTANT_ID = find_staff_id('Бухгалтер')
    bot.send_message(ACCOUNTANT_ID, f"📨 Показания от кв. {user.apartment}:\n{report}")
    user.clear_metrics()
    temp_users.pop(call.from_user.id, None)
    bot.send_message(call.message.chat.id, "✅ Показания отправлены")
    logger.info(f'Показания переданы. Квартира {user.apartment}')


@bot.callback_query_handler(func=lambda call: call.data == 'back_edit')
def back_edit(call):
    """
    Возврат к редактированию ранее введенных данных
    :param call: вызов функции с требованием редактирования данных
    :return: None
    """
    # Проверка существования пользователя
    user = temp_users.get(call.from_user.id)
    if not user:
        bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
        return

    # Создание сообщения с кнопками
    markup = create_meters_markup(user)
    month, year = get_month()
    bot.send_message(call.message.chat.id, f"📊 Возврат к редактированию за {month} {year}", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel(call):
    """
    Отмена ввода показаний
    :param call: Вызов функции с требованием отмены ввода показаний
    :return: None
    """
    # Отмена ввода
    user = temp_users.get(call.from_user.id)
    if user:
        user.clear_metrics()
        temp_users.pop(call.from_user.id, None)

    bot.send_message(call.message.chat.id, "🚫 Ввод отменён")


@bot.message_handler(commands=['manager', 'accountant', 'electric', 'plumber'])
def handle_address_request(message):
    """
    Выбор получателя обращения / заявки на работу
    :param message: Сообщение от польщователя - команда, соотвествующая получателю обращения
    :return: None
    """
    # Определяем тип получателя и текст запроса
    command = message.text.split('@')[0]
    MANAGER_ID = find_staff_id('Председатель')
    ACCOUNTANT_ID = find_staff_id('Бухгалтер')
    PLUMBER_ID = find_staff_id('Сантехник')
    ELECTRIC_ID = find_staff_id('Электрик')
    recipient_data = {
        '/manager': {
            'id': MANAGER_ID,
            'request_text': "✉️ Напишите своё обращение к председателю ТСЖ",
            'recipient': "Председатель",
            'message_type': 'Обращение председателю',
            'response_success': "✅ Обращение успешно отправлено председателю"
        },
        '/accountant': {
            'id': ACCOUNTANT_ID,
            'request_text': "✉️ Напишите своё обращение к бухгалтеру",
            'recipient': "Бухгалтер",
            'message_type': 'Обращение бухгалтеру',
            'response_success': "✅ Обращение успешно отправлено бухгалтеру"
        },
        '/electric': {
            'id': ELECTRIC_ID,
            'request_text': "✉️ Напишите текст заявки на работу электрика",
            'recipient': "Электрик",
            'message_type': 'Заявка на работу слектрика',
            'response_success': "✅ Заявка на работу электрика успешно отправлена"
        },
        '/plumber': {
            'id': PLUMBER_ID,
            'request_text': "✉️ Напишите текст заявки на работу сантехника",
            'recipient': "Сантехник",
            'message_type': 'Заявка на работу сантехника',
            'response_success': "✅ Заявка на работу сантехника успешно отправлена"
        }
    }

    msg = bot.send_message(message.chat.id, recipient_data[command]['request_text'])
    bot.register_next_step_handler(msg, lambda m: send_address(m, recipient_data[command]))


def send_address(message, recipient_info):
    """
    Запись обращения в БД, отправка получателю
    :param message: Сообщение от пользователя - текст обращения
    :param recipient_info: Информация о получателе обращения
    :return: None
    """
    text = message.text.strip() if message.text else ""
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or ""
    sender_surname = message.from_user.last_name or ""

    # Получаем номер квартиры из базы данных
    result = find_user_by_id("users", sender_id, "apartment")
    apartment = result[0] if result else "Неизвестна"

    ap = Appeal(
        sender_id=message.from_user.id,
        apartment=apartment,
        message_text=text,
        recirient_post=recipient_info['recipient']
    )

    # Сохраняем обращение в базу данных
    insert_to_database('appeals',
                       ['sender_id', 'apartment', 'message_text', 'recipient_post'],
                       [ap.sender_id, ap.apartment, ap.message_text, ap.recipient_post]
                       )

    # Кнопка отправки сообщения
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "Ответить",
        callback_data=f"reply_{sender_id}_{message.message_id}"
    ))

    # Формируем и отправляем сообщение
    bot.send_message(
        recipient_info['id'],
        f'📨 Обращение от жителя:\n'
        f'👤 [{sender_name} {sender_surname}](tg://user?id={sender_id})\n'
        f'🏠 Квартира: {apartment}\n\n'
        f'_{text}_',
        parse_mode="Markdown",
        reply_markup=markup
    )
    logger.info(f"Отправлено обращение от пользователя{sender_id}. Получатель {recipient_info['recipient']}")

    # Отправляем подтверждение пользователю
    bot.send_message(message.chat.id, recipient_info['response_success'])

    # Логируем действие
    logger.info(f'{recipient_info["message_type"]} отправлено. Кв. {apartment}, ID {sender_id}')


@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def start_staff_reply(call):
    """
    Запрос ответа на обращение от сотрудника
    :param call: вызов функции с требованием ответа на обращение
    :return: None
    """
    _, user_id, message_id = call.data.split('_')
    active_dialogs[call.from_user.id] = (int(user_id), int(message_id))

    bot.send_message(
        call.from_user.id,
        "✍️ Введите ваш ответ:",
        reply_markup=types.ForceReply(selective=True)
    )


@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text == "✍️ Введите ваш ответ:")
def process_staff_reply(message):
    """
    Запись ответа в БД. Отправка ответа пользователю
    :param message: Сообщение от сотрудника - ответ на обращение
    :return: None
    """
    staff_id = message.from_user.id
    if staff_id not in active_dialogs:
        return

    MANAGER_ID = find_staff_id('Председатель')
    ACCOUNTANT_ID = find_staff_id('Бухгалтер')
    PLUMBER_ID = find_staff_id('Сантехник')
    ELECTRIC_ID = find_staff_id('Электрик')

    user_id, original_message_id = active_dialogs[staff_id]
    if staff_id == MANAGER_ID:
        staff_position = "председателя ТСЖ"
    elif staff_id == ACCOUNTANT_ID:
        staff_position = "бухгалтера"
    elif staff_id == ELECTRIC_ID:
        staff_position = "электрика"
    elif staff_id == PLUMBER_ID:
        staff_position = "сантехника"
    else:
        staff_position = "администрации"

    # Отправляем ответ пользователю
    bot.send_message(user_id, f"📩 Ответ {staff_position} на ваше обращение:\n\n{message.text}")

    # Обновляем статус в БД
    update_values('appeals',
                  {'status': 'closed', 'answer_text': message.text},
                  {'sender_id': user_id, 'status': 'open'}
                  )
    logger.info(f'Ответ {staff_position} на обращение')
    bot.send_message(staff_id, "✅ Ответ отправлен")
    del active_dialogs[staff_id]


def notifications():
    """
    Оработчик напоминаний
    1. Уведомление о начале сбора показаний (для всех)
    2. Напоминание во время сбора показаний (для тех, кто не еще не передал)
    3. Уведомление о завершении сбора (для тех, кто не передал)
        3.1. Отправка отчета бухгалтеру
    :return: None
    """
    scheulder = BackgroundScheduler()
    scheulder.add_job(backup_daily, 'cron', hour=2, minute=0)

    while True:
        now = datetime.now()
        current_month = f"{now.month}.{now.year}"

        # Начало сбора показаний
        if now.day == start_collection[0] and now.hour == start_collection[1] and now.minute == start_collection[2]:
            users = select_all('users')
            logger.info("Открыт сбор показаний счетчиков")
            if not scheulder.running:
                scheulder.start()
            for user in users:
                bot.send_message(user[1], "📬 Открыт сбор показаний счетчиков")

        # Напоминание о передаче
        if now.day == notification_time[0] and now.hour == notification_time[1] and now.minute == notification_time[2]:
            users = select_all('users')
            sended_data = select_all('meters_data')
            apartments = []
            for data in sended_data:
                apartments.append(data[2])
            for user in users:
                users_apartment = user[2]
                user_id = user[1]
                if users_apartment not in apartments:
                    bot.send_message(user_id, "⏰ Пора передать показания счетчиков! /send")
                    logger.info(f"Напоминание отправлено пользователю {user_id}")

        # Завершение сбора
        if now.day == end_collection[0] and now.hour == end_collection[1] and now.minute == end_collection[2]:
            users = select_all('users')
            sended_data = select_all('meters_data')
            apartments = []
            for data in sended_data:
                apartments.append(data[2])
            for user in users:
                users_apartment = user[2]
                user_id = user[1]
                if users_apartment not in apartments:
                    logger.info(f"Уведомление о закрытии сбора отправлено {user_id}")
                    bot.send_message(user_id, "🔴 Прием показаний закрыт до следующего месяца")

            ACCOUNTANT_ID = find_staff_id('Бухгалтер')
            send_table(ACCOUNTANT_ID)
            logger.info('Таблица отправвлена бухгалтеру')
            if scheulder.running:
                scheulder.shutdown()
            clear_table('meters_data')
            backup_monthly()
            logger.warning('Таблица показаний очищена')

        time.sleep(60)


def init_db():
    """
    Инициализация БД при запуске бота
    :return: None
    """
    create_table('users', [
        "telegram_id INTEGER UNIQUE",
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
        'message_text TEXT',
        'recipient_post TEXT',
        'answer_text TEXT',
        "status TEXT DEFAULT 'open'",
    ])
    create_table('staff', [
        'post TEXT',
        'telegram_id INTEGER',
        'name TEXT',
        'auth_code TEXT'
    ])


def init_staff():
    """
    Заполениние таблицы сотрудников
    :return: None
    """
    tablename = 'staff'
    table = select_all(tablename)
    if table:
        return
    columns = ['post', 'auth_code']
    insert_to_database(tablename, columns, ['Админ', ADMIN_CODE])
    insert_to_database(tablename, columns, ['Председатель', MANAGER_CODE])
    insert_to_database(tablename, columns, ['Бухгалтер', ACCOUNTANT_CODE])
    insert_to_database(tablename, columns, ['Сантехник', PLUMBER_CODE])
    insert_to_database(tablename, columns, ['Электрик', ELECTRIC_CODE])


def backup_daily(db_path="tsg_database.sql", backup_dir="backups/daily"):
    """
    Создаёт ежедневную резервную копию базы данных.
    Старый бэкап удаляется, создаётся новый.
    """
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, "backup_daily.sql")

    # Удалить старый бэкап, если есть
    if os.path.exists(backup_path):
        os.remove(backup_path)

    shutil.copy2(db_path, backup_path)
    logger.info(f"[✓] Ежедневная резервная копия создана: {backup_path}")
    bot.send_message(find_staff_id('Админ'), "Резервная копия создана (день)")


def backup_monthly(db_path="tsg_database.sql", backup_dir="backups/monthly"):
    """
    Создаёт ежемесячную резервную копию базы данных.
    Хранится отдельно, не перезаписывается.
    """
    os.makedirs(backup_dir, exist_ok=True)
    month_str = datetime.now().strftime("%Y-%m")  # Используем уже импортированный datetime
    backup_path = os.path.join(backup_dir, f"backup_{month_str}.sql")

    if not os.path.exists(backup_path):
        shutil.copy2(db_path, backup_path)
        logger.info(f"[✓] Ежемесячная резервная копия создана: {backup_path}")
        bot.send_message(find_staff_id('Админ'), "Резервная копия создана (месяц)")
    else:
        logger.info(f"[!] Ежемесячная копия уже существует: {backup_path}")
        bot.send_message(find_staff_id('Админ'), "Ежемесячная копия уже существует")


# Запуск
if __name__ == '__main__':
    init_db()
    init_staff()
    now = datetime.now()
    logger.info('Бот запущен')
    threading.Thread(target=notifications, daemon=True).start()
    bot.polling(none_stop=True)
