import asyncio
import websockets

async def main():
    uri = "ws://127.0.0.1:8000/ws/stt"
    async with websockets.connect(uri) as ws:
        print("CONNECTED")

        # start 보내기
        await ws.send("start:test-session")
        print("SENT: start")

        # 이벤트 3개 받기 (interim, interim, final)
        for i in range(3):
            msg = await ws.recv()
            print(f"RECV[{i+1}]:", msg)

asyncio.run(main())
