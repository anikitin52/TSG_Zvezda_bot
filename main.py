from config import BOT_TOKEN, ADMIN_ID
from telebot import TeleBot, types
from datetime import date, datetime
import schedule
import threading
import time

bot = TeleBot(BOT_TOKEN)

# Хранилище данных: {user_id: apartment_number}
registered_users = {}
flats = {}  # {flat : meters_count }
current_datetime = datetime.now()
print(current_datetime)

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

if __name__ == "__main__":
    # Запуск проверки уведомлений в отдельном потоке
    threading.Thread(target=check_monthly_notification, daemon=True).start()
    print(f"Бот запущен")
    bot.polling(none_stop=True)
