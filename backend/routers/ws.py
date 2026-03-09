"""
WebSocket chat — streams AI tokens with subagent identification + interrupt handling.
Single /ws endpoint, supports approve/reject for dangerous tools.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langgraph.types import Command
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


async def _stream_events(ws: WebSocket, graph, input_data, config: dict) -> bool:
    """Stream graph events to the WebSocket client.

    Returns True if streaming completed normally, False if client disconnected.

    Subagent identification:
      DeepAgents routes all subagents through a single "tools" node, so the
      LangGraph namespace is always ('tools:<uuid>',) regardless of which
      subagent is active.  To identify the *actual* subagent, we look at
      completed tool_calls from the orchestrator (namespace=()) where
      tool name is "task" — the args contain "subagent_type".
    """
    active_subagent = "subagent"  # fallback label

    try:
        async for event in graph.astream(
            input_data,
            config=config,
            stream_mode="messages",
            subgraphs=True,
        ):
            if not isinstance(event, (tuple, list)) or len(event) != 2:
                continue

            namespace, chunk = event

            if not isinstance(namespace, tuple):
                continue
            if not isinstance(chunk, (tuple, list)) or len(chunk) != 2:
                continue

            token = chunk[0]

            # ── Track subagent dispatch from orchestrator ──
            # DeepAgents uses a "task" tool to dispatch subagents.
            # tool_calls (completed) contain full args with "subagent_type".
            # tool_call_chunks (streaming) are partial JSON fragments.
            tool_calls = getattr(token, "tool_calls", None)
            if tool_calls and namespace == ():
                for tc in tool_calls:
                    if tc.get("name") == "task":
                        args = tc.get("args", {})
                        sub = args.get("subagent_type", "")
                        if sub:
                            active_subagent = sub

            tool_call_chunks = getattr(token, "tool_call_chunks", None)
            if tool_call_chunks:
                continue  # don't stream tool-call fragments to client

            # Only stream AI text content
            content = getattr(token, "content", None)
            if not content:
                continue

            token_type = getattr(token, "type", "")
            if token_type not in ("AIMessageChunk", "AIMessage", "ai"):
                continue

            # Determine agent: orchestrator vs tracked subagent
            if namespace == ():
                agent = "seamate"
            else:
                agent = active_subagent

            if not await _safe_send(ws, {
                "type": "token", "content": content, "agent": agent,
            }):
                return False

    except WebSocketDisconnect:
        return False
    except Exception as e:
        log.warning("Stream error: %s", e)
        await _safe_send(ws, {"type": "error", "content": str(e)})

    return True


async def _check_interrupts(ws: WebSocket, graph, config: dict,
                            pending: dict) -> bool:
    """Check graph state for pending interrupts after streaming.

    Sends interrupt cards to the client and stores interrupt info in `pending`.
    Returns False if client disconnected.
    """
    try:
        state = await graph.aget_state(config)
        for task in state.tasks:
            for intr in task.interrupts:
                hitl = intr.value  # HITLRequest dict
                action_requests = hitl.get("action_requests", [])
                num_actions = len(action_requests)

                if num_actions == 0:
                    continue

                # Store for later resume
                pending[intr.id] = {"num_actions": num_actions}

                # Send one interrupt card per action_request
                for action in action_requests:
                    if not await _safe_send(ws, {
                        "type": "interrupt",
                        "interrupt_id": intr.id,
                        "tool": action.get("name", "unknown"),
                        "args": action.get("args", {}),
                        "description": action.get("description", ""),
                    }):
                        return False
    except Exception as e:
        log.warning("State check error: %s", e)

    return True


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    graph = websocket.app.state.graph
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    pending_interrupts: dict = {}  # interrupt_id → {num_actions: int}

    if not await _safe_send(websocket, {
        "type": "status", "content": "Connected to SeaMate",
    }):
        return

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = payload.get("type")

            # ── User message ─────────────────────────────────────────
            if msg_type == "message":
                user_text = payload.get("message", "").strip()
                if not user_text:
                    continue

                if not await _safe_send(websocket, {"type": "agent_start"}):
                    return

                ok = await _stream_events(
                    websocket, graph,
                    {"messages": [{"role": "user", "content": user_text}]},
                    config,
                )
                if not ok:
                    return

                # Check for interrupts (tool approval needed)
                if not await _check_interrupts(
                    websocket, graph, config, pending_interrupts
                ):
                    return

                if not await _safe_send(websocket, {"type": "agent_end"}):
                    return

            # ── Interrupt response (approve / reject) ────────────────
            elif msg_type == "interrupt_response":
                interrupt_id = payload.get("interrupt_id")
                decision = payload.get("decision", "reject")

                # Build decisions list (one per action_request in the HITLRequest)
                info = pending_interrupts.pop(interrupt_id, {})
                num_actions = info.get("num_actions", 1)

                if decision == "approve":
                    decisions = [{"type": "approve"}] * num_actions
                else:
                    decisions = [
                        {"type": "reject", "message": "User rejected this action."}
                    ] * num_actions

                cmd = Command(resume={"decisions": decisions})

                if not await _safe_send(websocket, {"type": "agent_start"}):
                    return

                ok = await _stream_events(websocket, graph, cmd, config)
                if not ok:
                    return

                # Could be another interrupt after resume
                if not await _check_interrupts(
                    websocket, graph, config, pending_interrupts
                ):
                    return

                if not await _safe_send(websocket, {"type": "agent_end"}):
                    return

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("WebSocket fatal: %s", e)
