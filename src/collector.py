import asyncio
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

async def fetch_from_channels(channels: list, api_id: str, api_hash: str, session_string: str, limit: int = 50) -> list:
    """
    Подключается к Telegram через StringSession и собирает тексты последних сообщений.
    
    :param channels: Список юзернеймов или ссылок на каналы
    :param api_id: API ID от Telegram
    :param api_hash: API HASH от Telegram
    :param session_string: Строка сессии Telethon (StringSession)
    :param limit: Количество последних сообщений для анализа в каждом канале
    :return: Список строк (тексты сообщений)
    """
    if not api_id or not api_hash or not session_string:
        print("❌ [Collector] Ошибка: Не переданы ключи авторизации Telegram (API_ID/HASH/SESSION)!")
        return []

    if not channels:
        print("⚠️ [Collector] Предупреждение: Список каналов пуст.")
        return []

    raw_messages_text = []
    
    # Инициализируем асинхронный клиент Telethon
    client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
    
    try:
        print("📡 Подключение к серверам Telegram...")
        await client.connect()
        
        # Проверка на то, авторизован ли клиент (валидна ли сессия)
        if not await client.is_user_authorized():
            print("❌ [Collector] Ошибка: SESSION_STRING недействительна или устарела!")
            return []

        print(f"🚀 Авторизация успешна. Начинаю обход {len(channels)} каналов...")

        for channel in channels:
            try:
                print(f"📥 Сбор постов из: {channel}")
                
                async for message in client.iter_messages(channel, limit=limit):
                    if message.text:
                        raw_messages_text.append(message.text)
                        
                # Небольшая пауза между каналами, чтобы не ловить Flood за частые запросы
                await asyncio.sleep(1)
                
            except errors.FloodWaitError as e:
                print(f"⏳ [FloodWait] Telegram просит подождать {e.seconds} сек. Ждем...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"⚠️ [Collector] Не удалось прочесть канал {channel}: {e}")

    except Exception as e:
        print(f"❌ [Collector] Критическая ошибка во время работы с Telegram API: {e}")
    finally:
        # Обязательно закрываем сессию, чтобы не вешать соединение
        await client.disconnect()
        print("🔌 Соединение с Telegram закрыто.")

    return raw_messages_text
