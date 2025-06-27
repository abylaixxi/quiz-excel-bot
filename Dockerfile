FROM python:3.11-slim

# Устанавливаем необходимые системные библиотеки
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем проект
COPY . .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем порт для Render (очень важно!)
EXPOSE 10000

# Запускаем скрипт
CMD ["python", "main.py"]
