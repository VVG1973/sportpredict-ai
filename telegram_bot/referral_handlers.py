"""
Обработчики для реферальной программы
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from database.db import Database
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = Router()


async def _get_db():
    """Создаёт и инициализирует подключение к БД"""
    db = Database()
    await db.init()
    return db


async def extend_user_vip(user_id: int, days: int = 1):
    """Продлевает VIP пользователю на указанное количество дней"""
    try:
        db = await _get_db()
        
        cursor = await db.conn.execute(
            "SELECT expires_at FROM subscriptions WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if row and row[0]:
            current_expires = datetime.fromisoformat(row[0].replace("Z", "+00:00")) if isinstance(row[0], str) else row[0]
            if current_expires < datetime.now():
                current_expires = datetime.now()
            new_expires = current_expires + timedelta(days=days)
            
            await db.conn.execute(
                "UPDATE subscriptions SET expires_at = ? WHERE user_id = ?",
                (new_expires.isoformat(), user_id)
            )
        else:
            expires_at = datetime.now() + timedelta(days=days)
            await db.conn.execute("""
                INSERT OR REPLACE INTO subscriptions 
                (user_id, username, plan, status, expires_at)
                VALUES (?, ?, 'referral', 'active', ?)
            """, (user_id, f"user_{user_id}", expires_at.isoformat()))
        
        pass  # asyncpg uses autocommit
        logger.info(f"✅ VIP продлён для {user_id} на {days} дней")
        return True
    except Exception as e:
        logger.error(f"Ошибка продления VIP: {e}")
        return False


@router.message(CommandStart(deep_link=True))
async def cmd_start_with_ref(message: Message, command: CommandStart):
    """Обработка старта с реферальной ссылкой"""
    try:
        args = command.args
        if args and args.startswith('ref_'):
            referrer_id = int(args.replace('ref_', ''))
            new_user_id = message.from_user.id
            new_user_username = message.from_user.username or f"user_{new_user_id}"
            
            if referrer_id != new_user_id:
                db = await _get_db()
                existing_ref = await db.get_referral_by_user(new_user_id)
                
                if not existing_ref:
                    await db.add_referral(referrer_id, new_user_id, new_user_username)
                    await extend_user_vip(referrer_id, days=7)

                    try:
                        await message.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 <b>Новый друг присоединился!</b>\n\n"
                                 f"👤 {new_user_username} зарегистрировался по вашей ссылке\n"
                                 f"🎁 Вам начислена <b>неделя VIP бесплатно!</b>\n\n"
                                 f"Используйте /invite чтобы пригласить ещё друзей",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")
                    
                    logger.info(f"✅ Реферал: {new_user_username} приглашён пользователем {referrer_id}")
        
        await cmd_referral(message)
        
    except Exception as e:
        logger.error(f"Ошибка обработки реферальной ссылки: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("referral"))
async def cmd_referral(message: Message):
    """Показать реферальную программу"""
    try:
        db = await _get_db()
        user_id = message.from_user.id
        
        stats = await db.get_referral_stats(user_id)
        referrals = await db.get_user_referrals(user_id)
        
        bot_info = await message.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        text = f"👥 <b>Реферальная программа</b>\n\n"
        text += f"Приглашайте друзей и получайте <b>VIP бесплатно!</b>\n\n"
        text += f"🔗 <b>Ваша персональная ссылка:</b>\n<code>{ref_link}</code>\n\n"
        text += f"📊 <b>Ваша статистика:</b>\n"
        text += f"👤 Приглашено друзей: <b>{stats['total']}</b>\n"
        text += f"🎁 Получено VIP-недель: <b>{stats['total']}</b>\n"
        text += f"💰 Сэкономлено: <b>{stats['total'] * 7 * 99}₽</b>\n\n"
        
        if referrals:
            text += f"📋 <b>Ваши друзья:</b>\n"
            for ref in referrals[:10]:
                text += f"• {ref['username']} ({ref['created_at'][:10]})\n"
        else:
            text += f"📋 <b>Пока никого не пригласили</b>\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Создать приглашение для друга",
                callback_data="create_invite"
            )],
            [InlineKeyboardButton(
                text="📊 Полная статистика",
                callback_data="ref_stats"
            )]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
        
    except Exception as e:
        logger.error(f"Ошибка в /referral: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")


@router.message(Command("invite"))
async def cmd_invite(message: Message):
    """Создать персональное приглашение для отправки другу"""
    try:
        db = await _get_db()
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name or "друг"
        
        bot_info = await message.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        # Персональное приглашение с именем пользователя
        invite_text = (
            f"🎯 <b>AI-прогнозы с высокой вероятностью</b>\n\n"
            f"🤖 <b>{bot_info.username}</b> использует нейросеть для анализа:\n"
            f"• Статистику команд и H2H\n"
            f"• Коэффициенты букмекеров\n"
            f"• Текущую форму игроков\n\n"
            f"📊 Обычные прогнозы: <b>от 61%</b>\n"
            f"🔒 VIP-прогнозы: <b>от 71%</b>\n\n"
            f"🎁 <b>Попробуй бесплатно — VIP-неделя:</b>\n{ref_link}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Бот полностью бесплатный, есть VIP опции</i>"
        )
        
        # Кнопки для удобной отправки
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Отправить другу",
                switch_inline_query=f"🎯 AI-прогнозы на спорт! Регистрируйся по моей ссылке: {ref_link}"
            )],
            [InlineKeyboardButton(
                text="📋 Скопировать текст приглашения",
                callback_data="copy_invite"
            )],
            [InlineKeyboardButton(
                text="🔗 Показать мою ссылку",
                callback_data="show_ref_link"
            )]
        ])
        
        await message.answer(
            invite_text, 
            reply_markup=keyboard, 
            parse_mode="HTML", 
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка в /invite: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data == "create_invite")
async def create_invite_callback(callback: CallbackQuery):
    """Обработчик кнопки 'Создать приглашение'"""
    try:
        db = await _get_db()
        user_id = callback.from_user.id
        username = callback.from_user.username or callback.from_user.first_name or "друг"
        
        bot_info = await callback.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        invite_text = (
            f"🎯 <b>AI-прогнозы с высокой вероятностью</b>\n\n"
            f"🤖 @{bot_info.username} использует нейросеть для анализа:\n"
            f"• Статистику команд и H2H\n"
            f"• Коэффициенты букмекеров\n"
            f"• Текущую форму игроков\n\n"
            f"📊 Обычные прогнозы: <b>от 61%</b>\n"
            f"🔒 VIP-прогнозы: <b>от 71%</b>\n\n"
            f"🎁 <b>Попробуй бесплатно — VIP-неделя:</b>\n{ref_link}\n\n"
            f"💡 <i>Бот полностью бесплатный, есть VIP опции</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Отправить это сообщение",
                switch_inline_query=invite_text
            )]
        ])
        
        await callback.message.answer(
            "✅ <b>Ваше персональное приглашение готово!</b>\n\n"
            "Нажмите кнопку ниже, чтобы отправить его другу:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка create_invite: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "copy_invite")
async def copy_invite_callback(callback: CallbackQuery):
    """Показать текст для копирования"""
    try:
        db = await _get_db()
        user_id = callback.from_user.id
        username = callback.from_user.username or callback.from_user.first_name or "друг"
        
        bot_info = await callback.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        text = (
            f"📋 <b>Скопируйте этот текст и отправьте другу:</b>\n\n"
            f"<code>🎯 AI-прогнозы с высокой вероятностью\n\n"
            f"🤖 @{bot_info.username} использует нейросеть для анализа:\n"
            f"• Статистику команд и H2H\n"
            f"• Коэффициенты букмекеров\n"
            f"• Текущую форму игроков\n\n"
            f"📊 Обычные прогнозы: от 61%\n"
            f"🔒 VIP-прогнозы: от 71%\n\n"
            f"🎁 Попробуй бесплатно — VIP-неделя:\n{ref_link}</code>"
        )
        
        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer("Текст отправлен ниже!")
        
    except Exception as e:
        logger.error(f"Ошибка copy_invite: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "show_ref_link")
async def show_ref_link_callback(callback: CallbackQuery):
    """Показать реферальную ссылку"""
    try:
        db = await _get_db()
        user_id = callback.from_user.id
        bot_info = await callback.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        text = (
            f"🔗 <b>Ваша персональная ссылка:</b>\n\n"
            f"<code>{ref_link}</code>\n\n"
            f"<i>Скопируйте и отправьте друзьям!</i>"
        )
        
        await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка show_ref_link: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "ref_stats")
async def callback_ref_stats(callback: CallbackQuery):
    """Показать детальную статистику рефералов"""
    try:
        db = await _get_db()
        user_id = callback.from_user.id
        
        stats = await db.get_referral_stats(user_id)
        
        text = f"📊 <b>Детальная статистика</b>\n\n"
        text += f"👤 Всего приглашено: <b>{stats['total']}</b>\n"
        text += f"🎁 VIP-недель получено: <b>{stats['total']}</b>\n"
        text += f"💰 Эквивалент в рублях: <b>{stats['total'] * 7 * 99}₽</b>\n\n"
        text += f"<i>Каждый приглашённый друг = неделя VIP (693₽)</i>"
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка ref_stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.message(F.text == "👥 Пригласить друга")
async def button_invite(message: Message):
    """Обработчик кнопки 'Пригласить друга' в меню"""
    await cmd_invite(message)


@router.message(F.text == "📊 Моя реферальная программа")
async def button_referral(message: Message):
    """Обработчик кнопки 'Реферальная программа' в меню"""
    await cmd_referral(message)
