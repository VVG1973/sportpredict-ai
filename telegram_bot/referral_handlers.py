"""
Обработчики для реферальной программы
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from database.db import Database
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = Router()
db = Database()


async def extend_user_vip(user_id: int, days: int = 1):
    """Продлевает VIP пользователю на указанное количество дней"""
    try:
        await db.init()
        
        # Проверяем, есть ли активная подписка
        cursor = await db.conn.execute(
            "SELECT expires_at FROM subscriptions WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if row and row[0]:
            # Продлеваем существующую подписку
            current_expires = datetime.fromisoformat(row[0].replace("Z", "+00:00")) if isinstance(row[0], str) else row[0]
            if current_expires < datetime.now():
                current_expires = datetime.now()
            new_expires = current_expires + timedelta(days=days)
            
            await db.conn.execute(
                "UPDATE subscriptions SET expires_at = ? WHERE user_id = ?",
                (new_expires.isoformat(), user_id)
            )
        else:
            # Создаём новую подписку
            expires_at = datetime.now() + timedelta(days=days)
            await db.conn.execute("""
                INSERT OR REPLACE INTO subscriptions 
                (user_id, username, plan, status, expires_at)
                VALUES (?, ?, 'referral', 'active', ?)
            """, (user_id, f"user_{user_id}", expires_at.isoformat()))
        
        await db.conn.commit()
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
                await db.init()
                existing_ref = await db.get_referral_by_user(new_user_id)
                
                if not existing_ref:
                    # Регистрируем реферала
                    await db.add_referral(referrer_id, new_user_id, new_user_username)
                    
                    # Даём награду рефереру (1 день VIP)
                    await extend_user_vip(referrer_id, days=1)
                    
                    # Уведомляем реферера
                    try:
                        await message.bot.send_message(
                            chat_id=referrer_id,
                            text=f"🎉 <b>Новый друг присоединился!</b>\n\n"
                                 f"👤 {new_user_username} зарегистрировался по вашей ссылке\n"
                                 f"🎁 Вам начислен <b>1 день VIP бесплатно!</b>\n\n"
                                 f"Используйте /referral чтобы пригласить ещё друзей",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Не удалось уведомить реферера {referrer_id}: {e}")
                    
                    logger.info(f"✅ Реферал: {new_user_username} приглашён пользователем {referrer_id}")
        
        # Отправляем информацию о реферальной программе
        await cmd_referral(message)
        
    except Exception as e:
        logger.error(f"Ошибка обработки реферальной ссылки: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.message(Command("referral"))
async def cmd_referral(message: Message):
    """Показать реферальную программу"""
    try:
        await db.init()
        user_id = message.from_user.id
        
        stats = await db.get_referral_stats(user_id)
        referrals = await db.get_user_referrals(user_id)
        
        bot_info = await message.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        
        text = f"👥 <b>Реферальная программа</b>\n\n"
        text += f"Приглашайте друзей и получайте <b>VIP бесплатно!</b>\n\n"
        text += f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n"
        text += f"📊 <b>Ваша статистика:</b>\n"
        text += f"👤 Приглашено друзей: <b>{stats['total']}</b>\n"
        text += f"🎁 Получено VIP дней: <b>{stats['total']}</b>\n\n"
        
        if referrals:
            text += f"📋 <b>История приглашений:</b>\n"
            for ref in referrals[:10]:
                text += f"• {ref['username']} ({ref['created_at'][:10]})\n"
        else:
            text += f"📋 <b>История приглашений:</b>\n"
            text += f"<i>Пока никого не пригласили</i>\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📤 Поделиться ссылкой",
                switch_inline_query=f"🎯 AI-прогнозы на спорт с точностью 50%+\n\n🔗 {ref_link}\n\nПолучи VIP день бесплатно при регистрации!"
            )],
            [InlineKeyboardButton(
                text="📊 Моя статистика",
                callback_data="ref_stats"
            )]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)
        
    except Exception as e:
        logger.error(f"Ошибка в /referral: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")


@router.callback_query(F.data == "ref_stats")
async def callback_ref_stats(callback: CallbackQuery):
    """Показать детальную статистику рефералов"""
    try:
        await db.init()
        user_id = callback.from_user.id
        
        stats = await db.get_referral_stats(user_id)
        
        text = f"📊 <b>Детальная статистика</b>\n\n"
        text += f"👤 Всего приглашено: <b>{stats['total']}</b>\n"
        text += f"🎁 VIP дней получено: <b>{stats['total']}</b>\n"
        text += f"💰 Эквивалент в рублях: <b>{stats['total'] * 149}₽</b>\n\n"
        text += f"<i>Каждый приглашённый друг = 1 день VIP (149₽)</i>"
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка ref_stats: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
