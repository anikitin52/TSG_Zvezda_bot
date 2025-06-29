from datetime import datetime

from config import ACCOUNTANT_ID

from data import current_editing, temp_users, cold_water_meters, hot_water_meters, electricity_meters, current_meters
from database import create_table, insert_to_database
from main import bot
from utils import get_month, create_meters_markup, create_review_markup


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