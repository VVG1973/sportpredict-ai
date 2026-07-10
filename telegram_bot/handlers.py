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
                KeyboardButton(text="📞 Связаться с админом")
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
    """Приветствие с продажей VIP и экспрессов"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔥 Экспрессы дня"),
                KeyboardButton(text="💎 VIP прогнозы")
            ],
            [
                KeyboardButton(text="👑 Купить VIP"),
                KeyboardButton(text="📞 Связаться с админом")
            ],
            [
                KeyboardButton(text="ℹ️ Помощь")
            ]
        ],
        resize_keyboard=True
    )

    text = (
        f"👋 <b>{message.from_user.first_name}, добро пожаловать!</b>\n\n"
        f"🎯 <b>SportPredict AI</b> — AI-прогнозы на спорт\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Что вы получаете бесплатно:</b>\n"
        f"• 1 топ-прогноз в день с исходом\n"
        f"• Экспрессы x2 и x3 в обоих каналах\n"
        f"• Кнопки букмекеров для быстрой ставки\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔒 <b>Что скрыто в VIP-канале:</b>\n"
        f"• 5-6 эксклюзивных прогнозов в день\n"
        f"• Исходы скрыты — видны только VIP-подписчикам\n"
        f"• Точность VIP-прогнозов: <b>70%+</b>\n\n"
        f"💎 <b>Купить VIP-прогноз:</b> всего <b>50₽</b>\n"
        f"👑 <b>VIP-подписка:</b> от <b>99₽/день</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎁 <b>Бонус:</b> пригласи друга — получи VIP бесплатно!\n\n"
        f"⚠️ <i>Прогнозы — инфохарактер. 18+</i>"
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

# === СВЯЗЬ С АДМИНОМ ===

@router.message(F.text == "📞 Связаться с админом")
async def button_contact_admin(message: Message):
    """Пересылка сообщения админу"""
    from config import settings
    admin_id = settings.ADMIN_ID
    
    text = (
        "📞 <b>Связь с админом</b>\n\n"
        "Напишите ваше сообщение, и я перешлю его администратору.\n"
        "Нажмите кнопку ниже или просто напишите текст:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Написать сообщение", switch_inline_query_current_chat="")]
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.message(F.text == "ℹ️ Помощь")
async def button_help(message: Message):
    """Помощь"""
    await cmd_help(message)
