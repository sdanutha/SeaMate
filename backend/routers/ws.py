"""
Minimal WebSocket chat — no sessions, no DB.
Single /ws endpoint, streams AI tokens back.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import uuid

router = APIRouter()


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    graph = websocket.app.state.graph
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    await websocket.send_json({
        "type": "status", "content": "Connected to SeaMate"
    })

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)

            if payload.get("type") != "message":
                continue

            user_text = payload.get("message", "").strip()
            if not user_text:
                continue

            await websocket.send_json({"type": "agent_start"})

            try:
                async for event in graph.astream(
                    {"messages": [{"role": "user", "content": user_text}]},
                    config=config,
                    stream_mode="messages",
                    subgraphs=True,
                ):
                    # Expect (namespace, (token, metadata))
                    if (
                        not isinstance(event, (tuple, list))
                        or len(event) != 2
                    ):
                        continue

                    namespace, chunk = event

                    if not isinstance(namespace, tuple):
                        continue
                    if (
                        not isinstance(chunk, (tuple, list))
                        or len(chunk) != 2
                    ):
                        continue

                    token = chunk[0]

                    # Skip tool-call fragments
                    if getattr(token, "tool_call_chunks", None):
                        continue

                    # Only stream AI text content
                    content = getattr(token, "content", None)
                    if not content:
                        continue

                    token_type = getattr(token, "type", "")
                    if token_type not in (
                        "AIMessageChunk", "AIMessage", "ai"
                    ):
                        continue

                    await websocket.send_json({
                        "type": "token", "content": content
                    })

            except Exception as e:
                await websocket.send_json({
                    "type": "error", "content": str(e)
                })

            await websocket.send_json({"type": "agent_end"})

    except WebSocketDisconnect:
        pass
