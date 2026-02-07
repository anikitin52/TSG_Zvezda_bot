import threading
import time

from telebot import TeleBot, types
from datetime import datetime

from telebot.apihelper import ApiTelegramException

from services.SecurityManager import SecurityManager
from services.ExportManager import ExportManager
from services.TimeManager import TimeManager
from model.User import User
from model.Enums import UserRole
from model.Apartment import Apartment
from model.MeterData import MeterData
from utils.logger import logger
from utils.backup import make_backup

from ui.telegram.features.registration import check_password
from ui.telegram.features.staff_auth import add_enter_code
from ui.telegram.features.staff_auth import check_auth_code
from ui.telegram.features.info import show_info
from ui.telegram.callbacks import register_callbacks
from ui.telegram.features.send_meters_data import create_meters_markup
from ui.telegram.features.appeals_send import send_address
from ui.telegram.features.notifications import notifications

security_manager = SecurityManager()
export_manager = ExportManager()
time_manager = TimeManager()


bot = TeleBot(security_manager.get_token())
register_callbacks(bot)


@bot.message_handler(commands=['start'])
def start(message):
    """
    Обработка команды /start -> Запуск бота. Начало регистрации пользователя.
    :param message: Сообщение от пользователя - Команда /start
    :return: None
    """
    try:
        user_id = message.from_user.id

        # Проверяем наличие пользователя
        user = User(user_id)
        user.get_data_from_db()
        user_apartment = user.get_apartment()
        if user_apartment is not None:
            bot.send_message(message.chat.id, f"✅ Вы уже зарегистрированы! Квартира: {user_apartment}")
        else:
            # Запрашиваем пароль у нового пользователя
            msg = bot.send_message(message.chat.id, '🔒 Для начала работы с ботом введите пароль доступа:')
            bot.register_next_step_handler(msg, lambda m: check_password(m, bot, user))
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['info'])
def info(message):
    result = show_info(message.from_user.id)
    bot.send_message(message.chat.id, result, parse_mode='HTML')


@bot.message_handler(commands=['export'])
def export_meters(message):
    """
    Обработка команды /export -> Отправка пользователю таблицы с данными
    :param message: Сообщение от пользователя - команда -> /export
    :return: None
    """
    try:
        user_roles = User(message.from_user.id).get_data_from_db().get_roles()
        if any(role in user_roles for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.ACCOUNTANT]):
            export_manager.export_meters_data()
            now = datetime.now()
            current_month = f"{now.month:02d}.{now.year}"
            with open(f"Показания счетчиков {current_month}.xlsx", "rb") as f:
                bot.send_document(message.from_user.id, f)
        else:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['appeals'])
def export_appeals(message):
    try:
        user_roles = User(message.from_user.id).get_data_from_db().get_roles()
        if any(role in user_roles for role in [UserRole.ADMIN, UserRole.MANAGER]):
            export_manager.export_appeals_data()
            with open(f"Обращения.xlsx", "rb") as f:
                bot.send_document(message.from_user.id, f)
        else:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['backup'])
