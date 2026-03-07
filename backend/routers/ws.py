from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agents.registry import get_agent
import json
import uuid

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{agent_id}")
async def websocket_chat(websocket: WebSocket, agent_id: str):
    await websocket.accept()

    agent = get_agent(agent_id)
    if not agent:
        await websocket.send_json({"type": "error", "content": f"Agent '{agent_id}' not found"})
        await websocket.close()
        return

    # Each WebSocket session gets its own conversation thread
    thread_id = str(uuid.uuid4())
    await websocket.send_json({"type": "status", "content": f"Connected to {agent.name}"})

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("message", "").strip()

            if not user_message:
                continue

            await websocket.send_json({"type": "user", "content": user_message})
            await websocket.send_json({"type": "agent_start", "agent": agent.name})

            async for token in agent.stream_response(user_message, thread_id=thread_id):
                await websocket.send_json({"type": "token", "content": token})

            await websocket.send_json({"type": "agent_end"})

    except WebSocketDisconnect:
        pass
