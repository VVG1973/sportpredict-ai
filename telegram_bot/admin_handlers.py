from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from config import settings

admin_router = Router()


# 🆕 Меню для обычных подписчиков
USER_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Моя статистика"),
            KeyboardButton(text="❤️ Мои команды"),
        ],
        [
            KeyboardButton(text="👑 VIP-подписка"),
            KeyboardButton(text="❓ Помощь"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)

# 🆕 Меню для админа (дополнительные кнопки)
ADMIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚀 Опубликовать прогнозы"),
            KeyboardButton(text="📈 Общая статистика"),
        ],
        [
            KeyboardButton(text="📊 Моя статистика"),
            KeyboardButton(text="❤️ Мои команды"),
        ],
        [
            KeyboardButton(text="👑 VIP-подписка"),
            KeyboardButton(text="❓ Помощь"),
        ],
    ],
    resize_keyboard=True,
    input_field_placeholder="Админ-панель..."
)


def get_menu_for_user(user_id: int) -> ReplyKeyboardMarkup:
    """Возвращает нужное меню в зависимости от пользователя"""
    if user_id == settings.ADMIN_ID:
        return ADMIN_MENU
    return USER_MENU


@admin_router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик /start"""
    menu = get_menu_for_user(message.from_user.id)
    
    # VIP deep-link
    if message.text and "vip" in message.text.lower():
        text = (
            "👑 <b>VIP-ПОДПИСКА</b>\n\n"
            "🎯 Эксклюзивные прогнозы с уверенностью >80%\n"
            "🔥 Доступ к закрытому VIP-каналу\n"
            "💎 Персональные уведомления\n\n"
            "💰 <b>Выберите тариф:</b>\n"
            "🎫 1 день — 99 ₽\n"
            "📅 Неделя — 499 ₽\n"
            "🗓 Месяц — 1 499 ₽\n"
            "👑 3 месяца — 3 499 ₽"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🎫 1 день — 99₽", callback_data="vip:day"),
                InlineKeyboardButton(text="📅 Неделя — 499₽", callback_data="vip:week"),
            ],
            [
                InlineKeyboardButton(text="🗓 Месяц — 1499₽", callback_data="vip:month"),
                InlineKeyboardButton(text="👑 3 мес — 3499₽", callback_data="vip:quarter"),
            ],
        ])
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        return
    
    # Админ
    if message.from_user.id == settings.ADMIN_ID:
        await message.answer(
            "👋 <b>Привет, босс!</b>\n\n"
            "🎛️ <b>Админ-панель активна</b>\n\n"
            "🚀 Опубликовать прогнозы — прямо сейчас в канал\n"
            "📈 Общая статистика — все прогнозы\n"
            "📊 Моя статистика — личная\n"
            "❤️ Мои команды — подписки\n\n"
            "Или используйте команды:\n"
            "`/publish` `/stats` `/admin`",
            parse_mode="HTML",
            reply_markup=menu
        )
    else:
        # Обычный пользователь
        text = (
            "👋 <b>Добро пожаловать в SportPredict AI!</b>\n\n"
            "🤖 Я бот с прогнозами от нейросети, "
            "обученной на <b>22 000+ реальных матчах</b>.\n\n"
            "🎮 <b>8 видов спорта:</b>\n"
            "⚽ Футбол • 🎾 Теннис • 🏀 Баскетбол\n"
            "🏒 Хоккей • 🎯 CS2 • 🗡️ Dota 2 • 🥊 MMA\n\n"
            "📋 <b>Что я умею:</b>\n"
            "• 📊 Прогнозы каждый день в 8:00 МСК\n"
            "• ❤️ Уведомления о ваших командах\n"
            "• 🏆 Личная статистика\n"
            "• 👑 VIP-подписка\n\n"
            "🎛️ <b>Используйте меню ниже:</b>"
        )
        
        await message.answer(text, parse_mode="HTML", reply_markup=menu)


# === КНОПКИ ДЛЯ АДМИНА ===

@admin_router.message(F.text == "🚀 Опубликовать прогнозы")
async def btn_publish(message: Message):
    """Кнопка публикации (только для админа)"""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Эта функция доступна только админу.")
        return
    
    from main import run_pipeline
    menu = get_menu_for_user(message.from_user.id)
    await message.answer("🚀 Запускаю публикацию прогнозов...", reply_markup=menu)
    await run_pipeline()
    await message.answer("✅ Готово! Проверь канал и личные сообщения.", reply_markup=menu)


@admin_router.message(F.text == "📈 Общая статистика")
async def btn_admin_stats(message: Message):
    """Общая статистика (только для админа)"""
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Эта функция доступна только админу.")
        return
    
    from database.db import Database
    db = Database()
    await db.init()
    stats = await db.get_stats()
    await db.close()
    
    menu = get_menu_for_user(message.from_user.id)
    text = (
        f"📈 <b>Общая статистика канала</b>\n\n"
        f"🏟 Всего прогнозов: <b>{stats['total']}</b>\n"
        f"✅ Выигрышей: <b>{stats['wins']}</b>\n"
        f"❌ Проигрышей: <b>{stats['losses']}</b>\n"
        f"⏳ Ожидают: <b>{stats['pending']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Винрейт:</b> {stats['winrate']:.1f}%\n"
        f"💰 <b>ROI:</b> {stats['roi']:.1f}%\n"
        f"💵 <b>Прибыль:</b> {stats['profit']:.0f} ₽"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=menu)


# === КНОПКИ ДЛЯ ВСЕХ ===

@admin_router.message(F.text == "📊 Моя статистика")
async def btn_stats(message: Message):
    """Личная статистика (для всех)"""
    from database.db import Database
    
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    
    db = Database()
    await db.init()
    stats = await db.get_user_stats(user_id)
    await db.close()
    
    total_activity = stats["views"] + stats["votes"] * 2 + stats["follows"] * 3
    
    if total_activity >= 100:
        level = "🏆 Эксперт"
    elif total_activity >= 50:
        level = "⭐ Продвинутый"
    elif total_activity >= 20:
        level = "🔥 Активный"
    elif total_activity >= 5:
        level = "👍 Новичок+"
    else:
        level = "🌱 Начинающий"
    
    teams_text = ""
    if stats["teams"]:
        teams_text = "\n\n❤️ <b>Любимые команды:</b>\n" + "\n".join([f"• {t}" for t in stats["teams"]])
    
    menu = get_menu_for_user(user_id)
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 <b>{username}</b>\n"
        f"🎖 <b>Уровень:</b> {level}\n\n"
        f"👁 Просмотров: <b>{stats['views']}</b>\n"
        f"❤️ Подписок: <b>{stats['follows']}</b>\n"
        f"🗳 Голосов: <b>{stats['votes']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Активность:</b> {total_activity} очков"
        f"{teams_text}"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=menu)


@admin_router.message(F.text == "❤️ Мои команды")
async def btn_myteams(message: Message):
    """Мои команды (для всех)"""
    from database.db import Database
    
    user_id = message.from_user.id
    db = Database()
    await db.init()
    teams = await db.get_user_follows(user_id)
    await db.close()
    
    if teams:
        teams_text = "\n".join([f"❤️ {t}" for t in teams])
        
        buttons = []
        for team in teams[:6]:
            buttons.append([InlineKeyboardButton(
                text=f"❌ {team}",
                callback_data=f"unfollow:{team}"
            )])
        buttons.append([InlineKeyboardButton(text="➕ Добавить команду", callback_data="add_team_hint")])
        
        await message.answer(
            f"❤️ <b>Ваши любимые команды ({len(teams)}):</b>\n\n"
            f"{teams_text}\n\n"
            f"💡 Нажмите на команду, чтобы отписаться:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    else:
        await message.answer(
            "📭 <b>У вас пока нет подписок</b>\n\n"
            "Напишите команду:\n\n"
            "<code>/follow Man United</code>\n"
            "<code>/follow Barcelona</code>\n"
            "<code>/follow NAVI</code>\n"
            "<code>/follow Team Spirit</code>",
            parse_mode="HTML"
        )


@admin_router.message(F.text == "👑 VIP-подписка")
async def btn_vip(message: Message):
    """VIP-подписка (для всех)"""
    text = (
        "👑 <b>VIP-ПОДПИСКА</b>\n\n"
        "🎯 Эксклюзивные прогнозы с уверенностью >80%\n"
        "🔥 Доступ к закрытому VIP-каналу\n"
        "💎 Персональные уведомления\n\n"
        "💰 <b>Выберите тариф:</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎫 1 день — 99₽", callback_data="vip:day"),
            InlineKeyboardButton(text="📅 Неделя — 499₽", callback_data="vip:week"),
        ],
        [
            InlineKeyboardButton(text="🗓 Месяц — 1499₽", callback_data="vip:month"),
            InlineKeyboardButton(text="👑 3 мес — 3499₽", callback_data="vip:quarter"),
        ],
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(F.text == "❓ Помощь")
async def btn_help(message: Message):
    """Помощь (для всех)"""
    menu = get_menu_for_user(message.from_user.id)
    text = (
        "🤖 <b>SportPredict AI — Справка</b>\n\n"
        "📋 <b>Основные команды:</b>\n"
        "• /start — Запуск бота\n"
        "• /mystats — Моя статистика\n"
        "• /help — Эта справка\n\n"
        "❤️ <b>Любимые команды:</b>\n"
        "• /follow Team — Подписаться\n"
        "• /unfollow Team — Отписаться\n"
        "• /myteams — Мои подписки\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>Примеры:</b>\n"
        "<code>/follow Man United</code>\n"
        "<code>/follow Barcelona</code>\n"
        "<code>/follow NAVI</code>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=menu)


# === CALLBACK ОБРАБОТЧИКИ ===

@admin_router.callback_query(F.data.startswith("unfollow:"))
async def unfollow_from_menu(callback: CallbackQuery):
    """Отписка из списка команд"""
    from database.db import Database
    
    team_name = callback.data.replace("unfollow:", "")
    user_id = callback.from_user.id
    
    db = Database()
    await db.init()
    await db.unfollow_team(user_id, team_name)
    teams = await db.get_user_follows(user_id)
    await db.close()
    
    if teams:
        teams_text = "\n".join([f"❤️ {t}" for t in teams])
        buttons = []
        for team in teams[:6]:
            buttons.append([InlineKeyboardButton(
                text=f"❌ {team}",
                callback_data=f"unfollow:{team}"
            )])
        
        await callback.message.edit_text(
            f"✅ Отписались от <b>{team_name}</b>\n\n"
            f"❤️ <b>Остались ({len(teams)}):</b>\n{teams_text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    else:
        await callback.message.edit_text(
            f"✅ Отписались от <b>{team_name}</b>\n\n"
            f"📭 У вас больше нет подписок.",
            parse_mode="HTML"
        )
    
    await callback.answer()


@admin_router.callback_query(F.data == "add_team_hint")
async def add_team_hint(callback: CallbackQuery):
    """Подсказка как добавить команду"""
    await callback.answer(
        "Напишите в чат: /follow Название команды\n"
        "Например: /follow Man United",
        show_alert=True
    )


# === ТЕКСТОВЫЕ КОМАНДЫ ===

@admin_router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Эта команда доступна только админу.")
        return
    
    from database.db import Database
    db = Database()
    await db.init()
    stats = await db.get_stats()
    await db.close()
    
    menu = get_menu_for_user(message.from_user.id)
    text = (
        f"📈 <b>Общая статистика</b>\n\n"
        f"🏟 Всего: {stats['total']}\n"
        f"✅ Выигрышей: {stats['wins']}\n"
        f"❌ Проигрышей: {stats['losses']}\n"
        f"⏳ Ожидают: {stats['pending']}\n"
        f"🎯 Винрейт: {stats['winrate']:.1f}%\n"
        f"💰 ROI: {stats['roi']:.1f}%"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=menu)


@admin_router.message(Command("publish"))
async def cmd_publish(message: Message):
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("❌ Эта команда доступна только админу.")
        return
    
    from main import run_pipeline
    menu = get_menu_for_user(message.from_user.id)
    await message.answer("🚀 Запускаю публикацию прогнозов...", reply_markup=menu)
    await run_pipeline()
    await message.answer("✅ Готово!", reply_markup=menu)


@admin_router.message(Command("follow"))
async def cmd_follow(message: Message):
    from database.db import Database
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Используйте: <code>/follow Название команды</code>\n\n"
            "Примеры:\n"
            "• <code>/follow Man United</code>\n"
            "• <code>/follow Barcelona</code>\n"
            "• <code>/follow NAVI</code>",
            parse_mode="HTML"
        )
        return
    
    team_name = parts[1].strip()
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    
    db = Database()
    await db.init()
    
    if await db.follow_team(user_id, username, team_name):
        teams = await db.get_user_follows(user_id)
        teams_text = "\n".join([f"• {t}" for t in teams])
        
        menu = get_menu_for_user(user_id)
        await message.answer(
            f"✅ <b>Вы подписались на {team_name}!</b>\n\n"
            f"📋 <b>Ваши команды ({len(teams)}):</b>\n{teams_text}",
            parse_mode="HTML",
            reply_markup=menu
        )
    
    await db.close()


@admin_router.message(Command("unfollow"))
async def cmd_unfollow(message: Message):
    from database.db import Database
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите команду: <code>/unfollow Man United</code>",
            parse_mode="HTML"
        )
        return
    
    team_name = parts[1].strip()
    user_id = message.from_user.id
    
    db = Database()
    await db.init()
    await db.unfollow_team(user_id, team_name)
    teams = await db.get_user_follows(user_id)
    await db.close()
    
    menu = get_menu_for_user(user_id)
    if teams:
        teams_text = "\n".join([f"• {t}" for t in teams])
        await message.answer(
            f"✅ Отписались от <b>{team_name}</b>\n\n"
            f"📋 <b>Остались ({len(teams)}):</b>\n{teams_text}",
            parse_mode="HTML",
            reply_markup=menu
        )
    else:
        await message.answer(
            f"✅ Отписались от <b>{team_name}</b>\n\n"
            f"📭 У вас больше нет подписок.",
            parse_mode="HTML",
            reply_markup=menu
        )


@admin_router.message(Command("myteams"))
async def cmd_myteams(message: Message):
    from database.db import Database
    
    user_id = message.from_user.id
    db = Database()
    await db.init()
    teams = await db.get_user_follows(user_id)
    await db.close()
    
    menu = get_menu_for_user(user_id)
    if teams:
        teams_text = "\n".join([f"❤️ {t}" for t in teams])
        await message.answer(
            f"❤️ <b>Ваши команды ({len(teams)}):</b>\n\n{teams_text}",
            parse_mode="HTML",
            reply_markup=menu
        )
    else:
        await message.answer(
            "📭 У вас пока нет подписок\n\n"
            "Используйте <code>/follow Team</code>",
            parse_mode="HTML",
            reply_markup=menu
        )


@admin_router.message(Command("mystats"))
async def cmd_mystats(message: Message):
    from database.db import Database
    
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name
    
    db = Database()
    await db.init()
    stats = await db.get_user_stats(user_id)
    await db.close()
    
    total_activity = stats["views"] + stats["votes"] * 2 + stats["follows"] * 3
    
    if total_activity >= 100:
        level = "🏆 Эксперт"
    elif total_activity >= 50:
        level = "⭐ Продвинутый"
    elif total_activity >= 20:
        level = "🔥 Активный"
    elif total_activity >= 5:
        level = "👍 Новичок+"
    else:
        level = "🌱 Начинающий"
    
    teams_text = ""
    if stats["teams"]:
        teams_text = "\n\n❤️ <b>Любимые команды:</b>\n" + "\n".join([f"• {t}" for t in stats["teams"]])
    
    menu = get_menu_for_user(user_id)
    text = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"👤 <b>{username}</b>\n"
        f"🎖 <b>Уровень:</b> {level}\n\n"
        f"👁 Просмотров: <b>{stats['views']}</b>\n"
        f"❤️ Подписок: <b>{stats['follows']}</b>\n"
        f"🗳 Голосов: <b>{stats['votes']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Активность:</b> {total_activity} очков"
        f"{teams_text}"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=menu)


@admin_router.message(Command("help"))
async def cmd_help(message: Message):
    menu = get_menu_for_user(message.from_user.id)
    text = (
        "🤖 <b>SportPredict AI — Справка</b>\n\n"
        "📋 <b>Основные команды:</b>\n"
        "• /start — Запуск бота\n"
        "• /mystats — Моя статистика\n"
        "• /help — Эта справка\n\n"
        "❤️ <b>Любимые команды:</b>\n"
        "• /follow Team — Подписаться\n"
        "• /unfollow Team — Отписаться\n"
        "• /myteams — Мои подписки\n\n"
        "💡 Или используйте кнопки меню ниже!"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=menu)


@admin_router.message(Command("menu"))
async def cmd_menu(message: Message):
    menu = get_menu_for_user(message.from_user.id)
    await message.answer(
        "🎛️ <b>Главное меню</b>\n\n"
        "Выберите действие кнопкой:",
        reply_markup=menu,
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "show_vip_menu")
async def show_vip_menu(callback: CallbackQuery):
    text = (
        "👑 <b>VIP-ПОДПИСКА</b>\n\n"
        "🎯 Эксклюзивные прогнозы с уверенностью >80%\n"
        "🔥 Доступ к закрытому VIP-каналу\n\n"
        "💰 <b>Выберите тариф:</b>\n"
        "🎫 1 день — 99 ₽\n"
        "📅 Неделя — 499 ₽\n"
        "🗓 Месяц — 1 499 ₽\n"
        "👑 3 месяца — 3 499 ₽"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎫 1 день — 99₽", callback_data="vip:day"),
            InlineKeyboardButton(text="📅 Неделя — 499₽", callback_data="vip:week"),
        ],
        [
            InlineKeyboardButton(text="🗓 Месяц — 1499₽", callback_data="vip:month"),
            InlineKeyboardButton(text="👑 3 мес — 3499₽", callback_data="vip:quarter"),
        ],
    ])
    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("vip:"))
async def process_vip_callback(callback: CallbackQuery):
    from telegram_bot.vip_manager import VIPManager, CryptoBotService, SubscriptionManager
    
    plan = callback.data.split(":")[1]
    user_id = callback.from_user.id
    username = callback.from_user.username or "unknown"
    
    vip_manager = VIPManager(callback.bot)
    service = CryptoBotService()
    manager = SubscriptionManager()
    await manager.init()
    
    prices = {"day": 99, "week": 499, "month": 1499, "quarter": 3499}
    amount = prices.get(plan, 0)
    
    try:
        invoice = await service.create_invoice(amount=amount, description=f"VIP {plan}")
        
        await manager.save_invoice(
            invoice_id=invoice["invoice_id"],
            user_id=user_id,
            username=username,
            plan=plan,
            amount=amount
        )
        
        await callback.message.answer(
            f"💳 <b>Оплата VIP ({plan})</b>\n\n"
            f"💰 Сумма: {amount} ₽\n\n"
            f"🔗 <a href='{invoice['pay_url']}'>👉 ОПЛАТИТЬ</a>\n\n"
            f"⏳ После оплаты VIP-ссылка придёт автоматически.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка создания инвойса: {e}")
    
    await service.close()
    await callback.answer()
