import os
import logging
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openpyxl import Workbook
import re
from io import BytesIO

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN")


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
            if re.match(r'^(ответ|правильный ответ|answer)[:\-]?', line.strip().lower()):
                correct_raw = line.split(':', 1)[-1].strip()
            elif re.match(r'^[aа]\)|[бb]\)|[вc]\)|[гd]\)|[еe]\)', line.strip().lower()):
                options.append(re.sub(r'^[aаbбвcгdеe]\)\s*', '', line.strip(), flags=re.I))
            else:
                options.append(line.strip())

        if not options:
            if correct_raw:
                qtype = "Fill-in-the-Blank"
            else:
                qtype = "Open-Ended"
        elif ',' in correct_raw:
            qtype = "Checkbox"
        elif correct_raw:
            qtype = "Multiple Choice"
        else:
            qtype = "Poll"

        correct_index = []
        for ans in re.split(r'[,\s]+', correct_raw):
            ans = ans.lower().strip()
            index = {'а':1, 'б':2, 'в':3, 'г':4, 'д':5, 'a':1, 'b':2, 'c':3, 'd':4, 'e':5}
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
    excel_file = create_excel(questions)
    await update.message.reply_document(
        document=InputFile(excel_file, filename="quiz.xlsx"),
        caption="Готово ✅"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
