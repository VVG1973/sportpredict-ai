"""
Обработчики для любимых команд пользователей
Поддерживает: выбор из списка + ручной ввод (на русском или английском)
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.db import Database
import logging

logger = logging.getLogger(__name__)

router = Router()
db = Database()


# === FSM для ручного ввода команды ===
class FavoriteTeamStates(StatesGroup):
    waiting_for_team_name = State()


# === Расширенный список команд по регионам и лигам ===
POPULAR_TEAMS = {
    "🏴 Англия (Premier League)": [
        "Manchester United", "Manchester City", "Liverpool", "Chelsea", "Arsenal", 
        "Tottenham", "Newcastle United", "Aston Villa", "West Ham", "Brighton"
    ],
    "🇪🇸 Испания (La Liga)": [
        "Real Madrid", "Barcelona", "Atletico Madrid", "Sevilla", "Real Sociedad", 
        "Valencia", "Athletic Bilbao", "Villarreal"
    ],
    "🇩🇪 Германия (Bundesliga)": [
        "Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Bayer Leverkusen", 
        "Eintracht Frankfurt", "Wolfsburg"
    ],
    "🇮🇹 Италия (Serie A)": [
        "Juventus", "AC Milan", "Inter Milan", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina"
    ],
    "🇫🇷 Франция (Ligue 1)": [
        "PSG", "Marseille", "Lyon", "Monaco", "Lille", "Nice"
    ],
    "🇷🇺 Россия (РПЛ)": [
        "Zenit", "Spartak Moscow", "CSKA Moscow", "Lokomotiv Moscow", 
        "Dynamo Moscow", "Krasnodar", "Rostov", "Rubin Kazan"
    ],
    "🇷🇺 Россия (ФНЛ)": [
        "Baltika Kaliningrad", "Torpedo Moscow", "Alania Vladikavkaz", 
        "SKA-Khabarovsk", "Rodina Moscow", "Sokol Saratov"
    ],
    "🇺🇦 Украина (УПЛ)": [
        "Shakhtar Donetsk", "Dynamo Kyiv", "Zorya Luhansk", "Dnipro-1", "Vorskla Poltava"
    ],
    "🌍 Еврокубки / Сборные": [
        "Real Madrid", "Manchester City", "Bayern Munich", "PSG", 
        "Inter Milan", "Barcelona"
    ],
}


# === Максимум избранных команд ===
MAX_FAVORITES = 10


@router.message(Command("favorites"))
async def cmd_favorites(message: Message, state: FSMContext):
    """Показать избранные команды"""
    # Сбрасываем любое активное состояние
    await state.clear()
    
    try:
        await db.init()
        favorites = await db.get_user_favorites(message.from_user.id)
        
        if not favorites:
            text = "⭐ <b>У вас пока нет избранных команд</b>\n\n"
            text += "Выберите команды, за которыми хотите следить, или введите название вручную!\n\n"
            text += f"<i>Мы пришлём прогноз за 1 час до матча ваших команд.</i>"
        else:
            text = f"⭐ <b>Ваши избранные команды ({len(favorites)}/{MAX_FAVORITES}):</b>\n\n"
            for team in favorites:
                text += f"✅ {team}\n"
            text += f"\n👇 Добавьте ещё (максимум {MAX_FAVORITES}) или удалите ненужные:"
        
        keyboard = _build_teams_keyboard(favorites)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в /favorites: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")


def _build_teams_keyboard(user_favorites: list) -> InlineKeyboardMarkup:
    """Строит клавиатуру с командами по лигам"""
    buttons = []
    
    # Кнопка ручного ввода (всегда сверху)
    buttons.append([InlineKeyboardButton(
        text="✏️ Ввести свою команду вручную",
        callback_data="fav_manual_input"
    )])
    buttons.append([InlineKeyboardButton(
        text="📋 Показать список по лигам",
        callback_data="fav_show_leagues"
    )])
    
    # Если есть избранные - добавляем кнопку "Готово"
    if user_favorites:
        buttons.append([InlineKeyboardButton(
            text="✅ Готово",
            callback_data="fav_done"
        )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_leagues_keyboard() -> InlineKeyboardMarkup:
    """Строит клавиатуру со списком лиг"""
    buttons = []
    for league_name in POPULAR_TEAMS.keys():
        buttons.append([InlineKeyboardButton(
            text=league_name,
            callback_data=f"fav_league:{league_name}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад",
        callback_data="fav_back_to_main"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_teams_in_league_keyboard(league_name: str, user_favorites: list) -> InlineKeyboardMarkup:
    """Строит клавиатуру с командами из конкретной лиги"""
    buttons = []
    teams = POPULAR_TEAMS.get(league_name, [])
    row = []
    
    for team in teams:
        is_favorite = team in user_favorites
        emoji = "⭐" if is_favorite else "➕"
        callback = f"fav_toggle:{team}"
        
        row.append(InlineKeyboardButton(
            text=f"{emoji} {team}",
            callback_data=callback
        ))
        
        if len(row) == 1:  # Одна команда в ряд (названия длинные)
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(
        text="◀️ К списку лиг",
        callback_data="fav_show_leagues"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("invite"))
async def cmd_invite_placeholder(message: Message):
    """Заглушка - переадресуем к referral_handlers"""
    try:
        from telegram_bot.referral_handlers import cmd_invite
        await cmd_invite(message)
    except Exception as e:
        logger.error(f"Ошибка invite: {e}")


# === Кнопка "Показать список по лигам" ===
@router.callback_query(F.data == "fav_show_leagues")
async def show_leagues(callback: CallbackQuery):
    """Показать список лиг для выбора"""
    try:
        await db.init()
        user_id = callback.from_user.id
        favorites = await db.get_user_favorites(user_id)
        
        text = (
            f"🌍 <b>Выберите лигу</b>\n\n"
            f"Ваши избранные: <b>{len(favorites)}/{MAX_FAVORITES}</b>\n\n"
            f"<i>Нажмите на лигу, чтобы увидеть команды:</i>"
        )
        
        keyboard = _build_leagues_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка show_leagues: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# === Кнопка "Назад в главное меню" ===
@router.callback_query(F.data == "fav_back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Вернуться в главное меню favorites"""
    await state.clear()
    try:
        await db.init()
        favorites = await db.get_user_favorites(callback.from_user.id)
        
        if not favorites:
            text = "⭐ <b>У вас пока нет избранных команд</b>\n\n"
            text += "Выберите из списка или введите вручную!"
        else:
            text = f"⭐ <b>Ваши избранные команды ({len(favorites)}/{MAX_FAVORITES}):</b>\n\n"
            for team in favorites:
                text += f"✅ {team}\n"
        
        keyboard = _build_teams_keyboard(favorites)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка back_to_main: {e}")


