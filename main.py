import asyncio
import json
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

# База активных подключений пользователей
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.player_map = {}  # websocket -> "Игрок X"
        self.player_counter = 1

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

# Симуляция ответов ИИ-соперника (для MVP теста)
AI_RESPONSES = [
    "лол, вы че так серьезно к этому относитесь?))",
    "Игрок 1 подозрительно долго молчит, походу он робот 🤖",
    "я вообще чай пью щас, че вы прикопались со своими проверками кек",
    "хз крч, по-моему тут все люди, ну кроме Игрока 2)",
    "база, согласен с прошлым сообщением",
    "пжлст, давайте без капчей в чате, у меня мозг кипит",
    "да живой я, живой) че доказать-то надо?"
]

async def trigger_ai_behavior():
    """Имитирует человека: думает, включает статус 'печатает' и выдает фразу"""
    await asyncio.sleep(random.randint(3, 6)) # Думает
    
    # Отправляем сигнал, что ИИ ("Игрок ИИ") начал печатать
    await manager.broadcast({"type": "typing", "sender": "Игрок ИИ"})
    await asyncio.sleep(random.randint(2, 4)) # Печатает
    
    ai_text = random.choice(AI_RESPONSES)
    await manager.broadcast({
        "type": "message",
        "sender": "Игрок ИИ",
        "text": ai_text
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_name = await manager.connect(websocket)
    
    # Приветствуем игрока и сообщаем его скрытое имя
    await websocket.send_text(json.dumps({
        "type": "system", 
        "text": f"Вы подключились! В этой комнате ваше имя: {player_name}"
    }))
    
    # Оповещаем остальных анонимно
    await manager.broadcast({
        "type": "system", 
        "text": f"Новый участник вошел в комнату допроса."
    })

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                user_text = message_data.get("text", "")
                
                # Рассылаем всем сообщение от скрытого имени "Игрок Х"
                await manager.broadcast({
                    "type": "message",
                    "sender": player_name,
                    "text": user_text
                })
                
                # С шансом 60% запускаем ответ ИИ-игрока на реплику человека
                if random.random() > 0.4:
                    asyncio.create_task(trigger_ai_behavior())
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({
            "type": "system", 
            "text": "Один из участников покинул комнату."
        })

# Главная страница (подгружает наш HTML-интерфейс)
@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
