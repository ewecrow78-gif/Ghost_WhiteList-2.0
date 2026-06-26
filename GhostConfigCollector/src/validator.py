
import asyncio
from datetime import datetime

TIMEOUT_PING = 5  # Максимальное время ожидания ответа от сервера (в секундах)

async def ping_server(config_info: tuple) -> dict:
    """
    Замеряет скорость отклика порта сервера асинхронным методом.
    
    :param config_info: Кортеж (crypto_key, base_part, remark) из процессора
    :return: Словарь с данными сервера или None, если сервер лежит
    """
    crypto_key, base_part, remark = config_info
    
    # Импортируем функцию определения страны локально, чтобы избежать циклического импорта
    from src.processor import detect_country
    
    try:
        # Извлекаем хост и порт из уникального ключа (например, vless://uuid@host:port)
        server_part = crypto_key.split("@")[-1]
        host = server_part.split(":")[0]
        port = int(server_part.split(":")[1].split("/")[0])
    except Exception:
        return None

    start_time = datetime.now()
    try:
        # Пытаемся асинхронно открыть сетевое соединение с хостом и портом
        connection = asyncio.open_connection(host, port)
        await asyncio.wait_for(connection, timeout=TIMEOUT_PING)
        
        # Считаем задержку в миллисекундах (ms)
        latency = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Определяем страну для этого сервера
        country_code, flag = detect_country(remark)
        
        return {
            "base_part": base_part,
            "latency": latency,
            "country_code": country_code,
            "flag": flag
        }
    except Exception:
        # Если сервер упал по таймауту или порт закрыт — он не проходит проверку
        return None

async def validate_all_servers(unique_configs: dict) -> list:
    """Запускает параллельное тестирование всех уникальных прокси"""
    print(f"⚡ [Validator] Начинаю асинхронный пинг {len(unique_configs)} серверов...")
    
    # Создаем пул задач для одновременного выполнения
    tasks = [ping_server(item) for item in unique_configs.values()]
    results = await asyncio.gather(*tasks)
    
    # Фильтруем и оставляем только те сервера, которые вернули успешный результат
    valid_servers = [res for res in results if res is not None]
    print(f"📉 [Validator] Пинг завершен. Живых серверов: {len(valid_servers)}")
    return valid_servers
