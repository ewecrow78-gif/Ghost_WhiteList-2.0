import logging
from pathlib import Path
from datetime import datetime

def setup_logger():
    """Настраивает логирование в консоль и в файл"""
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path / "collector.log", encoding="utf-8")
        ]
    )
    return logging.getLogger("GhostCollector")

def generate_readme(total_found: int, unique_count: int, working_count: int, countries_data: dict):
    """Автоматически перезаписывает README.md актуальной статистикой"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Флаги для красивой таблицы
    FLAG_EMOJIS = {
        'US': '🇺🇸', 'DE': '🇩🇪', 'NL': '🇳🇱', 'FI': '🇫🇮', 'GB': '🇬🇧',
        'FR': '🇫🇷', 'SG': '🇸🇬', 'JP': '🇯🇵', 'HK': '🇭🇰', 'TR': '🇹🇷',
        'PL': '🇵🇱', 'UA': '🇺🇦', 'KZ': '🇰🇿', 'RU': '🇷🇺', 'BY': '🇧🇾'
    }
    
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
    print("📝 [Utils] README.md успешно обновлен актуальной статистикой.")