# === Выбор конкретной лиги ===
@router.callback_query(F.data.startswith("fav_league:"))
async def show_league_teams(callback: CallbackQuery):
    """Показать команды из выбранной лиги"""
    try:
        await db.init()
        league_name = callback.data.split(":", 1)[1]
        user_id = callback.from_user.id
        favorites = await db.get_user_favorites(user_id)
        
        text = (
            f"⚽ <b>{league_name}</b>\n\n"
            f"Ваши избранные: <b>{len(favorites)}/{MAX_FAVORITES}</b>\n\n"
            f"Нажмите на команду, чтобы добавить/удалить:"
        )
        
        keyboard = _build_teams_in_league_keyboard(league_name, favorites)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка show_league_teams: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# === Переключение избранного (добавить/удалить) ===
@router.callback_query(F.data.startswith("fav_toggle:"))
async def toggle_favorite(callback: CallbackQuery):
    """Добавить/удалить команду из избранного"""
    try:
        await db.init()
        team = callback.data.split(":", 1)[1]
        user_id = callback.from_user.id
        
        favorites = await db.get_user_favorites(user_id)
        
        if team in favorites:
            await db.remove_favorite_team(user_id, team)
            await callback.answer(f"❌ {team} удалена", show_alert=False)
        else:
            if len(favorites) >= MAX_FAVORITES:
                await callback.answer(f"⚠️ Максимум {MAX_FAVORITES} команд!", show_alert=True)
                return
            await db.add_favorite_team(user_id, team)
            await callback.answer(f"⭐ {team} добавлена!", show_alert=False)
        
        # Обновляем список (возвращаемся к лигам)
        new_favorites = await db.get_user_favorites(user_id)
        
        text = (
            f"🌍 <b>Выберите лигу</b>\n\n"
            f"Ваши избранные: <b>{len(new_favorites)}/{MAX_FAVORITES}</b>"
        )
        
        keyboard = _build_leagues_keyboard()
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка toggle_favorite: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# === Ручной ввод команды (FSM) ===
@router.callback_query(F.data == "fav_manual_input")
async def start_manual_input(callback: CallbackQuery, state: FSMContext):
    """Начать процесс ручного ввода команды"""
    try:
        await db.init()
        favorites = await db.get_user_favorites(callback.from_user.id)
        
        if len(favorites) >= MAX_FAVORITES:
            await callback.answer(f"⚠️ Достигнут лимит {MAX_FAVORITES} команд!", show_alert=True)
            return
        
        # Устанавливаем состояние ожидания ввода
        await state.set_state(FavoriteTeamStates.waiting_for_team_name)
        
        text = (
            f"✏️ <b>Введите название команды</b>\n\n"
            f"Можно на <b>русском</b> или <b>английском</b> языке.\n\n"
            f"<b>Примеры:</b>\n"
            f"• <code>Spartak Moscow</code>\n"
            f"• <code>Спартак Москва</code>\n"
            f"• <code>Manchester United</code>\n"
            f"• <code>Барселона</code>\n\n"
            f"⚠️ <i>Важно: название должно точно совпадать с тем, что используется в прогнозах!</i>\n\n"
            f"Отправьте название команды одним сообщением или нажмите ❌ для отмены."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="fav_cancel_input")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка start_manual_input: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# === Отмена ручного ввода ===
