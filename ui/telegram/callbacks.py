from ui.telegram.features.registration import select_meters
from ui.telegram.features.settings import *
from ui.telegram.features.send_meters_data import *
from ui.telegram.features.appeals_send import *


def register_callbacks(bot):
    @bot.callback_query_handler(func=lambda call: call.data.startswith('elec_'))
    def electricity_callback(call):
        select_meters(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_apartment_'))
    def edit_apartment(call):
        settings_apartment(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_water_'))
    def edit_water(call):
        settings_water(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_electric_'))
    def edit_electric(call):
        settings_electricity(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_elec_'))
    def confirm_electric(call):
        settings_confirm_electric(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('delete_account_'))
    def delete_account_confirmation(call):
        settings_delete(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_delete_'))
    def delete_account(call):
        settings_confirm_delete(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('meter_'))
    def send_meters_input(call):
        input_meters(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data == 'review')
    def send_meters_review(call):
        review(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
    def send_meters_edit_value(call):
        edit_value(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data == 'confirm_all')
    def send_meters_confirm_all(call):
        confirm_all(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data == 'back_edit')
    def send_meters_back_edit(call):
        back_edit(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data == 'cancel')
    def send_meters_cancel(call):
        cancel(call, bot)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('reply_'))
    def appeals_staff_reply(call):
        start_staff_reply(call, bot)

    @bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.text == "✍️ Введите ваш ответ:")
    def appeals_write_reply(message):
        process_staff_reply(message, bot)