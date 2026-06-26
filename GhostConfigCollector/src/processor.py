import json
import urllib.parse
from pathlib import Path

# Расширенный маппинг популярных VPN-локаций для точного определения флагов
FLAG_EMOJIS = {
    'US': '🇺🇸', 'DE': '🇩🇪', 'NL': '🇳🇱', 'FI': '🇫🇮', 'GB': '🇬🇧',
    'FR': '🇫🇷', 'SG': '🇸🇬', 'JP': '🇯🇵', 'HK': '🇭🇰', 'TR': '🇹🇷',
    'PL': '🇵🇱', 'UA': '🇺🇦', 'KZ': '🇰🇿', 'RU': '🇷🇺', 'BY': '🇧🇾',
    'CA': '🇨🇦', 'CH': '🇨🇭', 'SE': '🇸🇪', 'IT': '🇮🇹', 'ES': '🇪🇸',
    'RO': '🇷🇴', 'BG': '🇧🇬', 'AT': '🇦🇹', 'AU': '🇦🇺', 'KR': '🇰🇷'
}

def clean_and_parse_config(config_str: str) -> tuple:
    """
    Разбирает строку конфигурации на уникальный крипто-ключ,
    основную часть и изначальное имя (remark).
    Нужно для удаления дубликатов по серверу/порту.
    """
    try:
        config_str = config_str.strip()
        if "#" in config_str:
            base_part, remark = config_str.split("#", 1)
            # Декодируем старое имя, чтобы прочесть страну, если она там указана
            remark = urllib.parse.unquote(remark)
        else:
            base_part, remark = config_str, "Unknown"
        
        # Выделяем уникальную часть (протокол + адрес + порт) до параметров ?
        crypto_key = base_part.split("?")[0]
        return crypto_key, base_part, remark
    except Exception:
        return None, None, None

def detect_country(remark: str) -> tuple:
    """
    Анализирует текст старого имени (remark) конфигурации,
    чтобы определить ISO-код страны и вернуть соответствующий флаг.
    """
    remark_upper = remark.upper()
    
    # 1. Проверяем текстовые упоминания кодов стран (например, "DE", "US")
    for code, emoji in FLAG_EMOJIS.items():
        # Ищем код страны как отдельное слово или маркер (например, "[US]", "US-Server")
        if code in remark_upper or emoji in remark:
            return code, emoji
            
    # 2. Дополнительные популярные текстовые маркеры городов/стран
    additional_mappings = {
        'GERMANY': ('DE', '🇩🇪'), 'FRANKFURT': ('DE', '🇩🇪'),
        'USA': ('US', '🇺🇸'), 'AMERICA': ('US', '🇺🇸'), 'NEW YORK': ('US', '🇺🇸'),
        'NETHERLANDS': ('NL', '🇳🇱'), 'AMSTERDAM': ('NL', '🇳🇱'),
        'FINLAND': ('FI', '🇫🇮'), 'HELSINKI': ('FI', '🇫🇮'),
        'RUSSIA': ('RU', '🇷🇺'), 'MOSCOW': ('RU', '🇷🇺'),
        'UNITED KINGDOM': ('GB', '🇬🇧'), 'LONDON': ('GB', '🇬🇧')
    }
    
    for keyword, (code, emoji) in additional_mappings.items():
        if keyword in remark_upper:
            return code, emoji
            
    return "UN", "🌐"  # Если страна не определена

def process_and_filter(validated_servers: list) -> tuple:
    """
    Сортирует сервера по пингу, оставляет не более 100 штук,
    переименовывает по шаблону Ghost_WhiteList и группирует по странам.
    
    :param validated_servers: Список словарей от валидатора с ключами base_part, latency, etc.
    :return: (список всех строк, словарь со списками строк по странам)
    """
    # Сортировка: самые быстрые сервера с минимальной задержкой будут первыми
    sorted_servers = sorted(validated_servers, key=lambda x: x.get("latency", 9999))
    
    # Жесткий лимит согласно ТЗ: не более 100 работающих серверов
    final_working_pool = sorted_servers[:100]
    
    final_configs_strings = []
    countries_data = {}
    
    for idx, srv in enumerate(final_working_pool, start=1):
        # Определяем страну и флаг на основе сохраненных данных или ремарки
        country_code = srv.get("country_code", "UN")
        flag = srv.get("flag", "🌐")
        
        # Формируем новое строгое имя: Ghost_WhiteList | [Флаг] [Страна] | [Индекс]
        new_remark = f"Ghost_WhiteList | {flag} {country_code} | {idx}"
        
        # Кодируем имя в URL-безопасный формат (чтобы спецсимволы | и эмодзи не ломали VPN-клиенты)
        encoded_remark = urllib.parse.quote(new_remark)
        
        # Собираем финальную ссылку конфигурации
        full_config_str = f"{srv['base_part']}#{encoded_remark}"
        final_configs_strings.append(full_config_str)
        
        # Группируем по странам для последующей записи в отдельные файлы
        if country_code not in countries_data:
            countries_data[country_code] = []
        countries_data[country_code].append(full_config_str)
        
    return final_configs_strings, countries_data

def save_output_files(final_strings: list, countries_data: dict):
    """
    Записывает результаты в final_configs.json и распределяет 
    конфигурации по файлам в папку data/filtered/
    """
    filtered_path = Path("data/filtered")
    filtered_path.mkdir(parents=True, exist_ok=True)
    
    # 1. Сохраняем главный JSON файл со всеми 100 серверами
    with open("data/final_configs.json", "w", encoding="utf-8") as f:
        json.dump(final_strings, f, ensure_ascii=False, indent=4)
        
    # 2. Сохраняем ТОП-10 самых быстрых серверов
    top10_file = filtered_path / "top10.txt"
    top10_file.write_text("\n".join(final_strings[:10]), encoding="utf-8")
    
    # 3. Сохраняем ТОП-30 лучших серверов
    top30_file = filtered_path / "top30.txt"
    top30_file.write_text("\n".join(final_strings[:30]), encoding="utf-8")
    
    # 4. Сохраняем индивидуальные файлы под каждую страну (например, US.txt, DE.txt)
    # Перед записью удаляем старые файлы стран, чтобы не оставалось неактуальных локаций
    for old_file in filtered_path.glob("*.txt"):
        if old_file.name not in ["top10.txt", "top30.txt"]:
            old_file.unlink()
            
    for country_code, configs in countries_data.items():
        country_file = filtered_path / f"{country_code}.txt"
        country_file.write_text("\n".join(configs), encoding="utf-8")
        
    print(f"💾 [Processor] Результаты успешно распределены по файлам в {filtered_path}")
