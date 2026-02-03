from session_manager import SessionManager, SessionState

if __name__ == "__main__":
    sm = SessionManager()

    s = sm.create_session()
    print("created:", s.session_id, s.state)

    sm.set_state(s.session_id, SessionState.STREAMING)
    s2 = sm.get_session(s.session_id)
    print("state:", s2.session_id, s2.state)

    sm.end_session(s.session_id, reason="manual test")
    s3 = sm.get_session(s.session_id)
    print("ended:", s3.session_id, s3.state)
