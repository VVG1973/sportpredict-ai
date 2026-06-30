"""
Основные обработчики бота
"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import logging

logger = logging.getLogger(__name__)

router = Router()


# === МЕНЮ С КНОПКАМИ ===

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать главное меню с кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Прогноз на сегодня"),
                KeyboardButton(text="💎 VIP прогнозы")
            ],
            [
                KeyboardButton(text="📈 Моя статистика"),
                KeyboardButton(text="⭐ Избранные команды")
            ],
            [
                KeyboardButton(text="👥 Пригласить друга"),
                KeyboardButton(text="📊 Моя реферальная программа")
            ],
            [
                KeyboardButton(text="💳 Купить VIP"),
                KeyboardButton(text="ℹ️ Помощь")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    text = (
        "🎯 <b>Главное меню</b>\n\n"
        "Выберите действие:\n\n"
        "📊 Прогнозы - AI-прогнозы на сегодня\n"
        "💎 VIP - Точные прогнозы (70%+)\n"
        "⭐ Избранные - Ваши любимые команды\n"
        "👥 Пригласить друга - Получи VIP бесплатно!\n"
        "💳 VIP подписка - Доступ к премиум прогнозам"
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветствие с показом меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Прогноз на сегодня"),
                KeyboardButton(text="💎 VIP прогнозы")
            ],
            [
                KeyboardButton(text="⭐ Избранные команды"),
                KeyboardButton(text="👥 Пригласить друга")
            ],
            [
                KeyboardButton(text="💳 Купить VIP"),
                KeyboardButton(text="ℹ️ Помощь")
            ]
        ],
        resize_keyboard=True
    )
    
    text = (
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        "Я <b>SportPredict AI</b> — умный бот для прогнозов на спорт!\n\n"
        "🤖 <b>Что я умею:</b>\n"
        "✅ Анализ 22,000+ матчей\n"
        "✅ AI-прогнозы с точностью 45-55%\n"
        "✅ VIP прогнозы (70%+ уверенность)\n"
        "✅ Уведомления о любимых командах\n"
        "✅ Оплата криптой\n\n"
        "🎁 <b>Бонус:</b> пригласи друга и получи <b>VIP день бесплатно!</b>\n\n"
        "Используй кнопки ниже или команду /menu"
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Показать помощь"""
    text = (
        "ℹ️ <b>Помощь</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Перезапустить бота\n"
        "/menu - Главное меню\n"
        "/favorites - Избранные команды\n"
        "/referral - Реферальная программа\n"
        "/invite - Пригласить друга\n"
        "/stats - Статистика прогнозов\n"
        "/vip - Информация о VIP\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Добавьте любимые команды через /favorites\n"
        "2. Получайте персональные прогнозы\n"
        "3. Приглашайте друзей через /invite\n"
        "4. Получайте VIP бесплатно за каждого друга!\n\n"
        "<b>Поддержка:</b> @sportpredict_support"
    )
    
    await message.answer(text, parse_mode="HTML")


# === ОБРАБОТЧИКИ КНОПОК ===

@router.message(F.text == "📊 Прогноз на сегодня")
async def button_today_forecast(message: Message):
        await message.answer("⏳ Генерирую прогнозы... Это может занять 1-2 минуты.")
        try:
            from main import run_pipeline
            predictions = await run_pipeline()
            if predictions:
                await message.answer(f"✅ Готово! Сгенерировано {len(predictions)} прогнозов и отправлено в канал.")
            else:
                await message.answer("⚠️ На сегодня нет матчей в выбранных лигах.")
        except Exception as e:
            await message.answer(f"❌ Ошибка генерации: {e}")
