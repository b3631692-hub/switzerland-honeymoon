"""自動歸檔廣告信."""

from __future__ import annotations

from typing import Any

from .gmail_client import GmailClient, header_value


def build_query(config: dict[str, Any]) -> str:
    """組出 Gmail 搜尋字串."""
    clauses: list[str] = ["in:inbox"]

    older_than = config.get("older_than_days", 3)
    if older_than > 0:
        clauses.append(f"older_than:{older_than}d")

    or_parts: list[str] = []
    if config.get("use_category_promotions", True):
        or_parts.append("category:promotions")

    for kw in config.get("extra_keywords", []):
        # 主旨或寄件人含關鍵字
        or_parts.append(f'(subject:"{kw}" OR from:"{kw}")')

    if or_parts:
        clauses.append("(" + " OR ".join(or_parts) + ")")

    return " ".join(clauses)


def run(
    client: GmailClient,
    config: dict[str, Any],
    dry_run: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    """執行歸檔. 回傳 {'matched': n, 'archived': n}."""
    query = build_query(config)
    print(f"搜尋條件: {query}")

    message_ids = list(client.search_message_ids(query, max_results=limit))
    print(f"找到 {len(message_ids)} 封符合條件")

    if not message_ids:
        return {"matched": 0, "archived": 0}

    # 印出前 10 封讓使用者確認長相
    print("\n前 10 封預覽:")
    for mid in message_ids[:10]:
        msg = client.get_message(mid, headers=["From", "Subject", "Date"])
        print(
            f"  - [{header_value(msg, 'Date')[:25]}] "
            f"{header_value(msg, 'From')[:40]} | "
            f"{header_value(msg, 'Subject')[:50]}"
        )
    if len(message_ids) > 10:
        print(f"  ... 還有 {len(message_ids) - 10} 封")

    if dry_run:
        print("\n[dry-run] 不會實際歸檔. 加上 --apply 才會執行.")
        return {"matched": len(message_ids), "archived": 0}

    remove_labels = ["INBOX"]
    if config.get("mark_as_read", True):
        remove_labels.append("UNREAD")

    print(f"\n歸檔中 (移除 labels: {remove_labels})...")
    client.batch_modify(message_ids, remove_labels=remove_labels)
    print(f"完成: {len(message_ids)} 封已歸檔")

    return {"matched": len(message_ids), "archived": len(message_ids)}
