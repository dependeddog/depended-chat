from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_get_and_patch_my_profile(client, create_user, auth_header):
    user = await create_user("alice")
    headers = await auth_header("alice")

    get_response = await client.get("/users/me/profile", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == str(user.id)
    assert body["username"] == "alice"
    assert body["bio"] is None
    assert body["has_avatar"] is False
    assert body["avatar_url"] is None
    assert body["avatar_mime_type"] is None
    assert body["last_seen_at"] is not None

    patch_response = await client.patch("/users/me/profile", json={"bio": "Hello world"}, headers=headers)
    assert patch_response.status_code == 200
    assert patch_response.json()["bio"] == "Hello world"

    clear_response = await client.patch("/users/me/profile", json={"bio": "   "}, headers=headers)
    assert clear_response.status_code == 200
    assert clear_response.json()["bio"] is None


@pytest.mark.asyncio
async def test_avatar_upload_replace_delete(client, create_user, auth_header):
    user = await create_user("alice")
    headers = await auth_header("alice")

    upload_response = await client.put(
        "/users/me/avatar",
        headers=headers,
        files={"avatar": ("avatar.png", b"png-bytes", "image/png")},
    )
    assert upload_response.status_code == 200
    assert upload_response.json() == {
        "has_avatar": True,
        "avatar_url": f"/users/{user.id}/avatar",
        "avatar_mime_type": "image/png",
    }

    avatar_response = await client.get(f"/users/{user.id}/avatar")
    assert avatar_response.status_code == 200
    assert avatar_response.headers["content-type"] == "image/png"
    assert avatar_response.content == b"png-bytes"

    replace_response = await client.put(
        "/users/me/avatar",
        headers=headers,
        files={"avatar": ("avatar.jpg", b"jpg-bytes", "image/jpeg")},
    )
    assert replace_response.status_code == 200

    avatar_after_replace = await client.get(f"/users/{user.id}/avatar")
    assert avatar_after_replace.status_code == 200
    assert avatar_after_replace.headers["content-type"] == "image/jpeg"
    assert avatar_after_replace.content == b"jpg-bytes"

    delete_response = await client.delete("/users/me/avatar", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["has_avatar"] is False

    missing_avatar_response = await client.get(f"/users/{user.id}/avatar")
    assert missing_avatar_response.status_code == 404


@pytest.mark.asyncio
async def test_last_seen_routes_and_user_profile_access(client, create_user, auth_header):
    await create_user("alice")
    bob = await create_user("bob")
    headers = await auth_header("alice")

    my_last_seen = await client.get("/users/me/last-seen", headers=headers)
    assert my_last_seen.status_code == 200
    first_last_seen = datetime.fromisoformat(my_last_seen.json()["last_seen_at"])

    update_last_seen = await client.patch("/users/me/last-seen", headers=headers)
    assert update_last_seen.status_code == 200
    updated_last_seen = datetime.fromisoformat(update_last_seen.json()["last_seen_at"])
    assert updated_last_seen >= first_last_seen

    bob_profile = await client.get(f"/users/{bob.id}/profile", headers=headers)
    assert bob_profile.status_code == 200
    assert bob_profile.json()["id"] == str(bob.id)
    assert bob_profile.json()["has_avatar"] is False

    bob_last_seen = await client.get(f"/users/{bob.id}/last-seen", headers=headers)
    assert bob_last_seen.status_code == 200
    assert bob_last_seen.json()["user_id"] == str(bob.id)

    missing_profile = await client.get("/users/00000000-0000-0000-0000-000000000000/profile", headers=headers)
    assert missing_profile.status_code == 404

    missing_last_seen = await client.get("/users/00000000-0000-0000-0000-000000000000/last-seen", headers=headers)
    assert missing_last_seen.status_code == 404
