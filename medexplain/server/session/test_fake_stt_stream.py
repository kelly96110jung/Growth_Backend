from fake_stt_stream import fake_stt_stream

if __name__ == "__main__":
    session_id = "test-session-123"

    for event in fake_stt_stream(session_id):
        print(event.model_dump_json())
