FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем всё
COPY . .

# Копируем данные в backup (чтобы потом скопировать в volume)
RUN cp -r /app/data /app/data_backup 2>/dev/null || true

# Создаем пользователя
RUN useradd -m -u 1000 appuser
RUN chown -R appuser:appuser /app

USER appuser

# Используем entrypoint
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
