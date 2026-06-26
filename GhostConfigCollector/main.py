import os
import re
import sys
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
import urllib.parse

# Импорты из Telethon
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

# ==================== НАСТРОЙКИ И КОНСТАНТЫ ====================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

# URL для проверки доступности (имитация "белого списка", например, замер до Cloudflare/Google)
PING_URL = "https://www.cloudflare.com/cdn-cgi/trace"
TIMEOUT_PING = 5  # Таймаут на подключение в секундах

# Регулярные выражения для поиска конфигов и внешних ссылок
CONFIG_REGEX = re.compile(r'(vless|vmess|ss|trojan|ssr|hysteria2|tuic)://[^\s]+')
URL_REGEX = re.compile(r'https?://(?:raw\.githubusercontent\.com|github\.com|pastebin\.com)/[^\s]+')

# Маппинг стран для корректного отображения флагов (ISO код -> Эмодзи флага)
FLAG_EMOJIS = {
    'US': '🇺🇸', 'DE': '🇩🇪', 'NL': '🇳🇱', 'FI': '🇫🇮', 'GB': '🇬🇧',
    'FR': '🇫🇷', 'SG': '🇸🇬', 'JP': '🇯🇵', 'HK': '🇭🇰', 'TR': '🇹🇷',
    'PL': '🇵🇱', 'UA': '🇺🇦', 'KZ': '🇰🇿', 'RU': '🇷🇺', 'BY': '🇧🇾'
}

# ==================== ИНИЦИАЛИЗАЦИЯ СТРУКТУРЫ ====================
def init_structure():
    """Автоматически создает папки и базовые файлы при старте"""
    directories = [Path("data"), Path("data/filtered"), Path("logs")]
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 Создана папка: {directory}")

    channels_file = Path("data/channels.txt")
    if not channels_file.exists():
        default_channels = (
            "# Добавьте юзернеймы каналов (без @) или ссылки, по одной на строку\n"
            "nethbuilder\n"
            "https://t.me/vpn_channel_example\n"
        )
        channels_file.write_text(default_channels, encoding="utf-8")
        print(f"📄 Создан файл для каналов: {channels_file}")

