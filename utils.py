from telebot import types
from datetime import datetime
from data import cold_water_meters, hot_water_meters, electricity_meters
from data import months


def get_month():
    now = datetime.now()
    return months[now.month], now.year


def create_meters_markup(user):
    markup = types.InlineKeyboardMarkup()
    counter = 1

    # Холодная вода
    for i in range(user.cold_water_count):
        text = cold_water_meters[user.cold_water_count][i]
        if f'c{counter}' in user.metrics:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    # Горячая вода (столько же счетчиков)
    for i in range(user.cold_water_count):
        text = hot_water_meters[user.cold_water_count][i]
        if f'c{counter}' in user.metrics:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    # Электричество
    elec_meters = electricity_meters[user.electricity_type]
    for i in range(len(elec_meters)):
        text = elec_meters[i]
        if f'c{counter}' in user.metrics:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    if user.all_metrics_entered():
        markup.add(types.InlineKeyboardButton("📤 Перейти к проверке", callback_data='review'))
    markup.add(types.InlineKeyboardButton("🚫 Отменить ввод", callback_data='cancel'))
    return markup


def create_review_markup(user):
    markup = types.InlineKeyboardMarkup()
    counter = 1

    # Холодная вода
    for i in range(user.cold_water_count):
        text = f"{cold_water_meters[user.cold_water_count][i]}: {user.metrics.get(f'c{counter}', '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    # Горячая вода
    for i in range(user.cold_water_count):
        text = f"{hot_water_meters[user.cold_water_count][i]}: {user.metrics.get(f'c{counter}', '—')}"
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