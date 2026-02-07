from telebot import types

from model.User import User
from model.Apartment import Apartment
from services.SecurityManager import SecurityManager
from utils.logger import logger
from ui.telegram.features.staff_auth import check_auth_code

manager = SecurityManager()
registration_objects = {}


def check_password(message, bot, user):
    try:
        if message.text.strip() == manager.get_enter_code():
            # Пароль верный, сразу запрашиваем номер квартиры
            msg = bot.send_message(message.chat.id, "Введите номер вашей квартиры (от 1 до 150)")
            bot.register_next_step_handler(msg, lambda m: check_apartment_number(m, bot, user))
            logger.info(f'Пользователь {message.from_user.id} ввел верный пароль')

        elif message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        else:
            # Пароль неверный - запрашиваем снова
            msg = bot.send_message(message.chat.id, "❌ Неверный пароль. Попробуйте еще раз:")
            bot.register_next_step_handler(msg, lambda m: check_password(m, bot,
                                                                         user))  # Снова вызываем проверку пароля
            logger.info(f'Пользователь {message.from_user.id} ввел неверный пароль')

    except Exception as e:
        logger.error(f"Ошибка в check_password: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def check_apartment_number(message, bot, user):
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        if message.text.strip().lower() == '/auth':
            msg = bot.send_message(message.chat.id, "Переход к авторизации сотрудника")
            bot.register_next_step_handler(msg, lambda m: check_auth_code(m, bot, user))
            return
        try:
            apartment = int(message.text.strip())
            if not 1 <= apartment <= 150:
                raise ValueError

            # Проверка наличия квартиры в БД
            ap = Apartment(apartment)
            ap.check_apartment_in_db()
            user_id = message.from_user.id

            # Сохраняем номер квартиры
            user.register_in_apartment(apartment)

            msg = bot.send_message(message.chat.id, "Введите количество счетчиков холодной воды (от 1 до 3):")
            bot.register_next_step_handler(msg, lambda m: check_water_meters(m, bot, user, ap))

        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 150")
            bot.register_next_step_handler(msg, lambda m: check_apartment_number(m, bot, user))
    except Exception as e:
        logger.error(f"Ошибка в check_apartment_number: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def check_water_meters(message, bot, user, apartment):
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return
        try:
            water_meters = int(message.text.strip())
            if not 1 <= water_meters <= 3:
                raise ValueError

            # Сохраняем количество счетчиков
            user_id = message.from_user.id
            apartment.set_water_meters(water_meters)

            # Кнопки выбора счетчика электричества
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton('Однотарифный',
                                           callback_data=f'elec_1_{water_meters}_{user.get_apartment()}'),
                types.InlineKeyboardButton('Двухтарифный',
                                           callback_data=f'elec_2_{water_meters}_{user.get_apartment()}')
            )
            registration_objects[user_id] = {
                'apartment': apartment,
                'user': user
            }
            bot.send_message(message.chat.id, "Выберите тип счетчика электричества", reply_markup=markup)

        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
            bot.register_next_step_handler(msg, lambda m: check_water_meters(m, bot, user, apartment))

    except Exception as e:
        logger.error(f"Ошибка в check_water_meters: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def select_meters(call, bot):
    try:
        parts = call.data.split('_')
        elec_type = parts[1]
        water_count = parts[2]
        user_id = call.from_user.id

        if user_id not in registration_objects:
            bot.answer_callback_query(
                call.id,
                "❌ Вы не начали регистрацию или сессия истекла. Начните заново: /start",
                show_alert=True
            )
            return

        # Получаем сохраненные данные
        if user_id not in registration_objects or 'apartment' not in registration_objects[user_id]:
            bot.answer_callback_query(call.id, "❌ Ошибка: данные не найдены. Начните регистрацию заново.",
                                      show_alert=True)
            return

        session_data = registration_objects[user_id]
        apartment_obj = session_data['apartment']
        user_obj = session_data['user']

        apartment = apartment_obj.get_number()

        # Вставляем запись о квартире в БД
        # Вставляем запись о квартире в БД через объект User
        user_obj.create_new_in_db(
            water_count=int(water_count),
            electricity_count=int(elec_type)
        )

        # Очищаем временные данные
        if user_id in registration_objects:
            del registration_objects[user_id]

        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")

        ADMIN_ID = manager.get_admin_id()
        bot.send_message(ADMIN_ID,
                         f"Новый пользователь! \n"
                         f"Квартира: {apartment}\n"
                         f"Счетчиков воды: {water_count}\n"
                         f"Тип счетчика электричества: {'двухтарифный' if elec_type == '2' else 'однотарифный'}")

    except Exception as e:
        logger.error(f"Ошибка при завершении регистрации: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте снова.", show_alert=True)
