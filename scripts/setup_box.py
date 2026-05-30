"""One-shot Box setup.

Authenticates with the same credentials the game uses (CCG if BOX_ENTERPRISE_ID
is set, otherwise the Developer Token), finds-or-creates a `ShellQuest/state/`
folder hierarchy, and prints the state folder ID to paste into .env.

Usage:
    python scripts/setup_box.py
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _client():
    from boxsdk import Client
    cid = os.environ.get("BOX_CLIENT_ID")
    sec = os.environ.get("BOX_CLIENT_SECRET")
    ent = os.environ.get("BOX_ENTERPRISE_ID")
    tok = os.environ.get("BOX_DEVELOPER_TOKEN")
    if not (cid and sec and (ent or tok)):
        raise SystemExit(
            "Set BOX_CLIENT_ID, BOX_CLIENT_SECRET and either "
            "BOX_ENTERPRISE_ID (CCG) or BOX_DEVELOPER_TOKEN in .env first.")
    if ent:
        from boxsdk import CCGAuth
        auth = CCGAuth(client_id=cid, client_secret=sec, enterprise_id=ent)
    else:
        from boxsdk import OAuth2
        auth = OAuth2(client_id=cid, client_secret=sec, access_token=tok)
    return Client(auth)


def _find_or_create_subfolder(client, parent_id, name):
    parent = client.folder(parent_id)
    for item in parent.get_items():
        if item.name == name and item.type == "folder":
            print(f"Found existing {name!r} folder: {item.id}")
            return item.id
    created = parent.create_subfolder(name)
    print(f"Created {name!r} folder: {created.id}")
    return created.id


def main():
    client = _client()
    user = client.user().get()
    print(f"Connected as: {user.name}\n")

    sq_id = _find_or_create_subfolder(client, "0", "ShellQuest")
    state_id = _find_or_create_subfolder(client, sq_id, "state")

    print("\nAdd this to your .env:")
    print(f"BOX_STATE_FOLDER_ID={state_id}")


if __name__ == "__main__":
    main()
