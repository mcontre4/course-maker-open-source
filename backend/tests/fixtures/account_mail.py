import re
import time

import httpx


def wait_for_mailpit(inbox_url):
    deadline = time.monotonic() + 30
    while True:
        try:
            httpx.get(inbox_url + "/readyz", timeout=1).raise_for_status()
            return
        except httpx.HTTPError as error:
            if time.monotonic() >= deadline:
                raise AssertionError("The isolated Mailpit server did not become ready") from error
            time.sleep(0.1)


def delivered_account_link(inbox_url, email, subject):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        response = httpx.get(inbox_url + "/api/v1/messages")
        response.raise_for_status()
        for message in response.json().get("messages", []):
            recipients = [item["Address"] for item in message["To"]]
            if email in recipients and message["Subject"] == subject:
                full = httpx.get(inbox_url + "/api/v1/message/" + message["ID"]).json()
                return re.search(r"https?://\S+#token=\S+", full["Text"]).group()
        time.sleep(0.1)
    raise AssertionError("Account email was not delivered to the isolated test inbox")
