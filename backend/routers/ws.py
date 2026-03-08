"""
Minimal WebSocket chat — no sessions, no DB.
Single /ws endpoint, streams AI tokens back.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import uuid
import logging

router = APIRouter()
log = logging.getLogger("seamate.ws")


async def _safe_send(ws: WebSocket, data: dict) -> bool:
    """Send JSON to the WebSocket. Returns False if the client is gone."""
    try:
        await ws.send_json(data)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    graph = websocket.app.state.graph
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    if not await _safe_send(websocket, {
        "type": "status", "content": "Connected to SeaMate"
    }):
        return

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if payload.get("type") != "message":
                continue

            user_text = payload.get("message", "").strip()
            if not user_text:
                continue

            if not await _safe_send(websocket, {"type": "agent_start"}):
                return

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

                    if not await _safe_send(websocket, {
                        "type": "token", "content": content
                    }):
                        return

            except WebSocketDisconnect:
                return
            except Exception as e:
                log.warning("Stream error: %s", e)
                if not await _safe_send(websocket, {
                    "type": "error", "content": str(e)
                }):
                    return

            if not await _safe_send(websocket, {"type": "agent_end"}):
                return

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("WebSocket fatal: %s", e)
