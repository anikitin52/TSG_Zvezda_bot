from datetime import datetime

from telebot import types
from model.Apartment import Apartment
from model.MeterData import MeterData
from model.MeterData import cold_water_meters, hot_water_meters, electricity_meters
from model.User import User
from utils.logger import logger
from services.SecurityManager import SecurityManager
from services.TimeManager import TimeManager

time_manager = TimeManager()
manager = SecurityManager()

# Глобальное хранилище объектов MeterData для каждого пользователя
meter_data_cache = {}  # user_id -> MeterData объект


def get_or_create_meter_data(user_id, apartment_number):
    """Получает или создает объект MeterData для пользователя"""
    if user_id not in meter_data_cache:
        meter_data_cache[user_id] = MeterData(apartment_number)
    return meter_data_cache[user_id]


def create_meters_markup(user):
    """
    Создание кнопок ввода счетчиков
    :param user: Пользователь (объект User)
    :return: markup с кнопками
    """
    markup = types.InlineKeyboardMarkup()

    # Получаем данные квартиры
    apartment_obj = Apartment(user.apartment).get_data_from_db()
    water_count = apartment_obj.water_count
    electricity_count = apartment_obj.electricity_count

    counter = 1

    # Холодная вода
    cold_water_names = cold_water_meters[water_count]
    for i in range(water_count):
        text = cold_water_names[i]
        # Проверяем, введены ли уже показания для этого счетчика
        meter_data = get_or_create_meter_data(user.telegram_id, user.apartment)
        if str(counter) in meter_data.current_meters:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    # Горячая вода
    hot_water_names = hot_water_meters[water_count]
    for i in range(water_count):
        text = hot_water_names[i]
        meter_data = get_or_create_meter_data(user.telegram_id, user.apartment)
        if str(counter) in meter_data.current_meters:
            text += " ✅"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'meter_{counter}'))
        counter += 1

    # Электричество
    elec_meters = electricity_meters[electricity_count]
    for meter in elec_meters:
        meter_data = get_or_create_meter_data(user.telegram_id, user.apartment)
        if str(counter) in meter_data.current_meters:
            meter += " ✅"
        markup.add(types.InlineKeyboardButton(meter, callback_data=f'meter_{counter}'))
        counter += 1

    markup.add(types.InlineKeyboardButton("📤 Перейти к проверке", callback_data='review'))
    markup.add(types.InlineKeyboardButton("🚫 Отменить", callback_data='cancel'))
    return markup


def create_review_markup(meter_data):
    markup = types.InlineKeyboardMarkup()
    counter = 1

    # Холодная вода
    for i in range(meter_data.water_count):
        text = f"{cold_water_meters[meter_data.water_count][i]}: {meter_data.current_meters.get(str(counter), '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    # Горячая вода
    for i in range(meter_data.water_count):
        text = f"{hot_water_meters[meter_data.water_count][i]}: {meter_data.current_meters.get(str(counter), '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    # Электричество
    elec_meters = electricity_meters[meter_data.electricity_type]
    for i in range(len(elec_meters)):
        text = f"{elec_meters[i]}: {meter_data.current_meters.get(str(counter), '—')}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f'edit_{counter}'))
        counter += 1

    markup.row(
        types.InlineKeyboardButton("✅ Подтвердить все", callback_data='confirm_all'),
        types.InlineKeyboardButton("↩️ Назад к редактированию", callback_data='back_edit')
    )
    return markup


