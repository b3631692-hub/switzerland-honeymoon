"""Gmail API 操作的薄包裝層."""

from __future__ import annotations

import base64
from collections.abc import Iterator
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError


class GmailClient:
    """常用 Gmail 操作的包裝, 處理分頁、批次、錯誤."""

    def __init__(self, service: Resource, user_id: str = "me") -> None:
        self.service = service
        self.user_id = user_id

    def search_message_ids(self, query: str, max_results: int | None = None) -> Iterator[str]:
        """搜尋符合 Gmail query 的所有訊息 ID, 處理分頁."""
        page_token: str | None = None
        yielded = 0
        while True:
            request = self.service.users().messages().list(
                userId=self.user_id,
                q=query,
                pageToken=page_token,
                maxResults=500,
            )
            response = request.execute()
            for msg in response.get("messages", []):
                yield msg["id"]
                yielded += 1
                if max_results is not None and yielded >= max_results:
                    return
            page_token = response.get("nextPageToken")
            if not page_token:
                return

    def get_message(self, message_id: str, fmt: str = "metadata", headers: list[str] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "userId": self.user_id,
            "id": message_id,
            "format": fmt,
        }
        if headers:
            params["metadataHeaders"] = headers
        return self.service.users().messages().get(**params).execute()

    def get_message_full(self, message_id: str) -> dict[str, Any]:
        return self.get_message(message_id, fmt="full")

    def batch_modify(
        self,
        message_ids: list[str],
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> None:
        """批次加上/移除 label. Gmail API 一次最多 1000 封."""
        for chunk in _chunks(message_ids, 1000):
            body: dict[str, Any] = {"ids": chunk}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels
            self.service.users().messages().batchModify(
                userId=self.user_id, body=body
            ).execute()

    def trash(self, message_ids: list[str]) -> None:
        """把訊息丟到垃圾桶 (30 天後自動永久刪除, 期間可救回)."""
        for mid in message_ids:
            try:
                self.service.users().messages().trash(
                    userId=self.user_id, id=mid
                ).execute()
            except HttpError as exc:
                # 已經被刪、權限問題, 印出來但繼續處理其他信
                print(f"  ! 無法 trash {mid}: {exc}")

    def delete_permanently(self, message_ids: list[str]) -> None:
        """永久刪除. 無法復原, 慎用."""
        for mid in message_ids:
            try:
                self.service.users().messages().delete(
                    userId=self.user_id, id=mid
                ).execute()
            except HttpError as exc:
                print(f"  ! 無法 delete {mid}: {exc}")

    def list_labels(self) -> dict[str, str]:
        """回傳 {label_name: label_id} 字典."""
        response = self.service.users().labels().list(userId=self.user_id).execute()
        return {lbl["name"]: lbl["id"] for lbl in response.get("labels", [])}

    def ensure_label(self, name: str) -> str:
        """取得 label id, 不存在就建立. 支援巢狀格式 'Parent/Child'."""
        labels = self.list_labels()
        if name in labels:
            return labels[name]
        created = self.service.users().labels().create(
            userId=self.user_id,
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        ).execute()
        return created["id"]

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        response = self.service.users().messages().attachments().get(
            userId=self.user_id, messageId=message_id, id=attachment_id
        ).execute()
        return base64.urlsafe_b64decode(response["data"])


def _chunks(items: list, size: int) -> Iterator[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def header_value(message: dict[str, Any], name: str) -> str:
    """從 message metadata 取出指定 header."""
    headers = message.get("payload", {}).get("headers", [])
    target = name.lower()
    for h in headers:
        if h.get("name", "").lower() == target:
            return h.get("value", "")
    return ""
