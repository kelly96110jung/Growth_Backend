import asyncio
import websockets

WS_URL = "ws://127.0.0.1:8000/ws/stt"


async def main():
    async with websockets.connect(WS_URL) as ws:
        print("CONNECTED")

        # start 보내기
        await ws.send("start:test-session")
        print("SENT: start")

        # ✅ M2에서는 최소 5개(stt 3 + translation 2)까지 받아야 함
        # warning까지 오면 더 올 수 있으니 넉넉히 7개 받기
        max_messages = 7

        for i in range(1, max_messages + 1):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                print(f"TIMEOUT after receiving {i-1} messages")
                break

            print(f"RECV[{i}]: {msg}")


if __name__ == "__main__":
    asyncio.run(main())
