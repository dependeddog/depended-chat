from __future__ import annotations


def test_rest_send_message_broadcasts_message_created_to_chat_participants(ws_client, ws_connect, ws_two_users_chat):
    alice, bob, chat_id = ws_two_users_chat()

    with ws_connect(f"/ws/chats/{chat_id}", alice["access_token"]) as alice_chat_ws, ws_connect(
        f"/ws/chats/{chat_id}", bob["access_token"]
    ) as bob_chat_ws:
        alice_chat_ws.receive_json()
        bob_chat_ws.receive_json()

        response = ws_client.post(
            f"/chats/{chat_id}/messages",
            json={"text": "hello realtime"},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        message = response.json()

        alice_payload = alice_chat_ws.receive_json()
        bob_payload = bob_chat_ws.receive_json()

        for payload in (alice_payload, bob_payload):
            assert payload["event"] == "message.created"
            assert payload["data"]["id"] == message["id"]
            assert payload["data"]["chat_id"] == chat_id
            assert payload["data"]["sender_id"] == str(alice["id"])
            assert payload["data"]["text"] == "hello realtime"
            assert payload["data"]["created_at"]


def test_rest_send_message_broadcasts_chat_list_updated_to_events_channel(ws_client, ws_connect, ws_two_users_chat):
    alice, bob, chat_id = ws_two_users_chat()

    with ws_connect("/ws/events", bob["access_token"]) as bob_events_ws:
        bob_events_ws.receive_json()

        response = ws_client.post(
            f"/chats/{chat_id}/messages",
            json={"text": "hello unread"},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        message = response.json()

        chat_list_update = bob_events_ws.receive_json()
        assert chat_list_update["event"] == "chat.list.updated"
        assert chat_list_update["data"]["id"] == chat_id
        assert chat_list_update["data"]["unread_count"] == 1
        assert chat_list_update["data"]["last_message"]["id"] == message["id"]


def test_rest_mark_read_broadcasts_chat_read_and_chat_list_updated(ws_client, ws_connect, ws_two_users_chat):
    alice, bob, chat_id = ws_two_users_chat()

    msg_response = ws_client.post(
        f"/chats/{chat_id}/messages",
        json={"text": "to read"},
        headers=alice["headers"],
    )
    assert msg_response.status_code == 200

    with ws_connect(f"/ws/chats/{chat_id}", bob["access_token"]) as bob_chat_ws, ws_connect(
        "/ws/events", bob["access_token"]
    ) as bob_events_ws:
        bob_chat_ws.receive_json()
        bob_events_ws.receive_json()

        response = ws_client.post(f"/chats/{chat_id}/read", headers=bob["headers"])
        assert response.status_code == 200

        chat_read_event = bob_chat_ws.receive_json()
        assert chat_read_event["event"] == "chat.read"
        assert chat_read_event["data"]["chat_id"] == chat_id
        assert chat_read_event["data"]["user_id"] == str(bob["id"])
        assert chat_read_event["data"]["read_up_to_message_id"] is None

        chat_list_update = bob_events_ws.receive_json()
        assert chat_list_update["event"] == "chat.list.updated"
        assert chat_list_update["data"]["id"] == chat_id
        assert chat_list_update["data"]["unread_count"] == 0


def test_typing_events_broadcast_to_chat_participants(ws_connect, ws_two_users_chat):
    alice, bob, chat_id = ws_two_users_chat()

    with ws_connect(f"/ws/chats/{chat_id}", alice["access_token"]) as alice_chat_ws, ws_connect(
        f"/ws/chats/{chat_id}", bob["access_token"]
    ) as bob_chat_ws:
        alice_chat_ws.receive_json()
        bob_chat_ws.receive_json()

        alice_chat_ws.send_json({"event": "typing.start", "data": {}})
        started = bob_chat_ws.receive_json()
        assert started["event"] == "typing.started"
        assert started["data"]["chat_id"] == chat_id
        assert started["data"]["user_id"] == str(alice["id"])

        alice_chat_ws.send_json({"event": "typing.stop", "data": {}})
        stopped = bob_chat_ws.receive_json()
        assert stopped["event"] == "typing.stopped"
        assert stopped["data"]["chat_id"] == chat_id
        assert stopped["data"]["user_id"] == str(alice["id"])


def test_unknown_ws_event_returns_error(ws_connect, ws_two_users_chat):
    alice, _, chat_id = ws_two_users_chat()

    with ws_connect(f"/ws/chats/{chat_id}", alice["access_token"]) as websocket:
        websocket.receive_json()
        websocket.send_json({"event": "unknown.event", "data": {}})

        error_event = websocket.receive_json()
        assert error_event["event"] == "error"
        assert error_event["data"]["detail"] == "Unsupported event"


def test_multiple_event_connections_same_user_receive_updates(ws_client, ws_connect, ws_two_users_chat):
    alice, bob, chat_id = ws_two_users_chat()

    with ws_connect("/ws/events", bob["access_token"]) as bob_events_1, ws_connect(
        "/ws/events", bob["access_token"]
    ) as bob_events_2:
        bob_events_1.receive_json()
        bob_events_2.receive_json()

        response = ws_client.post(
            f"/chats/{chat_id}/messages",
            json={"text": "fanout"},
            headers=alice["headers"],
        )
        assert response.status_code == 200

        payload_1 = bob_events_1.receive_json()
        payload_2 = bob_events_2.receive_json()

        assert payload_1["event"] == "chat.list.updated"
        assert payload_1["data"]["id"] == chat_id
        assert payload_2["event"] == "chat.list.updated"
        assert payload_2["data"]["id"] == chat_id


def test_disconnect_removes_connection_from_manager(ws_connect, ws_register_and_login):
    from src.chat.ws_manager import ws_manager

    user = ws_register_and_login("disconnect_user")

    with ws_connect("/ws/events", user["access_token"]) as websocket:
        websocket.receive_json()
        assert len(ws_manager._user_connections[user["id"]]) == 1

    assert user["id"] not in ws_manager._user_connections
