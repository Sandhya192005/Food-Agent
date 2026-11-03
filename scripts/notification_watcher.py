"""Desktop notification watcher for the AI Food Agent's proactive agents.

Runs as a separate, standalone process from the API server. Polls
GET /notifications/pending as one logged-in user and pops up a real Windows
toast notification with clickable Yes/No buttons for each new one it finds.
The script waits indefinitely for you to click one before checking again -
it will not move on or time out on its own.

Usage:
    pip install -r scripts/requirements-watcher.txt
    python scripts/notification_watcher.py

Credentials: set AGENT_EMAIL / AGENT_PASSWORD as environment variables, or
just leave them unset and the script will prompt for them interactively.
"""

import os
import sys
import threading
import time
from getpass import getpass

import requests
from windows_toasts import (
    InteractableWindowsToaster,
    Toast,
    ToastActivatedEventArgs,
    ToastButton,
    ToastDuration,
)

BASE_URL = os.environ.get("AGENT_BASE_URL", "http://127.0.0.1:8000/api/v1")
POLL_SECONDS = int(os.environ.get("AGENT_POLL_SECONDS", "30"))

toaster = InteractableWindowsToaster("AI Food Agent")


def login(email: str, password: str) -> str:
    response = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_pending(token: str) -> list[dict]:
    response = requests.get(
        f"{BASE_URL}/notifications/pending", headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 401:
        raise PermissionError("token expired")
    response.raise_for_status()
    return response.json()


def respond(token: str, notification_id: int, answer: str) -> None:
    response = requests.post(
        f"{BASE_URL}/notifications/{notification_id}/respond",
        json={"response": answer},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()


def ask_via_toast(message: str) -> str:
    """Shows a toast with real Yes/No buttons and blocks until one is clicked -
    no timeout, matches "wait until I press yes/no" rather than guessing or
    moving on."""
    answered = threading.Event()
    result: dict[str, str] = {}

    def on_activated(args: ToastActivatedEventArgs) -> None:
        result["answer"] = args.arguments
        answered.set()

    toast = Toast([message])
    toast.AddAction(ToastButton("Yes", "yes"))
    toast.AddAction(ToastButton("No", "no"))
    toast.on_activated = on_activated
    toast.duration = ToastDuration.Long

    toaster.show_toast(toast)
    print(f'  Popup shown: "{message}" — waiting for you to click Yes or No...')
    answered.wait()  # deliberately no timeout
    return result["answer"]


def main() -> None:
    email = os.environ.get("AGENT_EMAIL") or input("Email: ").strip()
    password = os.environ.get("AGENT_PASSWORD") or getpass("Password: ")

    print(f"Logging in as {email} ...")
    token = login(email, password)
    print(f"Watching {BASE_URL}/notifications/pending every {POLL_SECONDS}s. Ctrl+C to stop.\n")

    seen_ids: set[int] = set()

    while True:
        try:
            pending = fetch_pending(token)
        except PermissionError:
            print("Token expired, logging in again...")
            token = login(email, password)
            continue
        except requests.RequestException as exc:
            print(f"Could not reach the server ({exc}), retrying in {POLL_SECONDS}s...")
            time.sleep(POLL_SECONDS)
            continue

        new_ones = [n for n in pending if n["id"] not in seen_ids]
        for notification in new_ones:
            seen_ids.add(notification["id"])
            print(f'\n[{notification["type"]}] {notification["message"]}')
            answer = ask_via_toast(notification["message"])
            respond(token, notification["id"], answer)
            print(f"  Recorded: {answer}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
