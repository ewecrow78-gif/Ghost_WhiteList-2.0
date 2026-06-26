import re
import asyncio
import aiohttp

# Регулярное выражение для поиска VPN конфигураций основных протоколов
CONFIG_REGEX = re.compile(r'(vless|vmess|ss|trojan|ssr|hysteria2|tuic)://[^\s]+')

# Регулярное выражение для поиска ссылок на GitHub и Pastebin
URL_REGEX = re.compile(r'https?://(?:raw\.githubusercontent\.com|github\.com|pastebin\.com)/[^\s]+')

def normalize_url(url: str) -> str:
    """
    Приводит обычные ссылки GitHub к формату raw, чтобы скачивать чистый текст,
    а также очищает ссылку от лишних знаков препинания на конце.
    """
    # Очистка от возможных артефактов парсинга на конце строки (точки, скобки)
    url = url.rstrip(').,;"\'')
    
    if "github.com" in url and "raw.githubusercontent.com" not in url:
        # Превращаем https://github.com/user/repo/blob/main/file.txt
        # в https://raw.githubusercontent.com/user/repo/main/file.txt
        url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url

async def fetch_configs_from_url(session: aiohttp.ClientSession, url: str) -> list:
    """Асинхронно скачивает страницу по ссылке и ищет в ней VPN конфигурации"""
    target_url = normalize_url(url)
    try:
        async with session.get(target_url, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                found_configs = CONFIG_REGEX.findall(text)
                if found_configs:
                    # Возвращаем полные строки совпадений
                    return [match.group(0) if isinstance(match, re.Match) else text[text.find(match):].split()[0] 
                            for match in CONFIG_REGEX.finditer(text)]
            else:
                print(f"⚠️ [Parser] Ссылка вернула статус {response.status}: {target_url}")
    except Exception as e:
        print(f"⚠️ [Parser] Ошибка при скачивании внешней ссылки {target_url}: {e}")
    return []

async def parse_all_contents(raw_texts: list) -> list:
    """
    Главная функция модуля. Извлекает конфиги из текстов ТГ и внешних ссылок.
    
    :param raw_texts: Список текстов постов из Telegram
    :return: Общий пул сырых конфигураций
    """
    combined_configs = []
    external_urls = set()

    print("🔍 Начинаю анализ текстов и поиск конфигураций...")

    # 1. Сбор прямых конфигов и поиск внешних ссылок в текстах
    for text in raw_texts:
        # Ищем конфиги прямо в тексте поста
        direct_configs = [m.group(0) for m in CONFIG_REGEX.finditer(text)]
        combined_configs.extend(direct_configs)
        
        # Ищем ссылки на внешние источники
        urls = URL_REGEX.findall(text)
        for url in urls:
            external_urls.add(url)

    print(f"📈 Найдено прямых конфигов в постах: {len(combined_configs)}")
    print(f"🔗 Обнаружено уникальных внешних ссылок для проверки: {len(external_urls)}")

    # 2. Асинхронный обход внешних ссылок (если они есть)
    if external_urls:
        async with aiohttp.ClientSession() as session:
            # Создаем массив задач для одновременного скачивания
            tasks = [fetch_configs_from_url(session, url) for url in external_urls]
            results = await asyncio.gather(*tasks)
            
            # Собираем результаты
            for res in results:
                combined_configs.extend(res)

    print(f"📊 Всего конфигураций собрано после парсинга: {len(combined_configs)}")
    return combined_configs
