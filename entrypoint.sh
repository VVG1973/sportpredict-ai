#!/bin/bash
# Копируем данные из backup в /data (где Railway volume)
if [ -d "/app/data_backup" ]; then
    cp -r /app/data_backup/* /data/ 2>/dev/null || true
    echo "✅ Данные скопированы в /data"
fi

# Запускаем main.py
exec python main.py