@router.callback_query(F.data == "fav_cancel_input")
async def cancel_manual_input(callback: CallbackQuery, state: FSMContext):
    """Отменить ручной ввод"""
    await state.clear()
    try:
        await db.init()
        favorites = await db.get_user_favorites(callback.from_user.id)
        
        text = f"⭐ <b>Ваши избранные команды ({len(favorites)}/{MAX_FAVORITES}):</b>\n\n"
        for team in favorites:
            text += f"✅ {team}\n"
        
        keyboard = _build_teams_keyboard(favorites)
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer("Ввод отменён")
    except Exception as e:
        logger.error(f"Ошибка cancel_manual_input: {e}")


# === Обработка введённого названия команды (FSM) ===
@router.message(StateFilter(FavoriteTeamStates.waiting_for_team_name))
async def process_team_name(message: Message, state: FSMContext):
    """Обработать введённое пользователем название команды"""
    try:
        await db.init()
        user_id = message.from_user.id
        
        # Получаем и валидируем введённое название
        team_name = message.text.strip() if message.text else ""
        
        if not team_name:
            await message.answer(
                "❌ <b>Название не может быть пустым!</b>\n\nПопробуйте ещё раз:",
                parse_mode="HTML"
            )
            return
        
        if len(team_name) < 2:
            await message.answer(
                "❌ <b>Слишком короткое название!</b>\n\nМинимум 2 символа. Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return
        
        if len(team_name) > 50:
            await message.answer(
                "❌ <b>Слишком длинное название!</b>\n\nМаксимум 50 символов. Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return
        
        # Проверяем лимит
        favorites = await db.get_user_favorites(user_id)
        if len(favorites) >= MAX_FAVORITES:
            await state.clear()
            await message.answer(
                f"⚠️ <b>Достигнут лимит {MAX_FAVORITES} команд!</b>\n\n"
                f"Удалите одну из существующих через /favorites, чтобы добавить новую.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем, нет ли уже такой команды
        if team_name in favorites:
            await state.clear()
            await message.answer(
                f"ℹ️ <b>Команда {team_name} уже в вашем списке!</b>",
                parse_mode="HTML"
            )
            return
        
        # Добавляем команду
        success = await db.add_favorite_team(user_id, team_name)
        
        if success:
            await state.clear()
            
            # Получаем обновлённый список
            new_favorites = await db.get_user_favorites(user_id)
            
            text = (
                f"✅ <b>Команда добавлена!</b>\n\n"
                f"⭐ <b>{team_name}</b> теперь в ваших избранных.\n\n"
                f"Всего команд: <b>{len(new_favorites)}/{MAX_FAVORITES}</b>\n\n"
                f"🔔 Мы пришлём вам уведомление, когда эта команда будет играть!"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="➕ Добавить ещё",
                    callback_data="fav_manual_input"
                )],
                [InlineKeyboardButton(
                    text="📋 Мой список команд",
                    callback_data="fav_done"
                )]
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            logger.info(f"✅ Пользователь {user_id} добавил вручную команду: {team_name}")
        else:
            await message.answer(
                "❌ Не удалось добавить команду. Попробуйте позже.",
                parse_mode="HTML"
            )
    
    except Exception as e:
        logger.error(f"Ошибка process_team_name: {e}")
        await state.clear()
        await message.answer(f"❌ Произошла ошибка: {e}")


# === Кнопка "Готово" ===
@router.callback_query(F.data == "fav_done")
async def favorites_done(callback: CallbackQuery, state: FSMContext):
    """Завершить выбор команд"""
    await state.clear()
    try:
        await db.init()
        favorites = await db.get_user_favorites(callback.from_user.id)
        
        if favorites:
            text = f"✅ <b>Отлично! Вы подписаны на {len(favorites)} команд:</b>\n\n"
            for team in favorites:
                text += f"⭐ {team}\n"
            text += "\n🔔 Мы пришлём вам прогноз за 1 час до их матчей!"
        else:
            text = "😔 Вы не выбрали ни одной команды.\n\nИспользуйте /favorites чтобы выбрать."
        
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка favorites_done: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
