from telebot import types
from datetime import datetime
from data.data import cold_water_meters, hot_water_meters, electricity_meters, months


def get_month():
    """
    Получение текущего месяца
    :return: Текущий месяц, текцщий год
    """
    now = datetime.now()
    return months[now.month], now.year


def create_meters_markup(user):
    """
    Создание кнопок ввода счетчиков
    :param user: Пользователь (объект)
    :return: markup с конпками
    """
    markup = types.InlineKeyboardMarkup()
    counter = 1

    # Холодная вода
    for i in range(user.water_count):
        text = cold_water_meters[user.water_count][i]
        if f'c{counter}' in user.metrics:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    # Горячая вода (столько же счетчиков, сколько и холодной)
    for i in range(user.water_count):
        text = hot_water_meters[user.water_count][i]
        if f'c{counter}' in user.metrics:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    # Электричество
    elec_meters = electricity_meters[user.electricity_type]
    for meter in elec_meters:
        if f'c{counter}' in user.metrics:
            meter += " ✅"
        markup.add(types.InlineKeyboardButton(meter, callback_data=f'meter_{counter}'))
        counter += 1

    if user.all_metrics_entered():
        markup.add(types.InlineKeyboardButton("📤 Перейти к проверке", callback_data='review'))
    markup.add(types.InlineKeyboardButton("🚫 Отменить ввод", callback_data='cancel'))
    return markup


def create_review_markup(user):
    """
    Создание кнопок ввода счетчиков при проверке введенных данных
    :param user: Пользователь (объект)
    :return: markup из кнопок
    """
    markup = types.InlineKeyboardMarkup()
    counter = 1

    # Холодная вода
    for i in range(user.water_count):
        text = f"{cold_water_meters[user.water_count][i]}: {user.metrics.get(f'c{counter}', '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    # Горячая вода
    for i in range(user.water_count):
        text = f"{hot_water_meters[user.water_count][i]}: {user.metrics.get(f'c{counter}', '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    # Электричество
    elec_meters = electricity_meters[user.electricity_type]
    for i in range(len(elec_meters)):
        text = f"{elec_meters[i]}: {user.metrics.get(f'c{counter}', '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    markup.row(
        types.InlineKeyboardButton("✅ Подтвердить все", callback_data='confirm_all'),
        types.InlineKeyboardButton("↩️ Назад к редактированию", callback_data='back_edit')
    )
    return markup