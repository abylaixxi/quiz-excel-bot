import os
import logging
import asyncio
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, MessageHandler, CommandHandler,
    ContextTypes, filters
)
from openpyxl import Workbook
from io import BytesIO
import re
import nest_asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ======================
#   ПАРСЕР ТЕСТОВ
# ======================

def parse_quiz(text):
    questions = []
    blocks = re.split(r'\n{2,}', text.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue

        question_text = lines[0].strip()
        options = []
        correct_raw = ""

        for line in lines[1:]:
            l = line.strip()
            # поиск строки правильного ответа
            if re.match(r'^(ответ|правильный ответ|answer)[:\-]?', l.lower()):
                correct_raw = l.split(':', 1)[-1].strip()
                continue

            # Опции A), B), C)...
            if re.match(r'^[aаbбвcгdдеe]\)', l.lower()):
                options.append(re.sub(r'^[aаbбвcгdдеe]\)\s*', '', l, flags=re.I))
                continue

            # если просто текст — добавляем как опцию (редкий случай)
            options.append(l)

        if not question_text:
            continue

        # Определение типа вопроса
        if not options and not correct_raw:
            continue

        if not options:
            qtype = "Open-Ended" if not correct_raw else "Fill-in-the-Blank"
        elif ',' in correct_raw:
            qtype = "Checkbox"
        elif correct_raw:
            qtype = "Multiple Choice"
        else:
            qtype = "Poll"

        # Индексы правильных ответов
        correct_index = []
        index_map = {'а': 1, 'б': 2, 'в': 3, 'г': 4, 'д': 5,
                     'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}

        for ans in re.split(r'[,\s]+', correct_raw):
            ans = ans.lower().strip()
            if ans in index_map:
                correct_index.append(index_map[ans])
            elif ans.isdigit():
                correct_index.append(int(ans))

        correct_index = ",".join(map(str, correct_index)) if correct_index else ""

        # Опций должно быть ровно 5
        while len(options) < 5:
            options.append("")

        questions.append([question_text, qtype] + options[:5] + [correct_index])

    return questions


# ======================
#   СОЗДАНИЕ ФАЙЛА EXCEL
# ======================

def create_excel(questions):
    wb = Workbook()
    ws = wb.active
    ws.append([
        "Question Text", "Question Type", "Option 1", "Option 2", "Option 3",
        "Option 4", "Option 5", "Correct Answer"
    ])

    for q in questions:
        ws.append(q)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ======================
#   КОМАНДЫ БОТА
# ======================

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quiz_buffer"] = ""
    await update.message.reply_text(
        "📝 Режим загрузки теста активирован!\n"
        "Отправляйте вопросы частями.\n"
        "Когда закончите — напишите: /done\n\n"
        "Чтобы очистить буфер: /reset"
    )


async def reset_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quiz_buffer"] = ""
    await update.message.reply_text("♻️ Буфер очищен.")


async def finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_text = context.user_data.get("quiz_buffer", "")

    if not full_text.strip():
        await update.message.reply_text("❌ Нет данных. Используйте /startquiz для начала.")
        return

    questions = parse_quiz(full_text)
    logger.info(f"Распознано вопросов: {len(questions)}")

    if not questions:
        await update.message.reply_text("❌ Не удалось распознать ни одного вопроса.")
        return

    excel_file = create_excel(questions)

    await update.message.reply_document(
        document=InputFile(excel_file, filename="quiz.xlsx"),
        caption="✅ Все вопросы обработаны одним файлом!"
    )

    context.user_data["quiz_buffer"] = ""


async def collect_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тихое накопление сообщений без ответов,
    чтобы Telegram не спамил и не делил длинные тексты.
    """
    if "quiz_buffer" not in context.user_data:
        return await update.message.reply_text(
            "❗ Перед отправкой теста введите команду /startquiz"
        )

    chunk = update.message.text.strip()

    # добавляем аккуратно
    existing = context.user_data.get("quiz_buffer", "")
    context.user_data["quiz_buffer"] = existing + "\n" + chunk


# ======================
#   ОСНОВНОЙ ЗАПУСК
# ======================

async def main():
    if not BOT_TOKEN or not WEBHOOK_URL:
        raise ValueError("BOT_TOKEN и WEBHOOK_URL должны быть заданы")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("startquiz", start_quiz))
    app.add_handler(CommandHandler("done", finish_quiz))
    app.add_handler(CommandHandler("reset", reset_quiz))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_text))

    logger.info(f"Устанавливаем webhook: {WEBHOOK_URL}")
    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook установлен!")

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
    )


if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
