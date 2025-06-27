import os
import logging
import asyncio
from telegram import Update, InputFile
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from openpyxl import Workbook
import re
from io import BytesIO

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
APP_URL = os.environ.get("APP_URL")  # Пример: https://quiz-excel-bot.onrender.com

def parse_quiz(text):
    questions = []
    blocks = re.split(r'\n{2,}', text.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue

        question_text = lines[0].strip()
        options = []
        correct_raw = ""

        for line in lines[1:]:
            if re.match(r'^(ответ|answer|правильный ответ)[:\-]?', line.strip().lower()):
                correct_raw = line.split(':', 1)[-1].strip()
            elif re.match(r'^[aаbбвcгdеe]\)', line.strip().lower()):
                options.append(re.sub(r'^[aаbбвcгdеe]\)\s*', '', line.strip(), flags=re.I))
            else:
                options.append(line.strip())

        if not options:
            qtype = "Fill-in-the-Blank" if correct_raw else "Open-Ended"
        elif ',' in correct_raw:
            qtype = "Checkbox"
        elif correct_raw:
            qtype = "Multiple Choice"
        else:
            qtype = "Poll"

        correct_index = []
        for ans in re.split(r'[,\s]+', correct_raw):
            ans = ans.lower().strip()
            index = {'а': 1, 'б': 2, 'в': 3, 'г': 4, 'д': 5, 'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
            if ans in index:
                correct_index.append(index[ans])
            elif ans.isdigit():
                correct_index.append(int(ans))
        correct_index = ','.join(map(str, correct_index)) if correct_index else ""

        while len(options) < 5:
            options.append("")

        questions.append([question_text, qtype] + options[:5] + [correct_index])
    return questions

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    questions = parse_quiz(text)
    if not questions:
        await update.message.reply_text(
            "❗ Неверный формат. Пример:\n\n"
            "1. Кто написал «Войну и мир»?\n"
            "а) Чехов\nб) Пушкин\nв) Толстой\nОтвет: в"
        )
        return

    excel_file = create_excel(questions)
    await update.message.reply_document(
        document=InputFile(excel_file, filename="quiz.xlsx"),
        caption="✅ Ваш тест готов!"
    )

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    webhook_url = f"{APP_URL}/webhook"
    await app.bot.set_webhook(webhook_url)

    logging.info(f"Webhook установлен: {webhook_url}")

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        webhook_url=webhook_url
    )

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())

