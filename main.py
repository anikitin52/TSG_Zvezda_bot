import os
import random
import socket
import http.client
import requests
from urllib3.exceptions import ProtocolError
import telebot.apihelper
import shutil
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from telebot import TeleBot

from config import *
from data.data import *
from data.database import *
from data.models import User
from services.exel_export import send_table, send_appeals_table
from services.logger import logger
from services.utils import *

bot = TeleBot(BOT_TOKEN)
now = datetime.now()

# TODO: Во всех функциях, которые принимают текст сделать проверку: if not message.text
@bot.message_handler(commands=['start'])
def start(message):
    """
    Обработка команды /start -> Запуск бота. Начало регистрации пользователя.
    :param message: Сообщение от пользователя - Команда /start
    :return: None
    """
    try:
        tablename = 'users'
        user_id = message.from_user.id

        # Проверяем наличие пользователя
        user = find_user_by_id(tablename, user_id)
        if user:
            apartment = user[3]
            bot.send_message(message.chat.id, f"✅ Вы уже зарегистрированы! Квартира: {apartment}")
        else:
            # Запрашиваем пароль у нового пользователя
            msg = bot.send_message(message.chat.id, '🔒 Для начала работы с ботом введите пароль доступа:')
            bot.register_next_step_handler(msg, check_password)
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


