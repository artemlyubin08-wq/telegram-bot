import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import *
import os

TOKEN = os.getenv("8173534065:AAHjIm0A0L7GtoiIyk7qV-JgF46Uzlwb0xo")
bot = Bot(TOKEN)

dp = Dispatcher()

state = {}


# ---------------- MENU ----------------
def menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🔁 Оценивать")],
            [KeyboardButton(text="🏆 Топ")]
        ],
        resize_keyboard=True
    )


# ---------------- START ----------------
@dp.message(F.text == "/start")
async def start(message: Message):

    await add_user(message.from_user.id, message.from_user.username or "user")

    if not await user_has_profile(message.from_user.id):
        state[message.from_user.id] = "bio"
        await message.answer("📝 Напиши о себе:")
        return

    await message.answer("Меню:", reply_markup=menu())


# ---------------- PROFILE ----------------
@dp.message()
async def flow(message: Message):

    st = state.get(message.from_user.id)

    if st == "bio":
        await set_bio(message.from_user.id, message.text)
        state[message.from_user.id] = "photo"
        await message.answer("📸 Отправь фото")
        return

    if st == "photo" and message.photo:
        await set_photo(message.from_user.id, message.photo[-1].file_id)
        state.pop(message.from_user.id, None)
        await message.answer("✅ Профиль создан!", reply_markup=menu())
        return


    # CHAT MODE
    if st == "chat":
        partner = await get_partner(message.from_user.id)

        if not partner:
            return

        partner_state = state.get(partner)
        is_online = partner_state == "chat"

        if not is_online:
            count = await get_pending_count(message.from_user.id, partner)

            if count >= 3:
                await exit_chat(message.from_user.id)
                await message.answer("🚪 Чат закрыт: нет ответа")
                return

            await inc_pending_messages(message.from_user.id, partner)

        if message.photo:
            await bot.send_photo(partner, message.photo[-1].file_id)
        else:
            await bot.send_message(partner, message.text)

        return


    # MENU
    if message.text == "👤 Профиль":
        rating, votes, bio = await get_user_stats(message.from_user.id)
        return await message.answer(f"👤 Профиль\n\n📝 {bio}\n⭐ {rating:.2f}\n🗳 {votes}")

    if message.text == "🏆 Топ":

        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("""
                SELECT username, rating
                FROM users
                ORDER BY rating DESC
                LIMIT 10
            """)
            rows = await cur.fetchall()

        text = "🏆 Топ:\n\n"

        if not rows:
            return await message.answer("Топ пуст")

        for i, r in enumerate(rows, 1):
            text += f"{i}. @{r[0]} — ⭐ {round(r[1],2)}\n"

        await message.answer(text)

    if message.text == "🔁 Оценивать":

        target = await get_random_user(message.from_user.id)

        if not target:
            return await message.answer("Нет пользователей")

        username, photo, bio = await get_full_user(target)

        kb = InlineKeyboardBuilder()

        for i in range(1, 11):
            kb.button(text=str(i), callback_data=f"rate:{target}:{i}")

        kb.adjust(5)

        caption = f"👤 Оцени человека\n\n📝 {bio}"

        if photo:
            await bot.send_photo(message.chat.id, photo, caption=caption, reply_markup=kb.as_markup())
        else:
            await message.answer(caption, reply_markup=kb.as_markup())


# ---------------- RATE ----------------
@dp.callback_query(F.data.startswith("rate:"))
async def rate(call: CallbackQuery):

    _, to_id, score = call.data.split(":")
    from_id = call.from_user.id

    to_id = int(to_id)
    score = int(score)

    await save_rating(from_id, to_id, score)
    await update_rating(to_id, score)

    await call.answer("Оценено")

    await save_incoming_rating(to_id, from_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⭐ Оценить в ответ", callback_data="rate_back")
    kb.adjust(1)

    try:
        await bot.send_message(
            to_id,
            "🔔 Вас оценили!",
            reply_markup=kb.as_markup()
        )
    except:
        pass

    other = await get_rating(to_id, from_id)

    if other >= 6 and score >= 6:

        await set_chat(from_id, to_id)

        kb = InlineKeyboardBuilder()
        kb.button(text="💬 Чат", callback_data="chat_open")
        kb.button(text="🚪 Выйти", callback_data="chat_exit")
        kb.adjust(1)

        await bot.send_message(from_id, "🔥 ВЗАИМНЫЙ МАТЧ!", reply_markup=kb.as_markup())
        await bot.send_message(to_id, "🔥 ВЗАИМНЫЙ МАТЧ!", reply_markup=kb.as_markup())


# ---------------- RATE BACK ----------------
@dp.callback_query(F.data == "rate_back")
async def rate_back(call: CallbackQuery):

    target = await get_last_rater(call.from_user.id)

    if not target:
        return await call.message.answer("Нет данных")

    username, photo, bio = await get_full_user(target)

    kb = InlineKeyboardBuilder()

    for i in range(1, 11):
        kb.button(text=str(i), callback_data=f"rate:{target}:{i}")

    kb.adjust(5)

    caption = f"👤 Оцени ответ\n\n📝 {bio}"

    if photo:
        await bot.send_photo(call.message.chat.id, photo, caption=caption, reply_markup=kb.as_markup())
    else:
        await call.message.answer(caption, reply_markup=kb.as_markup())

    await call.answer()


# ---------------- CHAT ----------------
@dp.callback_query(F.data == "chat_open")
async def open_chat(call: CallbackQuery):
    state[call.from_user.id] = "chat"

    partner = await get_partner(call.from_user.id)

    if partner:
        await clear_pending(call.from_user.id, partner)
        await clear_pending(partner, call.from_user.id)

    await call.message.answer("💬 чат открыт")
    await call.answer()


@dp.callback_query(F.data == "chat_exit")
async def exit_chat_handler(call: CallbackQuery):
    state.pop(call.from_user.id, None)
    await exit_chat(call.from_user.id)
    await call.message.answer("🚪 вышли из чата")
    await call.answer()


# ---------------- RUN ----------------
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())