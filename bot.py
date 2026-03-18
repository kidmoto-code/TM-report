#!/usr/bin/env python3

import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from typing import List, Optional
from loguru import logger

from config import TOKEN
from report import UserData, Report  # Используем переименованные модули


class Keyboards:
    """
    Класс для создания и управления клавиатурами телеграм-бота.

    :ivar button_info: Кнопка "Инструкция"
    :vartype button_info: types.KeyboardButton
    :ivar button_check: Кнопка "Проверить данные"
    :vartype button_check: types.KeyboardButton
    :ivar button_full: Кнопка "Подробнее"
    :vartype button_full: types.KeyboardButton
    :ivar button_home: Кнопка "На главную"
    :vartype button_home: types.KeyboardButton
    :ivar button_report: Кнопка "Сформировать отчет"
    :vartype button_report: types.KeyboardButton
    :ivar button_clear: Кнопка "Очистить данные"
    :vartype button_clear: types.KeyboardButton
    """

    def __init__(self):
        """
        Инициализирует клавиатуры бота с набором кнопок.
        """
        # Создание кнопок
        # self.button_info = types.KeyboardButton(text='Инструкция')
        self.button_check = types.KeyboardButton(text='Проверить данные')
        self.button_full = types.KeyboardButton(text='Подробнее')
        self.button_home = types.KeyboardButton(text='На главную')
        self.button_report = types.KeyboardButton(text='Сформировать отчет')
        self.button_clear = types.KeyboardButton(text='Очистить данные')

        # Стартовая клавиатура
        self.kb_start = types.ReplyKeyboardMarkup(
            keyboard=[
                [self.button_check, self.button_clear],
                [self.button_report]
            ],
            resize_keyboard=True
        )

        # Клавиатура для работы с данными
        self.kb_data = types.ReplyKeyboardMarkup(
            keyboard=[
                [self.button_full, self.button_clear],
                [self.button_home],
            ],
            resize_keyboard=True
        )


async def start_bot():
    """
    Основная функция для запуска телеграм-бота.

    Инициализирует бота, диспетчер и обработчики сообщений.
    Токен должен храниться в файле config.py.
    """
    bot = Bot(token=TOKEN)
    dp = Dispatcher(bot=bot)
    keybds = Keyboards()

    @dp.message(lambda message: message.text == 'На главную')
    @dp.message(Command('start'))
    async def cmd_start(message: types.Message) -> None:
        """
        Обработчик команды /start и кнопки 'На главную'.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        await message.answer(
            "Привет! Я бот для проверки товарных знаков.\n"
            "Отправь мне номера ТЗ, заявок или классов МКТУ через пробел.",
            reply_markup=keybds.kb_start
        )

    # @dp.message(lambda message: message.text == 'Инструкция')
    # @dp.message(Command('help'))
    # async def cmd_help(message: types.Message) -> None:
    #     """
    #     Обработчик команды /help и кнопки 'Инструкция'.
    #
    #     :param message: Объект входящего сообщения
    #     :type message: types.Message
    #     """
    #     await message.answer(MANUAL, reply_markup=keybds.kb_start)

    @dp.message(Command('log'))
    async def cmd_log(message: types.Message) -> None:
        """
        Обработчик команды /log для отправки файла логов.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        try:
            await message.answer_document(
                document=FSInputFile('debug.log'),
                reply_markup=keybds.kb_start
            )
        except FileNotFoundError:
            await message.answer("Файл логов не найден", reply_markup=keybds.kb_start)

    @dp.message(lambda message: message.text == 'Проверить данные')
    async def check_data(message: types.Message) -> None:
        """
        Обработчик кнопки 'Проверить данные'.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        stats = UserData.answer()
        await message.answer(stats, reply_markup=keybds.kb_data)

    @dp.message(lambda message: message.text == 'Подробнее')
    async def show_details(message: types.Message) -> None:
        """
        Обработчик кнопки 'Подробнее' для детализации данных.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        details = []
        for data_type in ['MKTU', 'TM', 'APP', 'MADRID']:
            items = UserData.get_data_by_type(data_type)
            if items:
                details.append(f"{data_type}: {', '.join(items)}")

        if details:
            await message.answer("\n".join(details), reply_markup=keybds.kb_start)
        else:
            await message.answer("Нет данных для отображения", reply_markup=keybds.kb_data)

    @dp.message(lambda message: message.text == 'Очистить данные')
    async def clear_data(message: types.Message) -> None:
        """
        Обработчик кнопки 'Очистить данные'.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        UserData.clear()
        await message.answer("Все данные очищены", reply_markup=keybds.kb_start)

    @dp.message(lambda message: message.text == 'Сформировать отчет')
    async def generate_report(message: types.Message) -> None:
        """
        Обработчик кнопки 'Сформировать отчет'.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        await message.answer("Формирую отчет...")

        try:
            Report()
            await message.answer_document(
                document=FSInputFile('report.docx'),
                reply_markup=keybds.kb_start
            )
        except Exception as e:
            await message.answer(f"Ошибка при формировании отчета: {str(e)}")
            logger.error(f"Report generation error: {str(e)}")
        UserData.clear()

    @dp.message()
    async def process_input(message: types.Message) -> None:
        """
        Обработчик ввода данных пользователем.

        :param message: Объект входящего сообщения
        :type message: types.Message
        """
        input_data = message.text.split()
        response = UserData.add_data(input_data)
        await message.answer(response, reply_markup=keybds.kb_start)

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(start_bot())
