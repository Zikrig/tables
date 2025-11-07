FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем код приложения
COPY app ./app
COPY bot.py ./
COPY examples ./examples

# Создаем директории для файлов
RUN mkdir -p uploads outputs

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Запускаем бота
CMD ["python", "bot.py"]