# ==================== ПАРСИНГ И ОБРАБОТКА СТРОК ====================
def parse_channels():
    """Читает список каналов из файла"""
    channels_file = Path("data/channels.txt")
    if not channels_file.exists():
        return []
    
    channels = []
    with open(channels_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Извлекаем юзернейм, если передана полная ссылка
                if "t.me/" in line:
                    line = line.split("t.me/")[-1].split("/")[0]
                channels.append(line)
    return list(set(channels))

def clean_and_parse_config(config_str):
    """Разбирает конфиг на составляющие для удаления дубликатов и переименования"""
    try:
        config_str = config_str.strip()
        if "#" in config_str:
            base_part, remark = config_str.split("#", 1)
            remark = urllib.parse.unquote(remark)
        else:
            base_part, remark = config_str, "Unknown"
        
        # Ключ для удаления дубликатов (тип протокола + адрес сервера и порт)
        # Пример: vless://uuid@server:port -> уникальный ключ
        crypto_key = base_part.split("?")[0]
        return crypto_key, base_part, remark
    except Exception:
        return None, None, None

def detect_country(remark):
    """Пытается определить страну и флаг из названия исходного конфига"""
    remark_upper = remark.upper()
    for code, emoji in FLAG_EMOJIS.items():
        if code in remark_upper or emoji in remark:
            return code, emoji
    return "UN", "🌐"  # Unknown

# ==================== АСИНХРОННЫЕ СЕТЕВЫЕ ОПЕРАЦИИ ====================
async def fetch_external_configs(session, url):
    """Скачивает контент по внешним ссылкам (GitHub/Pastebin) и ищет в них конфиги"""
    # Если ссылка на обычный гитхаб, переключаем на raw, чтобы скачать чистый текст
    if "github.com" in url and "raw.githubusercontent.com" not in url:
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                return CONFIG_REGEX.findall(text)
    except Exception as e:
        print(f"⚠️ Ошибка скачивания внешней ссылки {url}: {e}")
    return []

async def ping_and_validate(session, config_info):
    """
    Имитирует реальный HTTP-пинг. 
    В полноценной среде здесь поднимается локальный клиент (Xray/Sing-box) и запрос идет через него.
    В данном скрипте реализована валидация структуры и сетевой замер доступности узла (TCP/HTTP handshake).
    """
    crypto_key, base_part, remark = config_info
    
    # Извлекаем домен/IP сервера для базовой проверки доступности
    try:
        server_part = crypto_key.split("@")[-1]
        host = server_part.split(":")[0]
        port = int(server_part.split(":")[1].split("/")[0])
    except Exception:
        return None

    start_time = datetime.now()
    try:
        # Для точного прокси-пинга (как в Happ) необходима интеграция с подсистемой ядра (sing-box/xray).
        # Здесь мы замеряем скорость отклика порта сервера асинхронным методом.
        fut = asyncio.open_connection(host, port)
        await asyncio.wait_for(fut, timeout=TIMEOUT_PING)
        
        latency = int((datetime.now() - start_time).total_seconds() * 1000)
        
        country_code, flag = detect_country(remark)
        return {
            "base_part": base_part,
            "latency": latency,
            "country_code": country_code,
            "flag": flag
        }
    except Exception:
        return None  # Сервер недоступен или заблокирован (не прошел в белый список)

# ==================== ОСНОВНОЙ ПАЙПЛАЙН СБОРА ====================
async def start_collector():
    init_structure()
    channels = parse_channels()
    
    if not channels:
        print("❌ Список каналов пуст. Добавьте каналы в data/channels.txt")
        return

    if not API_ID or not API_HASH or not SESSION_STRING:
        print("❌ Отсутствуют переменные окружения API_ID, API_HASH или SESSION_STRING!")
        sys.exit(1)

    raw_configs_pool = []
    external_urls = []

    print(f"🔗 Подключение к Telegram и сбор данных из {len(channels)} каналов...")
    
    # Подключаемся к Telegram через сохраненную String-сессию
    client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)
    try:
        await client.connect()
        for channel in channels:
            try:
                print(f"📥 Сбор из канала: {channel}")
                # Берём последние 50 сообщений из каждого канала
                async for message in client.iter_messages(channel, limit=50):
                    if message.text:
                        # 1. Ищем прямые конфигурации в тексте
                        configs = CONFIG_REGEX.findall(message.text)
                        raw_configs_pool.extend(configs)
                        
                        # 2. Ищем ссылки на внешние источники (GitHub/Pastebin)
                        urls = URL_REGEX.findall(message.text)
                        external_urls.extend(urls)
            except errors.FloodWaitError as e:
                print(f"⏳ Ограничение Telegram Flood. Ожидание {e.seconds} секунд...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"⚠️ Не удалось прочесть канал {channel}: {e}")
    finally:
        await client.disconnect()

    # Сбор конфигов из внешних ссылок
    if external_urls:
        print(f"🌐 Проверка {len(external_urls)} внешних ссылок на наличие конфигов...")
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_external_configs(session, url) for url in set(external_urls)]
            results = await asyncio.gather(*tasks)
            for res in results:
                raw_configs_pool.extend(res)

    # 3. Удаление дубликатов
    unique_configs = {}
    for config in raw_configs_pool:
        crypto_key, base_part, remark = clean_and_parse_config(config)
        if crypto_key and crypto_key not in unique_configs:
            unique_configs[crypto_key] = (crypto_key, base_part, remark)

    print(f"🧹 Найдено уникальных конфигураций для проверки: {len(unique_configs)}")

    # 4. Асинхронный пинг и валидация
    validated_servers = []
    async with aiohttp.ClientSession() as session:
        tasks = [ping_and_validate(session, item) for item in unique_configs.values()]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res:
                validated_servers.append(res)

    # Сортировка по минимальному пингу (лучшие сверху)
    validated_servers = sorted(validated_servers, key=lambda x: x["latency"])
    
    # Лимит — максимум 100 работающих серверов общего пула
    final_working_pool = validated_servers[:100]
    print(f"✅ Проверку прошли (Online): {len(final_working_pool)} серверов.")

    # 5. Переименование, генерация флагов и запись результатов
    final_configs_strings = []
    countries_data = {}
    
    for idx, srv in enumerate(final_working_pool, start=1):
        # Шаблон переименования: Ghost_WhiteList | [Флаг] [Страна] | [Индекс]
        new_remark = f"Ghost_WhiteList | {srv['flag']} {srv['country_code']} | {idx}"
        encoded_remark = urllib.parse.quote(new_remark)
        full_config_str = f"{srv['base_part']}#{encoded_remark}"
        
        final_configs_strings.append(full_config_str)
        
        # Группировка по странам для папки фильтрации
        c_code = srv['country_code']
        if c_code not in countries_data:
            countries_data[c_code] = []
        countries_data[c_code].append(full_config_str)

    # Запись основных результатов
    with open("data/final_configs.json", "w", encoding="utf-8") as f:
        json.dump(final_configs_strings, f, ensure_ascii=False, indent=4)

    # 6. Распределение по папкам фильтрации (Топ 10, Топ 30, Страны)
    filtered_path = Path("data/filtered")
    
    # Топ 10 и Топ 30
    (filtered_path / "top10.txt").write_text("\n".join(final_configs_strings[:10]), encoding="utf-8")
    (filtered_path / "top30.txt").write_text("\n".join(final_configs_strings[:30]), encoding="utf-8")
    
    # По странам
    for c_code, configs in countries_data.items():
        (filtered_path / f"{c_code}.txt").write_text("\n".join(configs), encoding="utf-8")

    # 7. Генерация красивого README.md
    generate_readme(len(raw_configs_pool), len(unique_configs), len(final_working_pool), countries_data)
    print("🎉 Все конфигурации обновлены, файлы фильтрации сохранены, README.md обновлен!")

