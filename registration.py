from telebot import types
from datetime import datetime

from data import user_data
from database import select_all, insert_to_database
from config import ADMIN_ID
from main import bot

tablename = 'users'

@bot.callback_query_handler(func=lambda call: call.data == 'register')
def register(call):
    msg = bot.send_message(call.message.chat.id, "Введите номер вашей квартиры (1–150):")
    bot.register_next_step_handler(msg, process_apartment)


def process_apartment(message):
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
    try: # TODO: Вынести в отдельную функцию
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