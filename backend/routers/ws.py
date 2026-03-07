from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agents.orchestrator import get_orchestrator
from db.sessions import touch_session
from langgraph.types import Command
import json
import asyncio

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()

    graph = get_orchestrator()
    config = {"configurable": {"thread_id": session_id}}

    await websocket.send_json({"type": "status", "content": "Connected to SeaMate"})

    # pending HiL interrupt state
    pending_interrupt = None

    async def send(msg: dict):
        await websocket.send_json(msg)

    async def run_stream(input_payload):
        """Stream graph output and handle subgraphs + tool visibility."""
        nonlocal pending_interrupt

        current_subagent = None

        try:
            async for namespace, chunk in graph.astream(
                input_payload,
                config=config,
                stream_mode=["messages", "updates"],
                subgraphs=True,
            ):
                mode, data = chunk[0], chunk[1]
                is_subagent = any(s.startswith("tools:") for s in namespace)

                if mode == "updates":
                    # ── Interrupt (HiL) ──────────────────────────────────
                    if "__interrupt__" in data:
                        interrupts = data["__interrupt__"]
                        for interrupt_obj in interrupts:
                            val = interrupt_obj.value if hasattr(interrupt_obj, "value") else interrupt_obj
                            action_requests = val.get("action_requests", [])
                            for req in action_requests:
                                iid = req.get("id", session_id + "_int")
                                pending_interrupt = iid
                                await send({
                                    "type": "interrupt",
                                    "interrupt_id": iid,
                                    "tool": req.get("name"),
                                    "args": req.get("args", {}),
                                })
                        return  # wait for client decision

                    # ── Tool start / end ─────────────────────────────────
                    for node_name, node_data in data.items():
                        if not isinstance(node_data, dict):
                            continue
                        for msg in node_data.get("messages", []):
                            # tool calls → tool_start
                            for tc in getattr(msg, "tool_calls", []):
                                await send({
                                    "type": "tool_start",
                                    "tool": tc["name"],
                                    "args": tc.get("args", {}),
                                    "subagent": current_subagent,
                                })
                            # tool results → tool_end
                            if getattr(msg, "type", None) == "tool":
                                result = str(msg.content)
                                await send({
                                    "type": "tool_end",
                                    "tool": getattr(msg, "name", ""),
                                    "result": result[:500],  # cap length
                                    "subagent": current_subagent,
                                })

                elif mode == "messages":
                    token, _meta = data

                    if is_subagent:
                        # identify subagent name from namespace
                        sub_ns = next((s for s in namespace if s.startswith("tools:")), "")
                        sub_name = sub_ns.split(":")[1] if ":" in sub_ns else sub_ns

                        if sub_name != current_subagent:
                            if current_subagent:
                                await send({"type": "subagent_end", "name": current_subagent})
                            current_subagent = sub_name
                            await send({"type": "subagent_start", "name": sub_name})

                        if token.content and not getattr(token, "tool_call_chunks", None):
                            if getattr(token, "type", "") in ("AIMessageChunk", "AIMessage"):
                                await send({"type": "subagent_token", "name": sub_name, "content": token.content})
                    else:
                        # main orchestrator token
                        if current_subagent:
                            await send({"type": "subagent_end", "name": current_subagent})
                            current_subagent = None

                        if token.content and not getattr(token, "tool_call_chunks", None):
                            if getattr(token, "type", "") in ("AIMessageChunk", "AIMessage"):
                                await send({"type": "token", "content": token.content})

        except Exception as e:
            await send({"type": "error", "content": str(e)})
            return

        if current_subagent:
            await send({"type": "subagent_end", "name": current_subagent})

        await send({"type": "agent_end"})
        touch_session(session_id)

    # ── Main receive loop ────────────────────────────────────────────────────
    try:
        # Resume any existing conversation
        await run_stream(None)  # no-op if no pending state

    except Exception:
        pass  # fresh session, ignore

    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            msg_type = payload.get("type", "message")

            if msg_type == "message":
                user_text = payload.get("message", "").strip()
                if not user_text:
                    continue
                await send({"type": "user", "content": user_text})
                await send({"type": "agent_start"})
                await run_stream({"messages": [{"role": "user", "content": user_text}]})

            elif msg_type == "decision":
                decision_type = payload.get("decision", "approve")
                iid = payload.get("interrupt_id")
                pending_interrupt = None

                resume_decision = [{"type": decision_type}]
                await send({"type": "agent_start"})
                await run_stream(Command(resume={"decisions": resume_decision}))

    except WebSocketDisconnect:
        pass
