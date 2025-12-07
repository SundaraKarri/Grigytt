import streamlit as st
import asyncio
import threading
import json
import websockets
import time
import datetime
import subprocess
import os
from websockets.exceptions import ConnectionClosed

# ============================================================
# GLOBAL SERVER STATE
# ============================================================
clients = {}
timestamp = datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z"

# ============================================================
# ASYNC RELAY SERVER
# ============================================================
async def handler(ws):
    try:
        raw = await ws.recv()
        hello = json.loads(raw)

        cid = hello.get("id")
        if not cid:
            await ws.send(json.dumps({"type":"error","message":"missing id"}))
            return

        clients[cid] = ws
        print(f"[SERVER] {cid} connected")

        # Send peer list
        peers = [p for p in clients.keys() if p != cid]
        await ws.send(json.dumps({"type":"peers", "peers": peers}))

        # Main loop
        async for msg in ws:
            try:
                obj = json.loads(msg)
                target = obj.get("to")
                if not target:
                    continue

                if target in clients:
                    await clients[target].send(json.dumps({
                        "from": cid,
                        "payload": obj.get("payload"),
                        "msg_id": obj.get("msg_id")
                    }))
            except:
                continue

    except ConnectionClosed:
        pass
    except:
        pass
    finally:
        if cid in clients:
            print(f"[SERVER] {cid} disconnected")
            del clients[cid]


async def start_server():
    server = await websockets.serve(handler, "0.0.0.0", 8765)
    print("[SERVER] Relay running on ws://0.0.0.0:8765")
    await server.wait_closed()

# ============================================================
# START SERVER IN BACKGROUND THREAD (Streamlit-safe)
# ============================================================
def start_server_thread():
    asyncio.run(start_server())

def launch_server_if_not_running():
    if "server_running" not in st.session_state:
        st.session_state["server_running"] = False

    if not st.session_state["server_running"]:
        thread = threading.Thread(target=start_server_thread, daemon=True)
        thread.start()
        st.session_state["server_running"] = True
        st.success("Relay Server Started on ws://0.0.0.0:8765 🚀")


# ============================================================
# CLIENT IMPLEMENTATION
# ============================================================
async def run_client(name, target, payload, duration):
    uri = "ws://localhost:8765"

    try:
        ws = await websockets.connect(uri)
        await ws.send(json.dumps({"type":"hello","id":name}))

        t_end = time.time() + duration
        i = 0

        while time.time() < t_end:
            msg = {
                "to": target,
                "payload": payload,
                "msg_id": f"{name}-{i}"
            }
            await ws.send(json.dumps(msg))
            print(f"[{name}] sent to {target}: {payload}")
            await asyncio.sleep(1)
            i += 1

        await ws.close()

    except Exception as e:
        print(f"[{name}] ERROR: {e}")

def run_client_thread(name, target, payload, duration):
    asyncio.run(run_client(name, target, payload, duration))


# ============================================================
# STREAMLIT UI
# ============================================================
st.title("🚦 Multi-Client | 1 to 1 | Synchronous Relay Tester (Streamlit GUI)")
st.subheader("WebSocket Relay + Editable Payload + Timed Messaging")
st.subheader("| Version 1 |")
# Start server
if st.button("Start Relay Server"):
    launch_server_if_not_running()

st.divider()
st.header("📡 Launch a Client")

client_name = st.text_input("Client Name", "clientA")
target_name = st.text_input("Target Client", "clientB")

payload_text = st.text_area(
    "Payload (JSON Allowed)",
    '{"type": "message",'
    '"sender": "clientA",'
    '"text": "Hello! This project is Version 1.",'
    '"sent_at": "2025-12-08T02:30:04.878Z"}')

duration_sec = st.number_input("Duration (seconds)", 5, 300, 10)

if st.button("Start Client"):
    try:
        json.loads(payload_text)  # validate
    except:
        st.error("Payload must be valid JSON string!")
    else:
        thread = threading.Thread(
            target=run_client_thread,
            args=(client_name, target_name, json.loads(payload_text), duration_sec),
            daemon=True
        )
        thread.start()
        st.success(f"Client **{client_name}** started → sending to **{target_name}**")


st.divider()
st.header("⚙ Server Status")
if "server_running" in st.session_state and st.session_state["server_running"]:
    st.success("Server is running ✔")
else:
    st.warning("Server is not running")


