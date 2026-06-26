import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Импортируем функции из созданных модулей в папке src
from src.collector import fetch_from_channels
from src.parser import parse_all_contents
from src.processor import clean_and_parse_config, process_and_filter, save_output_files
from src.validator import validate_all_servers
from src.utils import setup_logger, generate_readme

# Загружаем переменные из .env (актуально для локального запуска)
load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

def parse_channels():
    """Читает список целевых каналов из data/channels.txt"""
    channels_file = Path("data/channels.txt")
    if not channels_file.exists():
        return []
    
    channels = []
    with open(channels_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "t.me/" in line:
                    line = line.split("t.me/")[-1].split("/")[0]
                channels.append(line)
    return list(set(channels))

async def main():
    # 1. Включаем логгер (из utils.py)
    logger = setup_logger()
    logger.info("🚀 Запуск Ghost_WhiteList конвейера...")

    # 2. Парсим список каналов
    channels = parse_channels()
    if not channels:
        logger.error("❌ Список каналов пуст! Заполните файл data/channels.txt")
        return

    # 3. Шаг Сбора: Получаем тексты постов из Telegram (collector.py)
    raw_texts = await fetch_from_channels(channels, API_ID, API_HASH, SESSION_STRING)
    if not raw_texts:
        logger.warning("⚠️ Не удалось собрать сообщения из Telegram.")
        return

    # 4. Шаг Парсинга: Извлекаем конфиги и качаем данные из внешних ссылок (parser.py)
    raw_configs = await parse_all_contents(raw_texts)
    if not raw_configs:
        logger.warning("⚠️ Конфигурации в собранных текстах не обнаружены.")
        return

    # 5. Очистка: Удаляем дубликаты по уникальному ключу (сервер/порт) перед пингом
    unique_configs = {}
    for config in raw_configs:
        crypto_key, base_part, remark = clean_and_parse_config(config)
        if crypto_key and crypto_key not in unique_configs:
            unique_configs[crypto_key] = (crypto_key, base_part, remark)

    logger.info(f"🧹 Фильтрация дубликатов завершена. Уникальных для проверки: {len(unique_configs)}")

    # 6. Шаг Валидации: Асинхронно пингуем порты серверов (validator.py)
    validated_servers = await validate_all_servers(unique_configs)

    # 7. Шаг Обработки: Сортируем по пингу, берем топ-100 и переименовываем (processor.py)
    final_strings, countries_data = process_and_filter(validated_servers)

    # 8. Сохранение: Записываем всё в json и распределяем по папкам фильтрации (processor.py)
    save_output_files(final_strings, countries_data)

    # 9. Отчетность: Генерируем красивую инфографику в README.md (utils.py)
    generate_readme(len(raw_configs), len(unique_configs), len(final_strings), countries_data)
    
    logger.info("🎉 Набор конфигураций Ghost_WhiteList успешно обновлен!")

if __name__ == "__main__":
    # Запуск асинхронного движка программы
    asyncio.run(main())