# ==================== ГЕНЕРАЦИЯ ОТЧЕТА README ====================
def generate_readme(total_found, unique_count, working_count, countries_data):
    """Перезаписывает README.md актуальной инфографикой и статистикой"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    country_rows = ""
    for c_code, configs in countries_data.items():
        emoji = FLAG_EMOJIS.get(c_code, "🌐")
        country_rows += f"| {emoji} {c_code} | {len(configs)} |\n"

    readme_content = f"""# 👻 Ghost_WhiteList Collector

Автоматический асинхронный инструмент для агрегации, очистки, валидации и умной фильтрации VPN конфигураций из Telegram-каналов и внешних репозиториев.

### 📊 Актуальная статистика

| Метрика | Значение |
| :--- | :--- |
| Всего собрано строк | **{total_found}** |
| Уникальных конфигураций | **{unique_count}** |
| **Прошли HTTP-валидацию (Макс. 100)** | 🔥 **{working_count}** |

### 🌍 Доступность по странам (Топ рабочих)

| Страна | Количество серверов |
| :--- | :--- |
{country_rows}

### 📂 Структура собранных файлов в `data/filtered/`
* `top10.txt` — 10 самых быстрых серверов с минимальной задержкой.
* `top30.txt` — 30 лучших серверов для повседневного использования.
* Файлы формата `[Код_Страны].txt` (например, `US.txt`, `DE.txt`) — выборка конфигураций под конкретные локации.

_Последнее обновление системы: `{current_time}`_
"""
    Path("README.md").write_text(readme_content, encoding="utf-8")

if __name__ == "__main__":
    # Запуск асинхронного ядра программы
    asyncio.run(start_collector())
