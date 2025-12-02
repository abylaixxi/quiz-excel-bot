import os
import logging
import asyncio
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from openpyxl import Workbook
from io import BytesIO
import re
import nest_asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------------- ПАРСЕР (НОВЫЙ, ИСПРАВЛЕННЫЙ) --------------------

def parse_quiz(text):
    questions = []
    raw_lines = [line.strip() for line in text.split("\n") if line.strip()]

    current_question = []
    for line in raw_lines:
        # Если новая строка начинается с номера — это новый вопрос
        if re.match(r"^\d+[\).]", line) and current_question:
            questions.append(current_question)
            current_question = [line]
        else:
            current_question.append(line)

    if current_question:
        questions.append(current_question)

    parsed = []
    for block in questions:
        q_text = block[0]
        options = []
        correct_raw = ""

        for line in block[1:]:
            # Определяем "Ответ:"
            if re.match(r'^(ответ|правильный ответ|answer)[:\-]?', line.lower()):
                correct_raw = line.split(':', 1)[-1].strip()
                continue

            # Определяем варианты
            if re.match(r'^[aаbбвcгdеe]\)', line.lower()):
                options.append(re.sub(r'^[aаbбвcгdеe]\)\s*', '', line, flags=re.I))
            else:
                options.append(line)

        # Тип вопроса
        if not options:
            qtype = "Open-Ended" if not correct_raw else "Fill-in-the-Blank"
        elif ',' in correct_raw:
            qtype = "Checkbox"
        elif correct_raw:
            qtype = "Multiple Choice"
        else:
            qtype = "Poll"

        # Индексация правильных ответов
        index_map = {
            'а': 1, 'б': 2, 'в': 3, 'г': 4, 'д': 5,
            'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5
        }

        correct_index = []
        for ans in re.split(r'[,\s]+', correct_raw):
            ans = ans.lower().strip()
            if ans in index_map:
                correct_index.append(index_map[ans])
            elif ans.isdigit():
                correct_index.append(int(ans))

        correct_index = ",".join(map(str, correct_index)) if correct_index else ""

        # Всегда дополняем до 5 вариантов
        while len(options) < 5:
            options.append("")

        parsed.append([q_text, qtype] + options[:5] + [correct_index])

    return parsed


# -------------------- СОЗДАНИЕ EXCEL --------------------

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


# -------------------- ОБРАБОТЧИКИ --------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"Получен текст:\n{text}")

    questions = parse_quiz(text)
    logger.info(f"Распознано вопросов: {len(questions)}")

    if not questions:
        await update.message.reply_text(
            "❌ Не удалось распознать вопросы.\n\n"
            "Отправьте текст в формате:\n"
            "1. Вопрос\nа) вариант\nб) вариант\nОтвет: а"
        )
        return

    excel_file = create_excel(questions)
    await update.message.reply_document(
        document=InputFile(excel_file, filename="quiz.xlsx"),
        caption=f"✅ Ваш тест готов! Всего вопросов: {len(questions)}"
    )


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Использование: /preview текст_теста")
        return

    text = " ".join(context.args)
    questions = parse_quiz(text)

    if not questions:
        await update.message.reply_text("❌ Не удалось распознать вопросы.")
        return

    preview_lines = [f"✅ Распознано вопросов: {len(questions)}\n"]
    for i, q in enumerate(questions[:5], start=1):
        preview_lines.append(f"{i}. {q[0]}")
    if len(questions) > 5:
        preview_lines.append("...")

    await update.message.reply_text("\n".join(preview_lines))


# -------------------- ЗАПУСК БОТА --------------------

async def main():
    if not BOT_TOKEN or not WEBHOOK_URL:
        raise ValueError("BOT_TOKEN и WEBHOOK_URL должны быть установлены!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info(f"Пытаемся установить webhook: {WEBHOOK_URL}")
    await app.bot.set_webhook(WEBHOOK_URL)
    logger.info("Webhook успешно установлен.")

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=WEBHOOK_URL,
    )


if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
