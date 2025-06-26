import os
import logging
import re
from io import BytesIO
from telegram import Update, InputFile
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from openpyxl import Workbook

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Получаем токен из переменной окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 📦 Парсинг теста
def parse_quiz(text):
    questions = []
    blocks = re.split(r'\n{2,}', text.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue  # Слишком мало строк для валидного вопроса

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

        # Определяем тип вопроса
        if not options:
            qtype = "Fill-in-the-Blank" if correct_raw else "Open-Ended"
        elif ',' in correct_raw:
            qtype = "Checkbox"
        elif correct_raw:
            qtype = "Multiple Choice"
        else:
            qtype = "Poll"

        # Индексы правильных ответов
        correct_index = []
        for ans in re.split(r'[,\s]+', correct_raw):
            ans = ans.lower().strip()
            index_map = {'а': 1, 'б': 2, 'в': 3, 'г': 4, 'д': 5, 'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}
            if ans in index_map:
                correct_index.append(index_map[ans])
            elif ans.isdigit():
                correct_index.append(int(ans))
        correct_index = ','.join(map(str, correct_index)) if correct_index else ""

        while len(options) < 5:
            options.append("")

        questions.append([question_text, qtype] + options[:5] + [correct_index])

    return questions

# 📄 Создание Excel-файла
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

# 🤖 Обработка сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    questions = parse_quiz(text)

    if not questions:
        await update.message.reply_text(
            "❌ Не удалось распознать ни одного вопроса.\n\n"
            "Пример формата:\n\n"
            "1. Кто написал «Войну и мир»?\n"
            "а) Чехов\n"
            "б) Пушкин\n"
            "в) Толстой\n"
            "г) Достоевский\n"
            "Ответ: в"
        )
        return

    excel_file = create_excel(questions)
    await update.message.reply_document(
        document=InputFile(excel_file, filename="quiz.xlsx"),
        caption="✅ Ваш тест готов!"
    )

# ▶️ Запуск бота
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
