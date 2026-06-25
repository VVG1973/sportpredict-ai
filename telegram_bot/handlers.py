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
    """Обработчик кнопки 'Прогноз на сегодня'"""
    await message.answer(
        "📊 <b>Прогнозы на сегодня</b>\n\n"
        "⏳ Генерирую прогнозы...\n\n"
        "<i>Прогнозы публикуются автоматически в 8:00 МСК</i>\n"
        "Или используйте /stats для просмотра статистики",
        parse_mode="HTML"
    )


@router.message(F.text == "💎 VIP прогнозы")
async def button_vip_forecast(message: Message):
    """Обработчик кнопки 'VIP прогнозы'"""
    await message.answer(
        "💎 <b>VIP прогнозы</b>\n\n"
        "🎯 Точность: 70%+\n"
        "📊 Анализ: 25+ признаков\n"
        "⚡ Обновление: ежедневно в 8:00 МСК\n\n"
        "💰 <b>Тарифы:</b>\n"
        "• 1 день - 149₽\n"
        "• 7 дней - 499₽ (экономия 52%)\n"
        "• 30 дней - 1499₽ (экономия 66%)\n\n"
        "Используйте /vip для покупки",
        parse_mode="HTML"
    )


@router.message(F.text == "⭐ Избранные команды")
async def button_favorites(message: Message):
    """Обработчик кнопки 'Избранные команды'"""
    # Импортируем и вызываем обработчик из favorites_handlers
    try:
        from telegram_bot.favorites import cmd_favorites
        await cmd_favorites(message)
    except Exception as e:
        logger.error(f"Ошибка вызова favorites: {e}")
        await message.answer("❌ Ошибка. Используйте /favorites")


@router.message(F.text == "👥 Пригласить друга")
async def button_invite(message: Message):
    """Обработчик кнопки 'Пригласить друга'"""
    try:
        from telegram_bot.referral_handlers import cmd_invite
        await cmd_invite(message)
    except Exception as e:
        logger.error(f"Ошибка вызова invite: {e}")
        await message.answer("❌ Ошибка. Используйте /invite")


@router.message(F.text == "📊 Моя реферальная программа")
async def button_referral(message: Message):
    """Обработчик кнопки 'Реферальная программа'"""
    try:
        from telegram_bot.referral_handlers import cmd_referral
        await cmd_referral(message)
    except Exception as e:
        logger.error(f"Ошибка вызова referral: {e}")
        await message.answer("❌ Ошибка. Используйте /referral")


@router.message(F.text == "💳 Купить VIP")
async def button_buy_vip(message: Message):
    """Обработчик кнопки 'Купить VIP'"""
    await message.answer(
        "💳 <b>Покупка VIP подписки</b>\n\n"
        "Используйте /vip для просмотра тарифов и оплаты",
        parse_mode="HTML"
    )


@router.message(F.text == "ℹ️ Помощь")
async def button_help(message: Message):
    """Обработчик кнопки 'Помощь'"""
    await cmd_help(message)


@router.message(F.text == "📈 Моя статистика")
async def button_my_stats(message: Message):
    """Обработчик кнопки 'Моя статистика'"""
    await message.answer(
        "📈 <b>Ваша статистика</b>\n\n"
        "Используйте /stats для просмотра общей статистики прогнозов",
        parse_mode="HTML"
    )
