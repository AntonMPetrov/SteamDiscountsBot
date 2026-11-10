import os
import asyncio
import logging
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("tg_token")

logging.basicConfig(level=logging.INFO)

STEAM_API = "https://store.steampowered.com/api/featuredcategories/"


def get_deals():
    response = requests.get(
        STEAM_API,
        params={"cc": "ru", "l": "russian"},
        timeout=20,
    )
    response.raise_for_status()

    data = response.json()
    specials = data.get("specials", {}).get("items", [])

    deals = []
    for game in specials:
        discount = game.get("discount_percent", 0)
        if discount < 50:
            continue

        price = game.get("final_price", 0) / 100
        original = game.get("original_price", 0) / 100
        if price <= 0 or original <= 0:
            continue

        deals.append({
            "name": game.get("name", "Без названия"),
            "discount": discount,
            "price": price,
            "original": original,
            "url": f"https://store.steampowered.com/app/{game['id']}/",
        })

    deals.sort(key=lambda x: x["discount"], reverse=True)
    return deals[:10]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот скидок Steam.\n\n"
        "/deals — найти лучшие скидки."
    )


async def deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ищу скидки Steam...")

    try:
        games = await asyncio.to_thread(get_deals)

        if not games:
            await update.message.reply_text(
                "Пока не нашёл подходящих скидок от 50%."
            )
            return

        parts = []
        for game in games:
            parts.append(
                f"🎮 {game['name']}\n"
                f"🔥 Скидка: -{game['discount']}%\n"
                f"💰 Цена: {game['price']:.2f} ₽\n"
                f"Обычная цена: {game['original']:.2f} ₽\n"
                f"🔗 {game['url']}"
            )

        await update.message.reply_text("\n\n".join(parts))

    except Exception:
        logging.exception("Ошибка поиска скидок")
        await update.message.reply_text(
            "Не удалось получить скидки. Попробуй позже."
        )


def main():
    if not TOKEN:
        raise RuntimeError(
            "Не задана переменная окружения tg_token. "
            "Установите её перед запуском."
        )

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("deals", deals))

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()