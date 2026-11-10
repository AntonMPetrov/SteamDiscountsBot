import os
import asyncio
import logging
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("tg_token")

logging.basicConfig(level=logging.INFO)

STEAM_API = "https://store.steampowered.com/api/featuredcategories/"

DEFAULT_DISCOUNT = 50


def get_deals(min_discount: int = DEFAULT_DISCOUNT):
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
        if discount < min_discount:
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
        "/deals — лучшие скидки от 50%.\n"
        "/deals 20 — скидки от 20%. \n"
        "/find 'Название игры' - поиск игр по названию."
    )


async def deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Разбор аргумента
    min_discount = DEFAULT_DISCOUNT

    if context.args:
        try:
            min_discount = int(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "Аргумент должен быть целым числом, например: /deals 20"
            )
            return

        if not (1 <= min_discount <= 100):
            await update.message.reply_text(
                "Скидка должна быть в диапазоне от 1 до 100."
            )
            return

    await update.message.reply_text(f"Ищу скидки от {min_discount}%...")

    try:
        games = await asyncio.to_thread(get_deals, min_discount)

        if not games:
            await update.message.reply_text(
                f"Пока не нашёл подходящих скидок от {min_discount}%."
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


STEAM_SEARCH_API = "https://store.steampowered.com/api/storesearch/"


def search_games(query: str, limit: int = 5):
    """Ищет игры в Steam по названию."""
    try:
        response = requests.get(
            STEAM_SEARCH_API,
            params={
                "term": query,
                "cc": "ru",  # Регион для цен
                "l": "russian",  # Язык
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        games = []
        for item in data.get("items", [])[:limit]:
            # Пропускаем всё, что не является игрой (DLC, софт и т.д.)
            if item.get("type") != "app":
                continue

            # Извлекаем цену, если она есть
            price_info = item.get("price")
            if price_info:
                final_price = price_info.get("final", 0) / 100
                currency = price_info.get("currency", "")
                price_str = f"{final_price:.2f} {currency}"
            else:
                price_str = "Цена не указана"

            games.append({
                "name": item.get("name", "Без названия"),
                "id": item.get("id"),
                "price": price_str,
                "url": f"https://store.steampowered.com/app/{item.get('id')}/",
            })
        return games

    except Exception:
        logging.exception(f"Ошибка поиска Steam по запросу: {query}")
        return []


async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Проверяем, есть ли аргументы
    if not context.args:
        await update.message.reply_text(
            "Пожалуйста, укажите название игры после команды.\n"
            "Например: /find The Witcher"
        )
        return

    # 2. Собираем название из списка слов
    query = " ".join(context.args)
    await update.message.reply_text(f"Ищу игру: «{query}»...")

    # 3. Ищем в отдельном потоке, чтобы не блокировать бота
    try:
        games = await asyncio.to_thread(search_games, query)

        if not games:
            await update.message.reply_text(
                f"По запросу «{query}» ничего не найдено."
            )
            return

        # 4. Формируем ответ в стиле команды /deals
        parts = []
        for game in games:
            parts.append(
                f"🎮 {game['name']}\n"
                f"💰 Цена: {game['price']}\n"
                f"🔗 {game['url']}"
            )

        await update.message.reply_text("\n\n".join(parts))

    except Exception:
        logging.exception("Ошибка в команде /find")
        await update.message.reply_text(
            "Не удалось выполнить поиск. Попробуй позже."
        )


def main():
    if not TOKEN:
        raise RuntimeError(
            "Не задана переменная окружения tg_token."
        )

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("deals", deals))
    app.add_handler(CommandHandler("find", find))


    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()