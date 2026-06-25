"""
Обработчики для любимых команд пользователей
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database.db import Database
import logging

logger = logging.getLogger(__name__)

router = Router()
db = Database()

# Популярные команды для быстрого выбора
POPULAR_TEAMS = [
    "Manchester United", "Manchester City", "Liverpool", "Chelsea", "Arsenal", "Tottenham",
    "Real Madrid", "Barcelona", "Atletico Madrid", "Bayern Munich", "Borussia Dortmund",
    "PSG", "Juventus", "AC Milan", "Inter Milan", "Napoli",
    "Zenit", "Spartak Moscow", "CSKA Moscow", "Lokomotiv Moscow"
]


@router.message(Command("favorites"))
async def cmd_favorites(message: Message):
    """Показать избранные команды"""
    await db.init()
    favorites = await db.get_user_favorites(message.from_user.id)
    
    if not favorites:
        text = "⭐ <b>У вас пока нет избранных команд</b>\n\n"
        text += "Выберите команды, за которыми хотите следить:"
    else:
        text = f"⭐ <b>Ваши избранные команды ({len(favorites)}):</b>\n\n"
        for team in favorites:
            text += f"✅ {team}\n"
        text += "\n👇 Добавьте ещё или удалите:"
    
    keyboard = _build_teams_keyboard(favorites)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


def _build_teams_keyboard(user_favorites: list) -> InlineKeyboardMarkup:
    """Строит клавиатуру с командами"""
    buttons = []
    row = []
    
    for i, team in enumerate(POPULAR_TEAMS):
        is_favorite = team in user_favorites
        emoji = "⭐" if is_favorite else "➕"
        callback = f"fav_toggle:{team}"
        
        row.append(InlineKeyboardButton(
            text=f"{emoji} {team}",
            callback_data=callback
        ))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
    
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(
        text="✅ Готово",
        callback_data="fav_done"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("fav_toggle:"))
async def toggle_favorite(callback: CallbackQuery):
    """Добавить/удалить команду из избранного"""
    await db.init()
    team = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    favorites = await db.get_user_favorites(user_id)
    
    if team in favorites:
        await db.remove_favorite_team(user_id, team)
        await callback.answer(f"❌ {team} удалена из избранного")
    else:
        if len(favorites) >= 5:
            await callback.answer("⚠️ Максимум 5 команд!", show_alert=True)
            return
        await db.add_favorite_team(user_id, team)
        await callback.answer(f"⭐ {team} добавлена в избранное")
    
    # Обновляем клавиатуру
    new_favorites = await db.get_user_favorites(user_id)
    keyboard = _build_teams_keyboard(new_favorites)
    
    text = f"⭐ <b>Ваши избранные команды ({len(new_favorites)}):</b>\n\n"
    for t in new_favorites:
        text += f"✅ {t}\n"
    text += "\n👇 Выберите ещё:"
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "fav_done")
async def favorites_done(callback: CallbackQuery):
    """Завершить выбор команд"""
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
