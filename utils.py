from telebot import types
from datetime import datetime
from main import meters4, meters6

#
months = {
    1: 'январь', 2: 'февраль', 3: 'март', 4: 'апрель',
    5: 'май', 6: 'июнь', 7: 'июль', 8: 'август',
    9: 'сентябрь', 10: 'октябрь', 11: 'ноябрь', 12: 'декабрь'
}

def get_month():
    now = datetime.now()
    return months[now.month], now.year

# Создание кнопок для ввода показаний
def create_meters_markup(user):
    markup = types.InlineKeyboardMarkup()
    for i in range(1, user.meters_count + 1):
        if user.meters_count == 4:
            text = meters4[i-1]
        elif user.meters_count == 6:
            text = meters6[i-1]
        if f'c{i}' in user.metrics:
            text += " ✅"

        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{i}'))
    if user.all_metrics_entered():
        markup.add(types.InlineKeyboardButton("📤 Перейти к проверке", callback_data='review'))
    markup.add(types.InlineKeyboardButton("🚫 Отменить ввод", callback_data='cancel'))
    return markup

# Создание кнопок для записи показаний
def create_review_markup(user):
    markup = types.InlineKeyboardMarkup()
    for i in range(1, user.meters_count + 1):
        if user.meters_count == 4:
            text = f"{meters4[i-1]}: {user.metrics.get(f'c{i}', '—')}"
        elif user.meters_count == 6:
            text = f"{meters6[i-1]}: {user.metrics.get(f'c{i}', '—')}"

        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{i}'))
    markup.row(
        types.InlineKeyboardButton("✅ Подтвердить все", callback_data='confirm_all'),
        types.InlineKeyboardButton("↩️ Назад к редактированию", callback_data='back_edit')
    )
    return markup