from telebot import types
from config import PASSWORD
from data.database import *
from model.apartment import Apartment

# Данные о пользователях, проходящих регистрацию
user_registration_data = {}  # user_id : Apartment


def registration_handler(bot):
    @bot.message_handler(commands=['start'])
    def start_bot(message):
        """
        Обработка команды /start -> Запуск бота. Начало регистрации пользователя.
        :param message: Сообщение от пользователя - Команда /start
        :return: None
        """

        # Проверяем наличие пользователя
        user_telegram_id = message.from_user.id
        is_register = check_user_registration(user_telegram_id)
        logger.info(f'Пользователь {user_telegram_id} запустил бота')
        if is_register:
            apartment = get_user_apartment(user_telegram_id)
            bot.send_message(message.chat.id, f'✅ Вы уже зарегистрированы! Квартира: {apartment}')
        else:
            # Запрашиваем код доступа у пользователя
            password = bot.send_message(message.chat.id, '🔒 Для начала работы с ботом введите код доступа:')
            bot.register_next_step_handler(password, check_password)

    def check_password(message):
        """
        Проверка введенного пароля
        :param message: Сообщение с введенным паролем
        :return: None
        """
        # Получаем пароль и id пользователя
        user_input = message.text.strip()
        user_telegram_id = message.from_user.id

        # Проверяем код доступа
        if user_input == PASSWORD:
            # Пароль верный -> Запрашиваем номер квартиры -> Переходим к проверке номера
            apartment_number = bot.send_message(message.chat.id, "Введите номер вашей квартиры (от 1 до 150)")
            bot.register_next_step_handler(apartment_number, check_apartment_number)
            logger.info(f'Пользователь {user_telegram_id} ввел верный пароль')
        elif user_input.lower() == '/cancel':
            # Пользователь отменил действие -> Останавнливаем процесс
            bot.send_message(message.chat.id, "❌ Действие отменено")
            logger.info(f'Пользоватлеь {user_telegram_id} остановил процесс регистрации')
            return
        else:
            # Пользователь ввел неверный пароль -> Требуем ввести снова
            password = bot.send_message(message.chat.id,
                                        "❌ Неверный пароль. Попробуйте еще раз: \nЕсли хотите отменить действие, введите /cancel")
            bot.register_next_step_handler(password, check_password)
            logger.info(f'Пользователь {user_telegram_id} ввел неверный код доступа')

    def check_apartment_number(message):
        """
        Проверка введенного номера квартиры
        :param message: Сообщение с введенным номером квартиры
        :return: None
        """
        user_input = message.text.strip()
        user_telegram_id = message.from_user.id

        if user_input.lower() == '/cancel':
            # Пользователь отменил действие -> Останавнливаем процесс
            bot.send_message(message.chat.id, "❌ Действие отменено")
            logger.info(f'Пользоватлеь {user_telegram_id} остановил процесс регистрации')
            return

        try:
            apartment = int(user_input)
            if not 1 <= apartment <= 150:
                logger.info(f'Пользователь {user_telegram_id} ввел неверный номер квартиры')
                raise ValueError

            # Квартира верная -> Сохраняем данные
            logger.info(f'Пользователь {user_telegram_id} ввел верный номер квартиры')
            user_registration_data[user_telegram_id] = Apartment(apartment)
            water_meters_count = bot.send_message(message.chat.id,
                                                  "Введите количество счетчиков холодной воды (от 1 до 3):")
            bot.register_next_step_handler(water_meters_count, check_water_meters)
            logger.info(f'Пользователь {user_telegram_id} ввел верный номер квартиры')

        except ValueError:
            apartment_number = bot.send_message(message.chat.id,
                                                "❌ Неверный номер квартиры! Введите номер квартиры от 1 до 150")
            bot.register_next_step_handler(apartment_number, check_apartment_number)

    def check_water_meters(message):
        """
        Проверка введенного количества счетчиков
        :param message: Сообщение с числом счетчиков
        :return: None
        """
        user_input = message.text.strip()
        user_telegram_id = message.from_user.id

        if user_input.lower() == '/cancel':
            # Пользователь отменил действие -> Останавнливаем процесс
            bot.send_message(message.chat.id, "❌ Действие отменено")
            logger.info(f'Пользоватлеь {user_telegram_id} остановил процесс регистрации')
            return

        try:
            water_meters = int(message.text.strip())
            if not 1 <= water_meters <= 3:
                logger.info(f'Пользователь {user_telegram_id} ввел неверное количество счетчиков воды')
                raise ValueError

            # Сохраняем количество счетчиков
            logger.info(f'Пользователь {user_telegram_id} ввел верное количество счетчиков воды')
            apartment = user_registration_data[user_telegram_id]
            apartment.set_water_meters_count(water_meters)

            # Кнопки выбора счетчика электричества
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton('Однотарифный',
                                           callback_data=f'elec_1_{water_meters}_{apartment.number}'),
                types.InlineKeyboardButton('Двухтарифный',
                                           callback_data=f'elec_2_{water_meters}_{apartment.number}')
            )
            bot.send_message(message.chat.id, "Выберите тип счетчика электричества", reply_markup=markup)

        except ValueError:
            count_water_meters = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
            bot.register_next_step_handler(count_water_meters, check_water_meters)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('elec_'))
    def select_meters(call):
        """
        Ввод числа электросчетчиков
        :param call: Данные о количестве электросчетчиков
        :return: None
        """
        data = call.data.split('_')
        elec_type = data[1]
        user_telegram_id = call.from_user.id

        # Сохраняем тип электросчетчика
        logger.info(f'Пользователь {user_telegram_id} выбрал электросчетчик {elec_type}')
        apartment = user_registration_data[user_telegram_id]
        apartment.set_electricity_count(int(elec_type))

        save_data(user_telegram_id)

        bot.answer_callback_query(call.id)
        logger.info(f'Пользователь {user_telegram_id} успешно прошел регистрацию')
        bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")

    def save_data(user_id):
        """
        Сохранение данных в БД, отправка увеомления
        :param user_id: id пользователя в Telegram
        :return: None
        """
        # Получаем сохраненные данные
        apartment = user_registration_data[user_id]
        user_name = f'Житель кв. {apartment.number}'
        apartment_number = apartment.number
        water_meters_count = apartment.water_meters
        electricity_count = apartment.electricity_meters

        # Запись в БД
        create_new_user(user_id, user_name, apartment_number, water_meters_count, electricity_count)

        # Очистка данных регистрации
        del user_registration_data[user_id]
        logger.info(f'Временный данные регистрации пользователя {user_id} очищены')

        # Уведомление админа
        ADMIN_ID = find_staff_id('Админ') or None
        if ADMIN_ID != None:
            bot.send_message(ADMIN_ID,
                         f"Новый пользователь: {user_name}\n"
                         f"Квартира: {apartment_number}\n"
                         f"Счетчиков воды: {water_meters_count}\n"
                         f"Тип счетчика электричества: {'двухтарифный' if electricity_count == 2 else 'однотарифный'}")
            logger.info(f'Уведомление о регистрации админу отправлено')
        else:
            logger.info("Отправить сообщение админу не удалось")
