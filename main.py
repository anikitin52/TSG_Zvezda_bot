from config import BOT_TOKEN, ADMIN_ID, ADMIN_CODE
from telebot import TeleBot, types
from datetime import date, datetime
import schedule
import threading
import time

bot = TeleBot(BOT_TOKEN)

# Хранилище данных: {user_id: apartment_number}
registered_users = {}
flats = {}  # {flat : meters_count }

user_metrics = {}  # {user_id: {'c1': value, 'c2': value, ...}}
current_editing = {}  # {user_id: current_editing_counter}

current_datetime = datetime.now()
print(current_datetime)
months = {
    1: 'январь',
    2: 'февраль',
    3: 'март',
    4: 'апрель',
    5: 'май',
    6: 'июнь',
    7: 'июль',
    8: 'август',
    9: 'сентябрь',
    10: 'октябрь',
    11: 'ноябрь',
    12: 'декабрь'
}
user_metrics = {}  # {user_id: {'c1': value, 'c2': value, ...}}
current_editing = {}  # {user_id: current_editing_counter}


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if user_id in registered_users:
        bot.send_message(message.chat.id, f"Вы уже зарегистрированы! Ваш номер квартиры: {registered_users[user_id]}")
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Зарегистрироваться", callback_data='register'))
        bot.send_message(message.chat.id, "Добро пожаловать!", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == 'register')
def register_callback(call):
    user_id = call.from_user.id
    if user_id in registered_users:
        bot.send_message(call.message.chat.id, "Вы уже зарегистрированы!")
        return

    msg = bot.send_message(call.message.chat.id, "Введите номер вашей квартиры (от 1 до 150):")
    bot.register_next_step_handler(msg, process_apartment_step)


def process_apartment_step(message):
    user_id = message.from_user.id

    try:
        apartment = int(message.text.strip())
        if apartment < 1 or apartment > 150:
            raise ValueError("Некорректный номер")
    except:
        msg = bot.send_message(message.chat.id, "❌ Некорректный ввод! Введите целое число от 1 до 150")
        bot.register_next_step_handler(msg, process_apartment_step)
        return

    if apartment in registered_users.values():
        bot.send_message(message.chat.id, f"❌ Квартира №{apartment} уже зарегистрирована!")
        return

    # Создаем inline-клавиатуру для выбора счетчиков
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("3 счетчика", callback_data=f"meters_3_{apartment}"),
        types.InlineKeyboardButton("5 счетчиков", callback_data=f"meters_5_{apartment}")
    )
    bot.send_message(message.chat.id, "Выберите количество счетчиков:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('meters_'))
def handle_meters_choice(call):
    _, count, apartment = call.data.split('_')
    apartment = int(apartment)
    count = int(count)
    user_id = call.from_user.id

    # Проверяем, не занята ли квартира (на случай параллельной регистрации)
    if apartment in flats:
        bot.send_message(call.message.chat.id, "❌ Эта квартира уже была зарегистрирована другим пользователем!")
        return

    # Регистрируем пользователя
    registered_users[user_id] = apartment
    flats[apartment] = count

    bot.send_message(call.message.chat.id,
                     f"✅ Регистрация успешна!\n"
                     f"Квартира: {apartment}\n"
                     f"Счетчиков: {count}\n"
                     f"Перейти в профиль: /account")

    # Уведомление админу
    bot.send_message(ADMIN_ID, f"Новый пользователь!\nКвартира: {apartment}\nСчетчиков: {count}")

@bot.message_handler(commands=['account'])
def account(message):
    user_id = message.from_user.id
    if user_id in registered_users:
        apartment = registered_users[user_id]
        bot.send_message(message.chat.id,
                         f"Ваш профиль:\n"
                         f"Квартира: {apartment}\n"
                         f"Счетчиков: {flats[apartment]}")
    else:
        bot.send_message(message.chat.id, "Вы еще не зарегистрированы! Нажмите /start")


def create_meters_markup(user_id, count):
    markup = types.InlineKeyboardMarkup()
    metrics = user_metrics.get(user_id, {})

    buttons = []
    for i in range(1, count + 1):
        btn_text = f"Счетчик {i}"
        if f'c{i}' in metrics:
            btn_text += " ✓"
        buttons.append(types.InlineKeyboardButton(btn_text, callback_data=f'meter_{i}'))

    if count == 3:
        markup.row(buttons[0], buttons[1])
        markup.row(buttons[2])
    elif count == 5:
        markup.row(buttons[0], buttons[1])
        markup.row(buttons[2], buttons[3])
        markup.row(buttons[4])

    # Изменяем условие для перехода к проверке
    if all(f'c{i}' in metrics for i in range(1, count + 1)):
        markup.row(types.InlineKeyboardButton("📤 Перейти к проверке", callback_data='review'))

    markup.row(types.InlineKeyboardButton("🚫 Отменить ввод", callback_data='cancel'))

    return markup


def create_review_markup(user_id, count):
    markup = types.InlineKeyboardMarkup()
    metrics = user_metrics.get(user_id, {})

    # Создаем кнопки для редактирования
    for i in range(1, count + 1):
        btn_text = f"Счетчик {i}: {metrics.get(f'c{i}', '—')}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f'edit_{i}'))

    # Кнопки подтверждения/отмены
    markup.row(
        types.InlineKeyboardButton("✅ Подтвердить все", callback_data='confirm_all'),
        types.InlineKeyboardButton("↩️ Назад к редактированию", callback_data='back_edit')
    )
    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def handle_edit(call):
    user_id = call.from_user.id
    meter_num = call.data.split('_')[1]
    current_editing[user_id] = meter_num

    # Запрашиваем новое значение
    msg = bot.send_message(
        call.message.chat.id,
        f"Введите новое значение для счетчика {meter_num}:"
    )
    bot.register_next_step_handler(msg, process_meter_value)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data == 'confirm_all')
