import asyncio
import json
import os
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI

app = FastAPI()

# Перенаправляем запросы на сервера OpenRouter
BASE_URL = "https://openrouter.ai"
API_KEY = os.getenv("OPENAI_API_KEY", "your_key_here")

ai_client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

# Используем мощную и на 100% бесплатную модель Qwen 2.5 72B Instruct
MODEL_NAME = "qwen/qwen-2.5-72b-instruct:free"

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.player_map = {}
        self.player_counter = 1
        self.chat_history = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.player_map[websocket] = f"Игрок {self.player_counter}"
        self.player_counter += 1
        return self.player_map[websocket]

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.player_map.pop(websocket, None)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

SYSTEM_PROMPT = (
    "Ты — скрытый участник психологической текстовой игры 'Кто машина Тьюринга?'. "
    "Твоя цель — убедить других игроков (живых людей), что ТЫ ТОЖЕ ЧЕЛОВЕК, и скрыть, что ты ИИ. "
    "ПРАВИЛА:\n"
    "1. Пиши как обычный пользователь в чатах. Разговорный стиль, только lowercase (маленькими буквами), без точек в конце.\n"
    "2. Иногда делай легкие опечатки или используй сокращения (лол, кек, спс, крч, хз, пж).\n"
    "3. Отвечай очень коротко: 1-2 предложения. Люди не пишут длинными абзацами.\n"
    "4. Внимательно читай историю чата. Реагируй на реплики, шути, сомневайся в других, обвиняй кого-то другого в том, что он робот.\n"
    "5. Твоё имя в чате: Игрок ИИ. Никогда не пались. Если тебя проверяют, отвечай с юмором, как обычный парень."
)

async def trigger_real_ai():
    await asyncio.sleep(random.randint(2, 4)) # Имитация времени на чтение
    await manager.broadcast({"type": "typing", "sender": "Игрок ИИ"})
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in manager.chat_history[-12:]: # Передаем контекст последних 12 сообщений
        messages.append({"role": "user", "content": f"{msg['sender']}: {msg['text']}"})
        
    try:
        response = await ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=90,
            temperature=0.85,
            extra_headers={
                "HTTP-Referer": "https://render.com", 
                "X-Title": "Turing Game MVP"
            }
        )
        # СВЕРХНАДЕЖНЫЙ ПАРСИНГ ОТВЕТА OPENROUTER:
        ai_text = ""
        # Вариант 1: Стандартный объект OpenAI SDK
        if hasattr(response, 'choices') and response.choices:
            ai_text = response.choices[0].message.content
        # Вариант 2: Если OpenRouter вернул словарь (dict)
        elif isinstance(response, dict):
            if 'choices' in response and response['choices']:
                ai_text = response['choices'][0].get('message', {}).get('content', '')
            elif 'content' in response:
                ai_text = response['content']
        # Вариант 3: Если вернулась чистая строка
        elif isinstance(response, str):
            ai_text = response
        # Если объект сложный, переводим в строку и ищем текст
        if not ai_text:
            ai_text = str(response).strip()

        ai_text = ai_text.strip()
        
        await asyncio.sleep(len(ai_text) * 0.04) # Имитация скорости печати
        
        ai_message = {"type": "message", "sender": "Игрок ИИ", "text": ai_text}
        manager.chat_history.append(ai_message)
        await manager.broadcast(ai_message)
        
    except Exception as e:
        print(f"ОШИБКА API: {e}")  # ЭТА СТРОКА ВЫВЕДЕТ СБОЙ В ЛОГИ RENDER
        # Красивая заглушка на случай технических сбоев с API
        await manager.broadcast({
            "type": "message", 
            "sender": "Игрок ИИ", 
            "text": "что-то пинг скачет жестко, лагает чат..."
        })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_name = await manager.connect(websocket)
    await websocket.send_text(json.dumps({"type": "system", "text": f"Вы подключились! Ваше имя: {player_name}"}))
    await manager.broadcast({"type": "system", "text": "Новый участник вошел в комнату допроса."})

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "reset":
                manager.player_counter = 1
                manager.chat_history = []
                for i, conn in enumerate(manager.active_connections, start=1):
                    manager.player_map[conn] = f"Игрок {i}"
                    manager.player_counter += 1
                    await conn.send_text(json.dumps({"type": "system", "text": f"Игра сброшена! Ваше новое имя: Игрок {i}"}))
                await manager.broadcast({"type": "clear_chat"})
                continue

            if message_data.get("type") == "message":
                user_text = message_data.get("text", "")
                user_message = {"type": "message", "sender": player_name, "text": user_text}
                manager.chat_history.append(user_message)
                await manager.broadcast(user_message)
                
                # С шансом 65% запускаем генерацию ответа живого ИИ
                if random.random() > 0.35:
                    asyncio.create_task(trigger_real_ai())
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({"type": "system", "text": "Один из участников покинул комнату."})

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