def backup(message):
    try:
        user_roles = User(message.from_user.id).get_data_from_db().get_roles()
        if UserRole.ADMIN not in user_roles:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
            return
        else:
            make_backup()
            bot.send_message(message.chat.id, "Резервная копия создана")
    except Exception as e:
        logger.error(f"Ошибка в backup: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['auth'])
def auth(message):
    try:
        # Проверка регистрации пользователя
        user = User(message.from_user.id).get_data_from_db()

        if user is None:
            msg = bot.send_message(message.chat.id, "Введите код доступа")
            bot.register_next_step_handler(msg, lambda m: add_enter_code(m, bot, user))
            return

        msg = bot.send_message(message.chat.id, 'Введите код авторизации')
        bot.register_next_step_handler(msg, lambda m: check_auth_code(m, bot, user))

    except Exception as e:
        logger.error(f"Ошибка в auth: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['account'])
def account(message):
    """Вывод профиля с кнопками редактирования"""
    try:
        user_id = message.from_user.id
        user = User(user_id).get_data_from_db()
        user_apartment = user.get_apartment()

        if user_apartment is None:
            bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
            return

        apartment = Apartment(user_apartment).get_data_from_db()
        result = {
            'apartment': user.get_apartment(),
            'water_count': apartment.get_water_count(),
            'electricity_count': apartment.get_electricity_count()
        }

        if result:
            apartment = result['apartment']
            water_count = result['water_count']
            electricity_type = result['electricity_count']
            rate = "Однотарифный" if electricity_type == 1 else "Двухтарифный"

            # Создаем клавиатуру с несколькими кнопками
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🏠 Изменить квартиру", callback_data=f'edit_apartment_{user_id}'),
                types.InlineKeyboardButton("💧 Изменить счетчики воды", callback_data=f'edit_water_{user_id}'),
                types.InlineKeyboardButton("⚡ Изменить электросчетчик", callback_data=f'edit_electric_{user_id}'),
                types.InlineKeyboardButton("❌ Удалить аккаунт", callback_data=f'delete_account_{user_id}')
            )

            bot.send_message(
                message.chat.id,
                f"🏠 Ваш профиль:\nКвартира: {apartment}\n"
                f"💧 Счётчиков воды: {water_count}\n"
                f"⚡ Счетчик электричества: {rate}",
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при получении данных профиля")

    except Exception as e:
        logger.error(f"Ошибка в account: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['send'])
def send_data(message):
    """
    Запуск процесса отправки показаний
    """
    try:
        # Проверка регистрации пользователя
        user = User(message.from_user.id).get_data_from_db()
        if user.apartment is None:
            bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
            return

        # Проверка времени отправки
        today = datetime.now().day
        start_day = time_manager.get_start_day()
        end_day = time_manager.get_end_day()

        if not (start_day <= today <= end_day):
            bot.send_message(message.chat.id,
                             f"❌ Прием показаний закрыт. Показания принимаются с {start_day} по {end_day} число каждого месяца")
            return

        # Проверяем, отправлялись ли уже показания
        meter_data = MeterData(user.apartment)
        if meter_data.check_apartment_send():
            bot.send_message(message.chat.id, "✅ Вы уже отправили показания за этот месяц")
            return

        # Создаем клавиатуру для ввода показаний
        markup = create_meters_markup(user)

        # Текущий месяц и год
        month_name = time_manager.get_text_month(datetime.now().month)
        year = datetime.now().year

        bot.send_message(message.chat.id, f"📊 Ввод показаний за {month_name} {year}\n\nВыберите счетчик:",
                         reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в send_data: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(commands=['manager', 'accountant', 'electric', 'plumber'])
def handle_address_request(message):
    """
    Выбор получателя обращения / заявки на работу
    :param message: Сообщение от польщователя - команда, соотвествующая получателю обращения
    :return: None
    """
    try:
        # Проверка регистрации пользователя
        user = User(message.from_user.id).get_data_from_db()
        if user.get_apartment() is None:
            bot.send_message(message.chat.id, "Вы не зарегистрированы. Чтобы начать работу введите /start")
            return

        # Определяем тип получателя и текст запроса
        command = message.text.split('@')[0]
        MANAGER_ID = security_manager.get_staff_id('Председатель')
        ACCOUNTANT_ID = security_manager.get_staff_id('Бухгалтер')
        PLUMBER_ID = security_manager.get_staff_id('Сантехник')
        ELECTRIC_ID = security_manager.get_staff_id('Электрик')
        recipient_data = {
            '/manager': {
                'id': MANAGER_ID,
                'request_text': "✉️ Напишите своё обращение к председателю ТСЖ",
                'recipient': "Председатель",
                'message_type': 'Обращение председателю',
                'response_success': "✅ Обращение успешно отправлено председателю",
                'answer_text': 'Ответ председателя ТСЖ на ваше обращение'
            },
            '/accountant': {
                'id': ACCOUNTANT_ID,
                'request_text': "✉️ Напишите своё обращение к бухгалтеру",
                'recipient': "Бухгалтер",
                'message_type': 'Обращение бухгалтеру',
                'response_success': "✅ Обращение успешно отправлено бухгалтеру",
                'answer_text': 'Ответ бухгалтера на ваше обращение'
            },
            '/electric': {
                'id': ELECTRIC_ID,
                'request_text': "✉️ Напишите текст заявки на работу электрика",
                'recipient': "Электрик",
                'message_type': 'Заявка на работу слектрика',
                'response_success': "✅ Заявка на работу электрика успешно отправлена",
                'answer_text': 'Ответ электрика на ваше обращение'
            },
            '/plumber': {
                'id': PLUMBER_ID,
                'request_text': "✉️ Напишите текст заявки на работу сантехника",
                'recipient': "Сантехник",
                'message_type': 'Заявка на работу сантехника',
                'response_success': "✅ Заявка на работу сантехника успешно отправлена",
                'answer_text': 'Ответ сантехника на ваше обращение'
            }
        }

        msg = bot.send_message(message.chat.id, recipient_data[command]['request_text'])
        bot.register_next_step_handler(msg, lambda m: send_address(m, bot, recipient_data[command]))

    except Exception as e:
        logger.error(f"Ошибка в handle_address_request: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_unrecognized_input(message):
    """
    Обрабатывает все текстовые сообщения, которые не были обработаны другими обработчиками
    """
    try:
        # Проверяем, зарегистрирован ли пользователь
        user = User(message.from_user.id).get_data_from_db()
        user_exists = user.get_apartment() is not None

        if user_exists:
            # Пользователь зарегистрирован - предлагаем доступные команды
            bot.send_message(
                message.chat.id,
                "❌ Ошибка ввода"
            )
        else:
            # Пользователь не зарегистрирован
            bot.send_message(
                message.chat.id,
                "❌ Ошибка ввода \n\n"
                "Для начала работы с ботом введите /start"
            )

        logger.info(f"Пользователь {message.from_user.id} отправил непонятное сообщение: {message.text}")

    except Exception as e:
        logger.error(f"Ошибка в handle_unrecognized_input: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")

def run_telegram_bot():
    # Запуск в отдельном потоке
    notification_thread = threading.Thread(target=notifications, args=(bot,), daemon=True)
    notification_thread.start()

    while True:
        try:
            bot.polling(none_stop=True, timeout=90)
        except ApiTelegramException as e:
            print(f"Ошибка API: {e}. Перезапуск через 10 секунд...")
            time.sleep(10)
        except Exception as e:
            print(f"Неизвестная ошибка: {e}. Перезапуск через 30 секунд...")
            time.sleep(30)
