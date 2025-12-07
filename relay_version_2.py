import streamlit as st
import asyncio
import threading
import json
import websockets
import time
import datetime
import random
from websockets.exceptions import ConnectionClosed

# ============================================================
# GLOBAL SERVER STATE
# ============================================================
clients = {}
client_threads = []
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

        async for msg in ws:
            try:
                obj = json.loads(msg)
                target = obj.get("to")
                if target:
                    if isinstance(target, list):
                        # Send to all targets
                        for t in target:
                            if t in clients:
                                await clients[t].send(json.dumps({
                                    "from": cid,
                                    "payload": obj.get("payload"),
                                    "msg_id": obj.get("msg_id")
                                }))
                    else:
                        # Single target
                        if target in clients:
                            await clients[target].send(json.dumps({
                                "from": cid,
                                "payload": obj.get("payload"),
                                "msg_id": obj.get("msg_id")
                            }))
            except Exception as e:
                print(f"[SERVER ERROR] {e}")
                continue

    except ConnectionClosed:
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
# SERVER THREAD MANAGEMENT
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

def launch_client(name, target, payload, duration):
    thread = threading.Thread(
        target=run_client_thread,
        args=(name, target, payload, duration),
        daemon=True
    )
    thread.start()
    client_threads.append(thread)
    print(f"[UI] Client {name} launched to send to {target}")

# ============================================================
# STREAMLIT UI
# ============================================================
st.title("🚦 Multi-Client | 1 to Many | Asynchronous Relay Tester (Streamlit GUI)")
st.subheader("WebSocket Relay + Editable Payload + Timed Messaging")
st.subheader("| Version 2 |")
# Start server
if st.button("Start Relay Server"):
    launch_server_if_not_running()

st.divider()
st.header("📡 Launch Multiple Clients")

num_clients = st.number_input("Number of clients to launch", 1, 50, 3)
base_name = st.text_input("Base Client Name", "Sridhar")
targets_text = st.text_area(
    "Targets (comma-separated client IDs)",
    "ClientA, ClientB, ClientC"
)
duration_sec = st.number_input("Duration (seconds)", 5, 300, 10)
payload_text = st.text_area(
    "Payload (JSON Allowed)",
    '{"type": "message",'
    '"sender": "clientA",'
    '"text": "Hello! This project is Version 1.",'
    '"sent_at": "2025-12-08T02:30:04.878Z"}')

random_payload = st.checkbox("Randomize payload 'value' field for each client", True)
send_to_all_targets = st.checkbox("Send each client to all targets simultaneously", False)

# Launch clients
if st.button("Launch Clients"):
    try:
        base_payload = json.loads(payload_text)
    except:
        st.error("Payload must be valid JSON!")
    else:
        targets = [t.strip() for t in targets_text.split(",") if t.strip()]
        if not targets:
            st.error("Provide at least one target client!")
        else:
            # Shuffle targets for randomness
            assigned_targets = targets.copy()
            random.shuffle(assigned_targets)

            for i in range(1, num_clients+1):
                client_name = f"{base_name}{i}"
                if send_to_all_targets:
                    target = targets  # list of all targets
                else:
                    # Round-robin assignment
                    target = assigned_targets[(i-1) % len(assigned_targets)]

                payload = base_payload.copy()
                if random_payload:
                    payload["value"] = random.randint(1, 9999)

                launch_client(client_name, target, payload, duration_sec)

            st.success(f"Launched {num_clients} clients sending to {len(targets)} target(s) ✅")

st.divider()
st.header("⚙ Server Status")
if "server_running" in st.session_state and st.session_state["server_running"]:
    st.success("Server is running ✔")
else:
    st.warning("Server is not running")

st.subheader("🖥 Active Client Threads")
if client_threads:
    for t in client_threads:
        st.text(f"{t.name} (alive: {t.is_alive()})")
else:
    st.text("No clients running yet.")