def input_meters(call, bot):
    try:
        meter_num = call.data.split('_')[1]
        user_id = call.from_user.id

        # Получаем пользователя и объект MeterData
        user = User(user_id).get_data_from_db()
        meter_data = get_or_create_meter_data(user_id, user.apartment)

        msg = bot.send_message(call.message.chat.id, f"Введите показания для выбранного счетчика:")
        bot.register_next_step_handler(msg, lambda m: process_value_input(m, bot, meter_data, meter_num, user_id))

    except Exception as e:
        logger.error(f"Ошибка в input_meters: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def process_value_input(message, bot, meter_data, meter_num, user_id):
    """
    Обработка ввода данных показаний счетчика
    """
    try:
        # Проверка корректности ввода
        try:
            value = int(message.text.strip())
            if value < 0:
                raise ValueError
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите положительное целое число")
            bot.register_next_step_handler(msg, lambda m: process_value_input(m, bot, meter_data, meter_num, user_id))
            return

        # Сохраняем показания в объекте MeterData
        meter_data.current_meters[str(meter_num)] = value

        # Получаем пользователя для обновления клавиатуры
        user = User(user_id).get_data_from_db()

        # Создание нового сообщения с кнопками

        month_name = time_manager.get_text_month(datetime.now().month)
        year = datetime.now().year

        markup = create_meters_markup(user)
        bot.send_message(message.chat.id, f"📊 Показания за {month_name} {year}", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в process_value_input: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def review(call, bot):
    """
    Проверка введенных данных
    """
    try:
        user_id = call.from_user.id

        # Получаем пользователя
        user = User(user_id).get_data_from_db()
        if user.apartment is None:
            bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
            return

        # Получаем объект MeterData
        meter_data = get_or_create_meter_data(user_id, user.apartment)

        # Получаем данные квартиры
        apartment_obj = Apartment(user.apartment).get_data_from_db()
        water_count = apartment_obj.water_count
        electricity_count = apartment_obj.electricity_count

        # Устанавливаем значения для отчета
        meter_data.water_count = water_count
        meter_data.electricity_type = electricity_count

        # Получаем отчет
        report = meter_data.get_report()

        # Создаем клавиатуру для проверки
        markup = create_review_markup(meter_data)

        # Получаем месяц и год
        month_name = time_manager.get_text_month(datetime.now().month)
        year = datetime.now().year

        bot.send_message(
            call.message.chat.id,
            f"📝 Проверка за {month_name} {year}",
            reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Ошибка в review: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def edit_value(call, bot):
    try:
        # Корректировка значений
        meter_num = call.data.split('_')[1]
        user_id = call.from_user.id

        # Получаем объект MeterData
        user = User(user_id).get_data_from_db()
        meter_data = get_or_create_meter_data(user_id, user.apartment)

        msg = bot.send_message(call.message.chat.id, f"Введите новое значение для выбранного счетчика:")
        bot.register_next_step_handler(msg, lambda m: process_edit_value(m, bot, meter_data, meter_num, user_id))

    except Exception as e:
        logger.error(f"Ошибка в edit_value: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def process_edit_value(message, bot, meter_data, meter_num, user_id):
    """
    Обработка нового значения при корректировке
    """
    try:
        # Проверка корректности ввода
        try:
            value = int(message.text.strip())
            if value < 0:
                raise ValueError
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите положительное целое число")
            bot.register_next_step_handler(msg, lambda m: process_edit_value(m, bot, meter_data, meter_num, user_id))
            return

        # Обновляем значение в объекте MeterData
        meter_data.current_meters[str(meter_num)] = value

        # Обновляем клавиатуру
        user = User(user_id).get_data_from_db()

        month_name = time_manager.get_text_month(datetime.now().month)
        year = datetime.now().year

        markup = create_meters_markup(user)
        bot.send_message(message.chat.id, f"📊 Показания за {month_name} {year}", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в process_edit_value: {e}", exc_info=True)
        bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")


def confirm_all(call, bot):
    try:
        user_id = call.from_user.id

        # Получаем пользователя
        user = User(user_id).get_data_from_db()
        if not user or user.apartment is None:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден", show_alert=True)
            return

        # Получаем данные квартиры
        apartment_obj = Apartment(user.apartment).get_data_from_db()
        water_count = apartment_obj.water_count
        electricity_type = apartment_obj.electricity_count

        # Получаем объект MeterData
        meter_data = get_or_create_meter_data(user_id, user.apartment)

        # Получаем отчет
        report = meter_data.get_report()

        # Получаем текущие показания из объекта meter_data
        data = meter_data.current_meters

        # Получаем имена счетчиков
        cold_list = cold_water_meters[water_count]
        hot_list = hot_water_meters[water_count]
        elec_list = electricity_meters[electricity_type]

        cw1 = int(data.get('1', 0)) if water_count >= 1 else 0
        cw2 = int(data.get('2', 0)) if water_count >= 2 else 0
        cw3 = int(data.get('3', 0)) if water_count >= 3 else 0

        hw1 = int(data.get(str(1 + water_count), 0)) if water_count >= 1 else 0
        hw2 = int(data.get(str(2 + water_count), 0)) if water_count >= 2 else 0
        hw3 = int(data.get(str(3 + water_count), 0)) if water_count >= 3 else 0

        el1 = int(data.get(str(1 + 2 * water_count), 0))
        el2 = int(data.get(str(2 + 2 * water_count), 0)) if electricity_type == 2 else 0

        month = datetime.now().strftime('%m.%Y')

        # Сохраняем данные в БД
        meter_data.save_to_db(
            user_id=user_id,
            apartment_number=user.apartment,
            water_count=water_count,
            electricity_type=electricity_type,
            values_dict={
                'cold_water_1': cw1,
                'cold_water_2': cw2,
                'cold_water_3': cw3,
                'hot_water_1': hw1,
                'hot_water_2': hw2,
                'hot_water_3': hw3,
                'electricity_1': el1,
                'electricity_2': el2
            }
        )

        # Отправка отчета бухгалтеру
        ACCOUNTANT_ID = manager.get_staff_id("Бухгалтер")

        if ACCOUNTANT_ID:
            bot.send_message(ACCOUNTANT_ID, f"📨 Показания от кв. {user.apartment}:\n{report}")

        # Очищаем данные из кэша
        if user_id in meter_data_cache:
            del meter_data_cache[user_id]

        bot.answer_callback_query(call.id, "✅ Показания отправлены")
        bot.send_message(call.message.chat.id, "✅ Показания успешно отправлены!")

        logger.info(f'Показания переданы. Квартира {user.apartment}')

    except Exception as e:
        logger.error(f"Ошибка в confirm_all: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def back_edit(call, bot):
    """
    Возврат к редактированию показаний
    """
    try:
        user_id = call.from_user.id

        # Получаем пользователя
        user = User(user_id).get_data_from_db()
        if user.apartment is None:
            bot.answer_callback_query(call.id, "❌ Пользователь не найден", show_alert=True)
            return

        # Создание клавиатуры с кнопками
        meter_data = get_or_create_meter_data(user_id, user.apartment)
        markup = create_review_markup(meter_data)

        # Получаем месяц и год

        month_name = time_manager.get_text_month(datetime.now().month)
        year = datetime.now().year

        bot.send_message(
            call.message.chat.id,
            f"📊 Редактирование показаний за {month_name} {year}",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Ошибка в back_edit: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


def cancel(call, bot):
    """
    Отмена ввода показаний
    """
    try:
        user_id = call.from_user.id

        # Удаляем объект MeterData из кэша
        if user_id in meter_data_cache:
            del meter_data_cache[user_id]

        bot.answer_callback_query(call.id, "🚫 Ввод отменён")
        bot.send_message(call.message.chat.id, "🚫 Ввод показаний отменён")

    except Exception as e:
        logger.error(f"Ошибка в cancel: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