def check_password(message):
    """
    Проверка введенного пароля
    :param message: Сообщение с введенным паролем
    :return: None
    """
    try:
        if message.text.strip() == PASSWORD:
            # Пароль верный, сразу запрашиваем номер квартиры
            msg = bot.send_message(message.chat.id, "Введите номер вашей квартиры (от 1 до 150)")
            bot.register_next_step_handler(msg, check_apartment_number)
            logger.info(f'Пользователь {message.from_user.id} ввел верный пароль')

        elif message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        else:
            # Пароль неверный - запрашиваем снова
            msg = bot.send_message(message.chat.id, "❌ Неверный пароль. Попробуйте еще раз:")
            bot.register_next_step_handler(msg, check_password)  # Снова вызываем проверку пароля
            logger.info(f'Пользователь {message.from_user.id} ввел неверный пароль')

    except Exception as e:
        logger.error(f"Ошибка в check_password: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


def check_apartment_number(message):
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        try:
            apartment = int(message.text.strip())
            if not 1 <= apartment <= 150:
                raise ValueError

            # Проверка наличия квартиры в БД
            tablename = 'users'
            users = select_all(tablename)
            user_id = message.from_user.id

            # Сохраняем номер квартиры
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['apartment'] = apartment

            msg = bot.send_message(message.chat.id, "Введите количество счетчиков холодной воды (от 1 до 3):")
            bot.register_next_step_handler(msg, check_water_meters)

        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 150")
            bot.register_next_step_handler(msg, check_apartment_number)
    except Exception as e:
        logger.error(f"Ошибка в check_apartment_number: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)



def check_water_meters(message):
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
            user_data[user_id]['water_count'] = water_meters

            # Кнопки выбора счетчика электричества
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton('Однотарифный',
                                           callback_data=f'elec_1_{water_meters}_{user_data[user_id]["apartment"]}'),
                types.InlineKeyboardButton('Двухтарифный',
                                           callback_data=f'elec_2_{water_meters}_{user_data[user_id]["apartment"]}')
            )
            bot.send_message(message.chat.id, "Выберите тип счетчика электричества", reply_markup=markup)

        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
            bot.register_next_step_handler(msg, check_water_meters)

    except Exception as e:
        logger.error(f"Ошибка в check_water_meters: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('elec_'))
def select_meters(call):
    try:
        parts = call.data.split('_')
        elec_type = parts[1]
        water_count = parts[2]
        user_id = call.from_user.id
        tablename = 'users'

        # Получаем сохраненные данные
        if user_id not in user_data or 'apartment' not in user_data[user_id]:
            bot.answer_callback_query(call.id, "❌ Ошибка: данные не найдены. Начните регистрацию заново.",
                                      show_alert=True)
            return

        apartment = user_data[user_id]['apartment']
        # Генерируем имя пользователя на основе его Telegram данных
        name = f"Житель кв.{apartment}"

        # Вставляем запись о квартире в БД
        insert_to_database(tablename,
                           ['telegram_id', 'name', 'apartment', 'water_count', 'electricity_count'],
                           [user_id, name, int(apartment), int(water_count), int(elec_type)])

        # Очищаем временные данные
        if user_id in user_data:
            del user_data[user_id]

        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "✅ Регистрация успешна! Перейдите в профиль: /account")

        ADMIN_ID = find_staff_id('Админ')
        bot.send_message(ADMIN_ID,
                         f"Новый пользователь: {name}\n"
                         f"Квартира: {apartment}\n"
                         f"Счетчиков воды: {water_count}\n"
                         f"Тип счетчика электричества: {'двухтарифный' if elec_type == '2' else 'однотарифный'}")

    except Exception as e:
        logger.error(f"Ошибка при завершении регистрации: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте снова.", show_alert=True)


@bot.message_handler(commands=['export'])
def export_data(message):
    """
    Обработка команды /export -> Отправка пользователю таблицы с данными
    :param message: Сообщение от пользователя - команда -> /export
    :return: None
    """
    try:
        ACCOUNTANT_ID = find_staff_id('Бухгалтер')
        ADMIN_ID = find_staff_id("Админ")

        if message.chat.id != ACCOUNTANT_ID and message.chat.id != ADMIN_ID:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
            return
        else:
            logger.info(f'Пользоватлель {message.chat.id} экспортировал Exel-таблицу с показаниями счетчтков')
            send_table(message.chat.id)

    except Exception as e:
        logger.error(f"Ошибка в export_data: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['appeals'])
def send_appeals(message):
    try:
        MANAGER_ID = find_staff_id('Председатель')
        ADMIN_ID = find_staff_id("Админ")

        if message.chat.id != MANAGER_ID and message.chat.id != ADMIN_ID:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
            return
        else:
            logger.info(f'Пользоватлель {message.chat.id} экспортировал Exel-таблицу с обращениями')
            send_appeals_table(message.chat.id)

    except Exception as e:
        logger.error(f"Ошибка в send_appeals: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['backup'])
def backup(message):
    try:
        admin = find_staff_id('Админ')
        if message.from_user.id != admin:
            bot.send_message(message.chat.id, "❌ У вас нет доступа к этой команде")
            return
        else:
            backup_daily()
            backup_monthly()

    except Exception as e:
        logger.error(f"Ошибка в backup: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['info'])
def info(message):
    """
    Выводит информацию о доступных польщователю командах
    :param message: Сообщение от пользователя - команда /info
    :return: None
    """
    try:
        if find_user_by_id('users', message.from_user.id) is None:
            bot.send_message(message.chat.id, "Вы не зарегистрированы. Чтобы начать работу введите /start")
            return

        result = "Список доступных вам команд: \n"
        user_status = 'user'
        result += '''
        /send - Передать показания счетчиков \n
        /manager - Отправить обращение к председателю \n
        /accountant - Отправить обращение к бухгалтеру \n
        /account - Переход в профиль квартиры \n
        '''
        staff_id = [
            find_staff_id('Админ'),
            find_staff_id('Председатель'),
            find_staff_id('Бухгалтер')
        ]
        for id in staff_id:
            if message.from_user.id == id:
                user_status = 'staff'

        if user_status == 'staff':
            result += "Специальные команды, доступныке вам \n"
            if message.from_user.id == staff_id[0]:
                result += "/backup - Сохранить резервную копию базы данных \n"
            if message.from_user.id == staff_id[1]:
                pass
            if message.from_user.id == staff_id[2]:
                result += '/export - Получить Exel-таблицу с показаниями счетчиков \n'

        bot.send_message(message.chat.id, result)

    except Exception as e:
        logger.error(f"Ошибка в info: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['account'])
def account(message):
    """Вывод профиля с кнопками редактирования"""
    try:
        telegram_id = message.from_user.id
        user_exists = find_user_by_id('users', telegram_id, 'COUNT(*)')[0] > 0

        if not user_exists:
            bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
            return

        result = find_user_by_id('users', telegram_id, 'apartment, water_count, electricity_count, name')

        if result:
            apartment, water_count, electricity_type, name = result
            rate = "Однотарифный" if electricity_type == 1 else "Двухтарифный"

            # Создаем клавиатуру с несколькими кнопками
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("✏️ Изменить ФИО", callback_data=f'edit_name_{telegram_id}'),
                types.InlineKeyboardButton("🏠 Изменить квартиру", callback_data=f'edit_apartment_{telegram_id}'),
                types.InlineKeyboardButton("💧 Изменить счетчики воды", callback_data=f'edit_water_{telegram_id}'),
                types.InlineKeyboardButton("⚡ Изменить электросчетчик", callback_data=f'edit_electric_{telegram_id}'),
                types.InlineKeyboardButton("❌ Удалить аккаунт", callback_data=f'delete_account_{telegram_id}')
            )

            bot.send_message(
                message.chat.id,
                f"🏠 Ваш профиль:\nФИО: {name}\nКвартира: {apartment}\n"
                f"Счётчиков воды: {water_count}\n"
                f"Счетчик электричества: {rate}",
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "❌ Ошибка при получении данных профиля")

    except Exception as e:
        logger.error(f"Ошибка в account: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


# Обработчики для каждой кнопки
@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_name_'))
def edit_name(call):
    """Обработка кнопки изменения ФИО"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Введите новое ФИО:")
        bot.register_next_step_handler(msg, process_new_name, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка в edit_name: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


def process_new_name(message, telegram_id):
    """Обработка нового ФИО"""
    try:
        if validate_russian_name(message.text):
            update_values('users', {'name': message.text.strip()}, {'telegram_id': telegram_id})
            bot.send_message(message.chat.id, "✅ ФИО успешно изменено")

        elif message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        else:
            msg = bot.send_message(message.chat.id, "❌ Неверный формат ФИО")
            bot.register_next_step_handler(msg, process_new_name, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка в process_new_name: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_apartment_'))
def edit_apartment(call):
    """Обработка кнопки изменения квартиры"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, "Введите новый номер квартиры (1-150):")
        bot.register_next_step_handler(msg, process_new_apartment, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка в edit_apartment: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


def process_new_apartment(message, telegram_id):
    """Обработка нового номера квартиры"""
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        try:
            apartment = int(message.text)
            if 1 <= apartment <= 150:
                update_values('users', {'apartment': apartment}, {'telegram_id': telegram_id})
                bot.send_message(message.chat.id, "✅ Номер квартиры изменен")
            else:
                msg = bot.send_message(message.chat.id, "❌ Номер должен быть от 1 до 150")
                bot.register_next_step_handler(msg, process_new_apartment, telegram_id)
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число")
            bot.register_next_step_handler(msg, process_new_apartment, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка в process_new_apartment: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_water_'))
def edit_water(call):
    """Обработка кнопки изменения счетчиков воды"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            "Введите новое количество счетчиков холодной воды (1-3):\n"
        )
        bot.register_next_step_handler(msg, process_new_water, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка в edit_water: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


def process_new_water(message, telegram_id):
    """Обработка нового количества счетчиков воды"""
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        try:
            water_count = int(message.text)
            if 1 <= water_count <= 3:
                update_values('users', {'water_count': water_count}, {'telegram_id': telegram_id})
                bot.send_message(message.chat.id, f"✅ Количество счетчиков воды изменено")
            else:
                msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
                bot.register_next_step_handler(msg, process_new_water, telegram_id)
        except ValueError:
            msg = bot.send_message(message.chat.id, "❌ Введите число от 1 до 3")
            bot.register_next_step_handler(msg, process_new_water, telegram_id)

    except Exception as e:
        logger.error(f"Ошибка в process_new_water: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_electric_'))
def edit_electric(call):
    """Обработка кнопки изменения типа электросчетчика"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton('Однотарифный', callback_data=f'confirm_elec_1_{telegram_id}'),
            types.InlineKeyboardButton('Двухтарифный', callback_data=f'confirm_elec_2_{telegram_id}')
        )

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "Выберите тип счетчика электричества:",
            reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Ошибка в edit_electric: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_elec_'))
def confirm_electric(call):
    """Подтверждение изменения типа электросчетчика"""
    try:
        parts = call.data.split('_')
        elec_type = int(parts[2])
        telegram_id = int(parts[3])

        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        try:
            update_values('users', {'electricity_count': elec_type}, {'telegram_id': telegram_id})
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                f"✅ Тип электросчетчика изменен на {'однотарифный' if elec_type == 1 else 'двухтарифный'}"
            )
        except Exception as e:
            logger.error(f"Ошибка при изменении электросчетчика: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка при изменении", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в confirm_electric: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_account_'))
def delete_account_confirmation(call):
    """Подтверждение удаления аккаунта"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        # Создаем клавиатуру подтверждения
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Да, удалить", callback_data=f'confirm_delete_{telegram_id}'),
            types.InlineKeyboardButton("❌ Нет, отменить", callback_data=f'cancel_delete_{telegram_id}')
        )

        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "⚠️ Вы уверены, что хотите удалить свой аккаунт?\n"
            "Все ваши данные будут безвозвратно удалены!",
            reply_markup=markup
        )

    except Exception as e:
        logger.error(f"Ошибка в delete_account_confirmation: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
def delete_account(call):
    """Окончательное удаление аккаунта"""
    try:
        telegram_id = int(call.data.split('_')[2])
        if call.from_user.id != telegram_id:
            bot.answer_callback_query(call.id, "❌ Недостаточно прав", show_alert=True)
            return

        try:
            # Удаляем из всех таблиц
            delete_from_database('users', {'telegram_id': telegram_id})
            delete_from_database('meters_data', {'telegram_id': telegram_id})
            delete_from_database('appeals', {'sender_id': telegram_id})

            bot.answer_callback_query(call.id, "✅ Аккаунт удален", show_alert=True)
            bot.send_message(
                call.message.chat.id,
                "❌ Ваш аккаунт был удален. Для новой регистрации нажмите /start"
            )
            logger.info(f"Пользователь {telegram_id} удалил аккаунт")

        except Exception as e:
            logger.error(f"Ошибка при удалении аккаунта {telegram_id}: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка при удалении", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в  delete_account: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_delete_'))
def cancel_delete(call):
    """Отмена удаления аккаунта"""
    try:
        telegram_id = int(call.data.split('_')[2])
        bot.answer_callback_query(call.id, "❎ Удаление отменено")
        bot.send_message(call.message.chat.id, "Удаление аккаунта отменено")

    except Exception as e:
        logger.error(f"Ошибка в cancel_delete: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['auth'])
def auth(message):
    """
    Обработка команды /aunh -> Запуск процесса авторизации сотрудника
    :param message: Сообщение от пользователя - команда /auth
    :return: None
    """
    try:
        # Проверка регистрации пользователя
        if find_user_by_id('users', message.from_user.id) is None:
            msg = bot.send_message(message.chat.id, "Введите код доступа")
            bot.register_next_step_handler(msg, add_enter_code)
            return

        msg = bot.send_message(message.chat.id, 'Введите код авторизации')
        bot.register_next_step_handler(msg, enter_auth_code)

    except Exception as e:
        logger.error(f"Ошибка в auth: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


def add_enter_code(message):
    try:
        code = message.text
        if code == PASSWORD:
            msg = bot.send_message(message.chat.id, "Bведите код авторизации")
            bot.register_next_step_handler(msg, enter_auth_code)

        elif message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        else:
            msg = bot.send_message(message.chat.id, "❌ Неверный пароль. Попробуйте еще раз:")
            bot.register_next_step_handler(msg, add_enter_code)  # Снова вызываем проверку пароля

    except Exception as e:
        logger.error(f"Ошибка в add_enter_code: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


def enter_auth_code(message):
    """
    Проверка кода авторизации -> атворизация сотруудника
    :param message: Сообщение от пользователя - код авторицации
    :return: None
    """
    try:
        if message.text.strip().lower() == '/cancel':
            bot.send_message(message.chat.id, "❌ Действие отменено")
            return

        user_id = message.from_user.id
        user_name = f'{message.from_user.first_name or ""} {message.from_user.last_name or ""}'
        auth_code = message.text.strip()

        # Получение кода авторизации из БД
        staff_list = select_all('staff')
        for post in staff_list:
            staff_post = post[1]
            code = post[4]
            if auth_code == code:
                update_values('staff',
                              {'telegram_id': user_id, 'name': user_name},
                              {'auth_code': auth_code}
                              )
                bot.send_message(message.chat.id, f'Вы успешно авторизованы как {staff_post}')
                logger.info(f'Пользоватлеь {message.chat.id} авторизован как {staff_post}')
                bot.send_message(find_staff_id('Админ'),
                                 f"⚠️Пользователь {message.from_user.id}: {message.from_user.first_name} {message.from_user.last_name} авторизован как {staff_post}")
                return
            else:
                continue
        else:
            msg = bot.send_message(message.chat.id, "Неверный код авторизации")
            logger.info(f'Пользователь {message.from_user.id} ввел неверный код авторизации')
            bot.register_next_step_handler(msg, enter_auth_code)

    except Exception as e:
        logger.error(f"Ошибка в enter_auth_code: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['send'])
def send_data(message):
    """
    Запуск процесса отправки показаний
    :param message: Сообщение от пользователя - команда /send
    :return: None
    """
    try:
        # Проверка времени отправки
        today = datetime.now().day
        if not (start_collection[0] <= today < end_collection[0]):
            bot.send_message(message.chat.id,
                             "❌ Прием показаний закрыт. Показания принимаются с 23 по 27 число каждого месяца")
            return

        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # Проверка того, что пользователь еще не отправлял показания в этом месяце
        telegram_id = message.from_user.id

        user_data = find_user_by_id('users', telegram_id, 'apartment')
        if user_data:
            apartment = user_data[0]
            current_month_str = f"{current_month:02d}.{current_year}"

            # Проверяем, сдавала ли квартира показания в текущем месяце
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM meters_data WHERE apartment = ? AND month = ?",
                        (apartment, current_month_str))
            already_submitted = cur.fetchone()[0] > 0
            cur.close()
            conn.close()

            if already_submitted:
                bot.send_message(message.chat.id, '✅ Вы уже передали показания в этом месяце')
                return

        # Проверка зарегистрирован ли пользователь
        if telegram_id in temp_users:
            user = temp_users[telegram_id]
        else:
            # Пользователь не зарегистрирован
            user_data = find_user_by_id('users', telegram_id, 'apartment, water_count, electricity_count')
            if not user_data:
                bot.send_message(message.chat.id, "❌ Вы не зарегистрированы. Для начала нажмите /start")
                return

            # Пользователь зарегистрирован. Принимаем данные
            apartment, water_count, electricity_count = user_data
            user = User(telegram_id, apartment, water_count, electricity_count)
            temp_users[telegram_id] = user

        # Кнопки для вывбора счетчика
        month, year = get_month()
        markup = create_meters_markup(user)
        bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в send_data: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data.startswith('meter_'))
def meter_input(call):
    """
    Ввод показаний для выбранного счетчика
    :param call: Вызов функции для конкретного счетчика
    :return: None
    """
    try:
        # Ввод показаний для выбранного счетчика
        meter = call.data.split('_')[1]
        current_editing[call.from_user.id] = meter
        msg = bot.send_message(call.message.chat.id, f"Введите показания для выбранного счетчика:")
        bot.register_next_step_handler(msg, process_value)

    except Exception as e:
        logger.error(f"Ошибка в meter_input: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


def process_value(message):
    """
    Обработка ввода данных
    :param message: Сообщение от пользователя - целое число
    :return: None
    """
    try:
        telegram_id = message.from_user.id
        user = temp_users.get(telegram_id)
        meter = current_editing.get(telegram_id)

        # Проверка на наличие ошибки
        if not user or not meter:
            bot.send_message(message.chat.id, "Ошибка: пользователь или счётчик не найдены")
            return

        # Проверка корректности ввода
        try:
            value = int(message.text.strip())
            if value < 0:
                raise ValueError
        except:
            msg = bot.send_message(message.chat.id, "❌ Введите положительное число")
            bot.register_next_step_handler(msg, process_value)
            return

        # Ввод данных
        user.add_metric(meter, value)
        # Создание нового сообщения с кнопками
        month, year = get_month()
        markup = create_meters_markup(user)
        bot.send_message(message.chat.id, f"📊 Показания за {month} {year}", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в process_value: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.callback_query_handler(func=lambda call: call.data == 'review')
def review(call):
    """
    Проверка введенных данных
    :param call: Вызов функции с требованием проверки данных
    :return: None
    """
    try:
        # Проверка наличия пользователя
        user = temp_users.get(call.from_user.id)
        if not user:
            bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
            return

        # Создание сообщения с проверкой
        markup = create_review_markup(user)
        month, year = get_month()
        bot.send_message(call.message.chat.id, f"📝 Проверка за {month} {year}", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в review: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_value(call):
    """
    Изменение значений
    :param call: Вызов функции с требованием изменить ранее введенные значения
    :return: None
    """
    try:
    # Корректировка значений
        meter = call.data.split('_')[1]
        current_editing[call.from_user.id] = meter
        msg = bot.send_message(call.message.chat.id, f"Введите новое значение для выбранного счетчика")
        bot.register_next_step_handler(msg, process_value)

    except Exception as e:
        logger.error(f"Ошибка в edit_value: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)

@bot.callback_query_handler(func=lambda call: call.data == 'confirm_all')
def confirm_all(call):
    """
    Обработка введенных показаний. Запись в БД
    :param call: вызов функции с требованием записать данные
    :return: None
    """
    try:
        # Проверка существования пользователя
        user = temp_users.get(call.from_user.id)
        if not user:
            bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
            return

        # Получение отчета
        report = user.get_report()

        # Получаем имена счетчиков
        cold_list = cold_water_meters[user.water_count]
        hot_list = hot_water_meters[user.water_count]
        elec_list = electricity_meters[user.electricity_type]

        # Получаем показания из current_meters
        data = current_meters.get(user.telegram_id, {})
        # ХВС
        cw1 = int(data.get(cold_list[0], 0)) if len(cold_list) > 0 else 0
        cw2 = int(data.get(cold_list[1], 0)) if len(cold_list) > 1 else 0
        cw3 = int(data.get(cold_list[2], 0)) if len(cold_list) > 2 else 0

        # ГВС
        hw1 = int(data.get(hot_list[0], 0)) if len(hot_list) > 0 else 0
        hw2 = int(data.get(hot_list[1], 0)) if len(hot_list) > 1 else 0
        hw3 = int(data.get(hot_list[2], 0)) if len(hot_list) > 2 else 0

        # Электричество
        el1 = int(data.get(elec_list[0], 0)) if len(elec_list) > 0 else 0
        el2 = int(data.get(elec_list[1], 0)) if len(elec_list) > 1 else 0

        month = now.strftime('%m.%Y')

        # Вставляем данные
        columns = [
            'telegram_id', 'apartment', 'month',
            'type_water_meter', 'type_electricity_meter',
            'cold_water_1', 'cold_water_2', 'cold_water_3',
            'hot_water_1', 'hot_water_2', 'hot_water_3',
            'electricity_1', 'electricity_2'
        ]
        values = [
            user.telegram_id,
            user.apartment,
            month,
            user.water_count,
            user.electricity_type,
            cw1, cw2, cw3,
            hw1, hw2, hw3,
            el1, el2
        ]
        insert_to_database('meters_data', columns, values)

        # Отправка отчета
        ACCOUNTANT_ID = find_staff_id('Бухгалтер')
        bot.send_message(ACCOUNTANT_ID, f"📨 Показания от кв. {user.apartment}:\n{report}")
        # TODO: !!! Сделать, чтобы у бухгалтера была возможность написать отправителю
        '''
        Варианты: 
        1. Кнопка "Написать отправителю"
        2. Потребовать номер телефона от отправителя и дать ссылку на него 
        '''
        user.clear_metrics()
        temp_users.pop(call.from_user.id, None)
        bot.send_message(call.message.chat.id, "✅ Показания отправлены")
        logger.info(f'Показания переданы. Квартира {user.apartment}')

    except Exception as e:
        logger.error(f"Ошибка в confirm_all: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)

@bot.callback_query_handler(func=lambda call: call.data == 'back_edit')
def back_edit(call):
    """
    Возврат к редактированию ранее введенных данных
    :param call: вызов функции с требованием редактирования данных
    :return: None
    """
    try:
        # Проверка существования пользователя
        user = temp_users.get(call.from_user.id)
        if not user:
            bot.send_message(call.message.chat.id, "Ошибка: пользователь не найден")
            return

        # Создание сообщения с кнопками
        markup = create_meters_markup(user)
        month, year = get_month()
        bot.send_message(call.message.chat.id, f"📊 Возврат к редактированию за {month} {year}", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка в back_edit: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)

@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def cancel(call):
    """
    Отмена ввода показаний
    :param call: Вызов функции с требованием отмены ввода показаний
    :return: None
    """
    try:
        # Отмена ввода
        user = temp_users.get(call.from_user.id)
        if user:
            user.clear_metrics()
            temp_users.pop(call.from_user.id, None)

        bot.send_message(call.message.chat.id, "🚫 Ввод отменён")

    except Exception as e:
        logger.error(f"Ошибка в cancel: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)


@bot.message_handler(commands=['manager', 'accountant', 'electric', 'plumber'])
def handle_address_request(message):
    """
    Выбор получателя обращения / заявки на работу
    :param message: Сообщение от польщователя - команда, соотвествующая получателю обращения
    :return: None
    """
    try:
        # Проверка регистрации пользователя
        if find_user_by_id('users', message.from_user.id) is None:
            bot.send_message(message.chat.id, "Вы не зарегистрированы. Чтобы начать работу введите /start")
            return

        # Определяем тип получателя и текст запроса
        command = message.text.split('@')[0]
        MANAGER_ID = find_staff_id('Председатель')
        ACCOUNTANT_ID = find_staff_id('Бухгалтер')
        PLUMBER_ID = find_staff_id('Сантехник')
        ELECTRIC_ID = find_staff_id('Электрик')
        # TODO: Если что-то срочное предложить пользователю позвонить сантехнику (обсудить)
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
        bot.register_next_step_handler(msg, lambda m: send_address(m, recipient_data[command]))

    except Exception as e:
        logger.error(f"Ошибка в handle_address_request: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)

def send_address(message, recipient_info):
    """
    Запись обращения в БД, отправка получателю
    :param message: Сообщение от пользователя - текст обращения
    :param recipient_info: Информация о получателе обращения
    :return: None
    """
    try:
        global appeals_count
        text = message.text.strip() if message.text else ""
        sender_id = message.from_user.id

        # Получаем данные пользователя
        data = find_user_by_id('users', sender_id, 'name, apartment')
        if not data:
            bot.send_message(message.chat.id, "❌ Ошибка: данные пользователя не найдены")
            return

        user_name, apartment = data

        # Вставляем обращение в БД и получаем его ID
        try:
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO appeals (sender_id, apartment, name, message_text, recipient_post) VALUES (?, ?, ?, ?, ?)",
                (sender_id, apartment, user_name, text, recipient_info['recipient'])
            )
            appeal_id = cur.lastrowid
            conn.commit()

            # Обновляем счетчик обращений
            appeals_count += 1
            with open('count.txt', 'w') as file:
                file.write(str(appeals_count))

        except Exception as e:
            logger.error(f"Ошибка при записи обращения: {e}")
            bot.send_message(message.chat.id, "❌ Ошибка при отправке обращения")
            return
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

        # Кнопка отправки сообщения
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "Ответить",
            callback_data=f"reply_{sender_id}_{message.message_id}_{appeal_id}"
        ))

        # Формируем и отправляем сообщение
        bot.send_message(
            recipient_info['id'],
            f'📨 Обращение от жителя:\n'
            f'👤 [{user_name}](tg://user?id={sender_id})\n'
            f'🏠 Квартира: {apartment}\n\n'
            f'_{text}_',
            parse_mode="Markdown",
            reply_markup=markup
        )

        # Сохраняем данные диалога
        active_dialogs[recipient_info['id']] = {
            'user_id': sender_id,
            'message_id': message.message_id,
            'appeal_id': appeal_id
        }

        # Отправка копии председателю (если получатель не председатель)
        if recipient_info['id'] != find_staff_id('Председатель'):
            bot.send_message(
                find_staff_id('Председатель'),
                f'📨 Обращение от жителя:\n'
                f'‍💻 Получатель: {recipient_info["recipient"]}\n'
                f'👤 Отправитель: [{user_name}](tg://user?id={sender_id})\n'
                f'🏠 Квартира: {apartment}\n\n'
                f'_{text}_',
                parse_mode="Markdown",
            )

        logger.info(f"Отправлено обращение от пользователя {sender_id}. Получатель {recipient_info['recipient']}")
        bot.send_message(message.chat.id, recipient_info['response_success'])

    except Exception as e:
        logger.error(f"Ошибка в send_adress: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)

@bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
def start_staff_reply(call):
    """
    Запрос ответа на обращение от сотрудника
    :param call: вызов функции с требованием ответа на обращение
    :return: None
    """
    try:
        parts = call.data.split('_')
        if len(parts) < 4:
            bot.answer_callback_query(call.id, "❌ Ошибка: неверный формат запроса")
            return

        user_id = int(parts[1])
        message_id = int(parts[2])
        appeal_id = int(parts[3])

        # Сохраняем данные диалога
        active_dialogs[call.from_user.id] = {
            'user_id': user_id,
            'message_id': message_id,
            'appeal_id': appeal_id
        }

        bot.send_message(
            call.from_user.id,
            "✍️ Введите ваш ответ:",
            reply_markup=types.ForceReply(selective=True)
        )

    except Exception as e:
        logger.error(f"Ошибка в start_staff_reply: {e}", exc_info=True)
        try:
            bot.answer_callback_query(call.id, "❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except:
            pass
        handle_error(e)

@bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text == "✍️ Введите ваш ответ:")
def process_staff_reply(message):
    """
    Запись ответа в БД. Отправка ответа пользователю
    :param message: Сообщение от сотрудника - ответ на обращение
    :return: None
    """
    try:
        staff_id = message.from_user.id
        if staff_id not in active_dialogs:
            return

        dialog_data = active_dialogs[staff_id]
        user_id = dialog_data['user_id']
        appeal_id = dialog_data['appeal_id']

        MANAGER_ID = find_staff_id('Председатель')
        ACCOUNTANT_ID = find_staff_id('Бухгалтер')
        ELECTRIC_ID = find_staff_id('Электрик')
        PLUMBER_ID = find_staff_id('Сантехник')

        # Определяем должность отвечающего
        if staff_id == MANAGER_ID:
            staff_position = "председателя ТСЖ"
        elif staff_id == ACCOUNTANT_ID:
            staff_position = "бухгалтера"
        elif staff_id == ELECTRIC_ID:
            staff_position = "электрика"
        elif staff_id == PLUMBER_ID:
            staff_position = "сантехника"
        else:
            staff_position = "администрации"

        # Формируем текст ответа
        bot.send_message(user_id, f"📩 Ответ {staff_position} на ваше обращение:\n\n{message.text}")

        # Обновляем обращение в БД
        try:
            conn = sqlite3.connect(db)
            cur = conn.cursor()
            cur.execute(
                "UPDATE appeals SET answer_text = ?, status = 'closed' WHERE id = ?",
                (message.text, appeal_id)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при обновлении обращения: {e}")
            bot.send_message(staff_id, "❌ Ошибка при сохранении ответа")
            return
        finally:
            if 'cur' in locals():
                cur.close()
            if 'conn' in locals():
                conn.close()

        # Отправляем копию председателю (если отвечающий не председатель)
        if staff_id != find_staff_id('Председатель'):
            user_data = find_user_by_id('users', user_id, 'name, apartment')
            if user_data:
                user_name, apartment = user_data
                bot.send_message(
                    find_staff_id('Председатель'),
                    f'📩 Ответ {staff_position}:\n'
                    f'‍💻 Получатель: {user_name}\n'
                    f'🏠 Квартира: {apartment}\n\n'
                    f'_{message.text}_',
                    parse_mode="Markdown"
                )

        logger.info(f'Ответ {staff_position} на обращение ID {appeal_id}')
        bot.send_message(staff_id, "✅ Ответ отправлен")
        del active_dialogs[staff_id]

    except Exception as e:
        logger.error(f"Ошибка в process_staff_reply: {e}", exc_info=True)
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_unrecognized_input(message):
    """
    Обрабатывает все текстовые сообщения, которые не были обработаны другими обработчиками
    """
    try:
        # Проверяем, зарегистрирован ли пользователь
        user_exists = find_user_by_id('users', message.from_user.id, 'COUNT(*)')

        if user_exists and user_exists[0] > 0:
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
        try:
            bot.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)

def notifications():
    """
    Оработчик напоминаний
    1. Уведомление о начале сбора показаний (для всех)
    2. Напоминание во время сбора показаний (для тех, кто не еще не передал)
    3. Уведомление о завершении сбора (для тех, кто не передал)
        3.1. Отправка отчета бухгалтеру
    :return: None
    """
    scheulder = BackgroundScheduler()
    scheulder.add_job(backup_daily, 'cron', hour=2, minute=0)

    # TODO: !!! Исправить ошбику. Таблица пустая
    while True:
        now = datetime.now()
        current_month = f"{now.month}.{now.year}"

        # Начало сбора показаний
        if now.day == start_collection[0] and now.hour == start_collection[1] and now.minute == start_collection[2]:
            users = select_all('users')
            logger.info("Открыт сбор показаний счетчиков")
            if not scheulder.running:
                scheulder.start()
            for user in users:
                bot.send_message(user[1], "📬 Открыт сбор показаний счетчиков")

        # Напоминание о передаче
        if now.day == notification_time[0] and now.hour == notification_time[1] and now.minute == notification_time[2]:
            users = select_all('users')
            sended_data = select_all('meters_data')
            apartments = []
            for data in sended_data:
                apartments.append(data[2])
            for user in users:
                users_apartment = user[2]
                user_id = user[1]
                if users_apartment not in apartments:
                    bot.send_message(user_id, "⏰ Пора передать показания счетчиков! /send")
                    logger.info(f"Напоминание отправлено пользователю {user_id}")

        # Завершение сбора
        if now.day == end_collection[0] and now.hour == end_collection[1] and now.minute == end_collection[2]:
            ACCOUNTANT_ID = find_staff_id('Бухгалтер')
            send_table(ACCOUNTANT_ID)
            logger.info('Таблица отправлена бухгалтеру')
            if scheulder.running:
                scheulder.shutdown()
            backup_monthly()

        time.sleep(60)


# Глобальный обработчик ошибок
def handle_error(exception):
    try:
        # TODO: Убрать сообщения админу о сетевых ошибках. См. "СЕТЕВЫЕ ОШИБКИ"
        logger.error(f"Глобальная ошибка: {exception}", exc_info=True)
        admin_id = find_staff_id('Админ')
        if admin_id:
            bot.send_message(admin_id, f"⚠️ Ошибка в боте:\n{str(exception)[:500]}")
    except Exception as inner_error:
        # Только логируем, чтобы избежать рекурсии
        print(f"CRITICAL: Error in error handler: {inner_error}")


def init_db():
    """
    Инициализация БД при запуске бота
    :return: None
    """
    try:
        create_table('users', [
            "telegram_id INTEGER UNIQUE",
            "name TEXT",
            "apartment INTEGER",
            "water_count INTEGER",
            "electricity_count INTEGER"
        ])
        create_table('meters_data', [
            "telegram_id INTEGER",
            "apartment INTEGER",
            "month VARCHAR",
            "type_water_meter INTEGER",
            "type_electricity_meter INTEGER",
            "cold_water_1 INTEGER",
            "cold_water_2 INTEGER",
            "cold_water_3 INTEGER",
            "hot_water_1 INTEGER",
            "hot_water_2 INTEGER",
            "hot_water_3 INTEGER",
            "electricity_1 INTEGER",
            "electricity_2 INTEGER"
        ])
        create_table('appeals', [
            'sender_id INTEGER',
            'apartment INTEGER',
            'name TEXT',
            'message_text TEXT',
            'recipient_post TEXT',
            'answer_text TEXT',
            "status TEXT DEFAULT 'open'",
        ])
        create_table('staff', [
            'post TEXT',
            'telegram_id INTEGER',
            'name TEXT',
            'auth_code TEXT'
        ])
    except Exception as e:
        logger.error(f"Ошибка в /init db: {e}", exc_info=True)
        try:
            bot.send_message(find_staff_id('Админ'), "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)

def init_staff():
    """
    Заполениние таблицы сотрудников
    :return: None
    """
    try:
        tablename = 'staff'
        table = select_all(tablename)
        if table:
            return
        columns = ['post', 'auth_code']
        insert_to_database(tablename, columns, ['Админ', ADMIN_CODE])
        insert_to_database(tablename, columns, ['Председатель', MANAGER_CODE])
        insert_to_database(tablename, columns, ['Бухгалтер', ACCOUNTANT_CODE])
        insert_to_database(tablename, columns, ['Сантехник', PLUMBER_CODE])
        insert_to_database(tablename, columns, ['Электрик', ELECTRIC_CODE])
    except Exception as e:
        logger.error(f"Ошибка в init staff: {e}", exc_info=True)
        try:
            bot.send_message(find_staff_id('Админ'), "❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass
        handle_error(e)


def backup_daily(db_path="tsg_database.sql", backup_dir="backups/daily"):
    """
    Создаёт ежедневную резервную копию базы данных.
    Старый бэкап удаляется, создаётся новый.
    """
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, "backup_daily.sql")

    # Удалить старый бэкап, если есть
    if os.path.exists(backup_path):
        os.remove(backup_path)

    shutil.copy2(db_path, backup_path)
    logger.info(f"[✓] Ежедневная резервная копия создана: {backup_path}")
    bot.send_message(find_staff_id('Админ'), "Резервная копия создана (день)")


def backup_monthly(db_path="tsg_database.sql", backup_dir="backups/monthly"):
    """
    Создаёт ежемесячную резервную копию базы данных.
    Хранится отдельно, не перезаписывается.
    """
    os.makedirs(backup_dir, exist_ok=True)
    month_str = datetime.now().strftime("%Y-%m")  # Используем уже импортированный datetime
    backup_path = os.path.join(backup_dir, f"backup_{month_str}.sql")

    if not os.path.exists(backup_path):
        shutil.copy2(db_path, backup_path)
        logger.info(f"[✓] Ежемесячная резервная копия создана: {backup_path}")
        bot.send_message(find_staff_id('Админ'), "Резервная копия создана (месяц)")
    else:
        logger.info(f"[!] Ежемесячная копия уже существует: {backup_path}")
        bot.send_message(find_staff_id('Админ'), "Ежемесячная копия уже существует")


# Запуск
if __name__ == '__main__':
    # Инициализация
    init_db()
    init_staff()
    logger.info('Бот запущен')
    print("Бот запущен")

    # Запускаем фоновые задачи в демон-потоке
    threading.Thread(target=notifications, daemon=True).start()

    # Улучшенная стратегия перезапуска
    restart_delay = 5  # начальная задержка
    max_delay = 300  # максимальная задержка (5 минут)
    consecutive_errors = 0  # счетчик последовательных ошибок
    max_consecutive_errors = 10  # максимальное количество ошибок подряд

    while True:
        try:
            logger.info(f"Запуск polling... (задержка: {restart_delay}сек, ошибок подряд: {consecutive_errors})")

            # Настройка polling с улучшенными параметрами
            bot.polling(
                none_stop=True,
                timeout=90,  # увеличенный timeout
                long_polling_timeout=60,  # увеличенный long_polling timeout
                skip_pending=True,  # пропускать pending updates при перезапуске
                interval=1,  # интервал между запросами
                allowed_updates=None  # или список конкретных update types
            )

            # Если polling завершился без ошибок - сбрасываем счетчики
            restart_delay = 5
            consecutive_errors = 0
            logger.info("Polling завершился нормально, перезапуск")

        except ConnectionResetError as e:
            # Конкретная ошибка "Удаленный хост принудительно разорвал подключение"
            consecutive_errors += 1
            logger.error(f"ConnectionResetError [{consecutive_errors}]: Удаленный хост разорвал соединение: {e}")

            if consecutive_errors >= max_consecutive_errors:
                logger.critical(
                    f"Достигнут лимит ошибок подряд ({max_consecutive_errors}). Приостанавливаю работу на 10 минут.")
                try:
                    bot.send_message(
                        find_staff_id("Админ"),
                        "🔴 КРИТИЧЕСКАЯ ОШИБКА: Достигнут лимит сетевых ошибок. "
                        "Бот приостановлен на 10 минут. Проверьте интернет-соединение."
                    )
                except:
                    pass
                time.sleep(600)  # 10 минут паузы
                consecutive_errors = 0
                restart_delay = 5
                continue

            # Экспоненциальная задержка + рандомизация
            restart_delay = min(restart_delay * 2, max_delay)
            jitter = random.uniform(0.8, 1.2)  # добавляем случайность
            actual_delay = restart_delay * jitter

            try:
                bot.send_message(
                    find_staff_id("Админ"),
                    f"🔌 Соединение разорвано Telegram сервером\n"
                    f"Перезапуск через {actual_delay:.1f}сек\n"
                    f"Ошибок подряд: {consecutive_errors}/{max_consecutive_errors}"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить админа: {notify_error}")

            logger.info(f"Ждем {actual_delay:.1f} секунд перед перезапуском...")
            time.sleep(actual_delay)

        except (ConnectionError, ProtocolError, requests.exceptions.ConnectionError,
                socket.gaierror, socket.timeout, http.client.RemoteDisconnected) as e:
            # Другие сетевые ошибки
            consecutive_errors += 1
            logger.error(f"Сетевая ошибка [{consecutive_errors}]: {type(e).__name__}: {e}")

            restart_delay = min(restart_delay * 1.5, max_delay)
            try:
                bot.send_message(
                    find_staff_id("Админ"),
                    f"🌐 Сетевая ошибка: {type(e).__name__}\n"
                    f"Перезапуск через {restart_delay}сек\n"
                    f"Ошибок подряд: {consecutive_errors}/{max_consecutive_errors}"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить админа: {notify_error}")

            time.sleep(restart_delay)

        except telebot.apihelper.ApiException as e:
            # Ошибки API Telegram (например, лимиты запросов)
            consecutive_errors += 1
            logger.error(f"API Error [{consecutive_errors}]: {e}")

            # Для API ошибок используем более агрессивную задержку
            restart_delay = min(restart_delay * 3, 900)  # максимум 15 минут для API errors
            try:
                bot.send_message(
                    find_staff_id("Админ"),
                    f"📡 Ошибка Telegram API: {str(e)[:100]}\n"
                    f"Перезапуск через {restart_delay}сек\n"
                    "Возможно, превышены лимиты запросов"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить админа: {notify_error}")

            time.sleep(restart_delay)

        except KeyboardInterrupt:
            # Корректный выход по Ctrl+C
            logger.info("Бот остановлен пользователем")
            try:
                bot.send_message(find_staff_id("Админ"), "🛑 Бот остановлен вручную")
            except:
                pass
            break

        except Exception as e:
            # Все остальные непредвиденные ошибки
            consecutive_errors += 1
            logger.error(f"Критическая ошибка [{consecutive_errors}]: {type(e).__name__}: {e}", exc_info=True)

            restart_delay = min(restart_delay * 2, max_delay)
            try:
                bot.send_message(
                    find_staff_id("Админ"),
                    f"⚠️ Непредвиденная ошибка: {type(e).__name__}\n"
                    f"Перезапуск через {restart_delay}сек\n"
                    f"Ошибка: {str(e)[:150]}"
                )
            except Exception as notify_error:
                logger.error(f"Не удалось уведомить админа: {notify_error}")

            time.sleep(restart_delay)

        finally:
            # Всегда выполняем очистку
            logger.info("Очистка ресурсов перед перезапуском...")
            try:
                # Закрываем все соединения (если используются)
                if 'session' in globals():
                    telebot.session.close()
            except Exception as cleanup_error:
                logger.error(f"Ошибка при очистке: {cleanup_error}")

            # Логируем статистику перед перезапуском
            logger.info(f"Статистика: задержка={restart_delay}сек, ошибок подряд={consecutive_errors}")

            # Проверяем соединение с интернетом
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                logger.info("Интернет-соединение активно")
            except socket.error:
                logger.warning("Нет интернет-соединения")
                try:
                    bot.send_message(
                        find_staff_id("Админ"),
                        "🌐 ВНИМАНИЕ: Нет интернет-соединения!\n"
                        "Бот будет пытаться переподключиться..."
                    )
                except:
                    pass