def handle_final_confirm(call):
    user_id = call.from_user.id
    metrics = user_metrics.get(user_id, {})

    # Формируем отчет
    report = "\n".join([f"Счетчик {i}: {metrics.get(f'c{i}', '—')}"
                        for i in range(1, flats[registered_users[user_id]] + 1)])

    # Отправляем админу
    bot.send_message(
        ADMIN_ID,
        f"📨 Новые показания от квартиры {registered_users[user_id]}:\n{report}"
    )

    # Очищаем данные
    if user_id in user_metrics:
        del user_metrics[user_id]

    # Уведомляем пользователя
    bot.send_message(call.message.chat.id, "✅ Показания успешно отправлены!")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == 'back_edit')
def handle_back_edit(call):
    show_meters_menu(call.message.chat.id, call.from_user.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass



def show_review_menu(chat_id, user_id):
    apartment = registered_users[user_id]
    count = flats[apartment]
    now = datetime.now()
    month = months[now.month]

    markup = create_review_markup(user_id, count)
    bot.send_message(
        chat_id,
        f"📝 Проверьте показания за {month} {now.year}:\n"
        "Нажмите на счетчик для изменения значения",
        reply_markup=markup
    )



@bot.callback_query_handler(func=lambda call: call.data.startswith('meter_'))
def handle_meter_select(call):
    user_id = call.from_user.id
    meter_num = call.data.split('_')[1]
    current_editing[user_id] = meter_num

    # Запрашиваем ввод показаний
    msg = bot.send_message(call.message.chat.id,
                           f"Введите показания для счетчика {meter_num} (только число):")
    bot.register_next_step_handler(msg, process_meter_value)

def process_meter_value(message):
    user_id = message.from_user.id
    meter_num = current_editing.get(user_id)

    try:
        value = int(message.text.strip())
        if value < 0:
            raise ValueError
    except:
        msg = bot.send_message(message.chat.id, "❌ Некорректное значение! Введите целое положительное число:")
        bot.register_next_step_handler(msg, process_meter_value)
        return

    # Сохраняем значение
    if user_id not in user_metrics:
        user_metrics[user_id] = {}
    user_metrics[user_id][f'c{meter_num}'] = value
    del current_editing[user_id]

    # Показываем обновленное меню
    show_meters_menu(message.chat.id, user_id)

def show_meters_menu(chat_id, user_id):
    if user_id not in registered_users:
        return

    apartment = registered_users[user_id]
    count = flats[apartment]
    now = datetime.now()
    month = months[now.month]

    markup = create_meters_markup(user_id, count)
    bot.send_message(chat_id,
                     f"📊 Передача показаний за {month} {now.year}\n"
                     f"Выберите счетчик:",
                     reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ['confirm', 'cancel'])
def handle_actions(call):
    user_id = call.from_user.id
    if call.data == 'confirm':
        # Формируем сообщение для админа
        metrics = user_metrics.get(user_id, {})
        report = "\n".join([f"{k}: {v}" for k, v in metrics.items()])
        bot.send_message(ADMIN_ID,
                         f"Новые показания от квартиры {registered_users[user_id]}:\n{report}")

        # Очищаем данные
        if user_id in user_metrics:
            del user_metrics[user_id]
        bot.send_message(call.message.chat.id, "✅ Показания успешно отправлены!")

    elif call.data == 'cancel':
        # Сбрасываем данные
        if user_id in user_metrics:
            del user_metrics[user_id]
        bot.send_message(call.message.chat.id, "🚫 Ввод показаний отменен")

    # Удаляем предыдущее сообщение с кнопками
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == 'review')
def handle_review(call):
    show_review_menu(call.message.chat.id, call.from_user.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

@bot.message_handler(commands=['send'])
def send_data(message):
    user_id = message.from_user.id
    if user_id not in registered_users:
        bot.send_message(message.chat.id, "❌ Вы не зарегистрированы! Начните с /start")
        return

    apartment = registered_users[user_id]
    if apartment not in flats:
        bot.send_message(message.chat.id, "⚠️ Данные о ваших счетчиках не найдены! Пройдите регистрацию заново /start")
        return

    count = flats[apartment]
    show_meters_menu(message.chat.id, user_id)


def check_monthly_notification():
    """Проверяем, нужно ли отправлять уведомление"""
    while True:
        now = datetime.now()
        # Проверяем 25 число месяца и время 18:00
        if now.day == 25 and now.hour == 18 and now.minute == 00:
            send_notification()
            # Ждем 1 час, чтобы не отправить повторно
            time.sleep(3600)
        else:
            # Проверяем каждую минуту
            time.sleep(60)


def send_notification():
    """Функция для рассылки сообщения всем пользователям"""
    if not registered_users:
        print("Нет пользователей для рассылки")
        return

    message = "📢 Ежемесячное уведомление! Пожалуйста, передайте показания счетчиков. \n Чтобы передать показания счетчиков перейдите в раздел /send"

    for user_id in registered_users:
        try:
            bot.send_message(user_id, message)
            print(f"Отправлено пользователю {user_id}. Кваритра {registered_users[user_id]}")
        except Exception as e:
            print(f"Ошибка отправки пользователю {user_id}: {e}")

@bot.message_handler()
def admin_auth(message):
    if message.text == ADMIN_CODE:
        bot.send_message(message.chat.id, "Вы получили права администратора")
        ADMIN_ID = message.chat.id

if __name__ == "__main__":
    # Запуск проверки уведомлений в отдельном потоке
    threading.Thread(target=check_monthly_notification, daemon=True).start()
    print(f"Бот запущен")
    bot.polling(none_stop=True)
