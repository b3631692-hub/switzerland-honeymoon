"""清理長時間沒互動的老舊未讀信."""

from __future__ import annotations

from typing import Any

from .gmail_client import GmailClient, header_value


def build_query(config: dict[str, Any]) -> str:
    clauses: list[str] = []

    older_than = config.get("older_than_days", 365)
    clauses.append(f"older_than:{older_than}d")

    if config.get("unread_only", True):
        clauses.append("is:unread")

    # 不碰垃圾桶和草稿
    clauses.append("-in:trash")
    clauses.append("-in:drafts")
    clauses.append("-in:sent")

    # 排除重要 label
    for lbl in config.get("exclude_labels", []):
        clauses.append(f"-label:{lbl}")

    # 排除特定寄件人
    for sender in config.get("exclude_senders", []):
        clauses.append(f'-from:"{sender}"')

    # 排除有加星標的
    clauses.append("-is:starred")

    return " ".join(clauses)


def run(
    client: GmailClient,
    config: dict[str, Any],
    dry_run: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    query = build_query(config)
    print(f"搜尋條件: {query}")

    message_ids = list(client.search_message_ids(query, max_results=limit))
    print(f"找到 {len(message_ids)} 封符合條件")

    if not message_ids:
        return {"matched": 0, "removed": 0}

    # 用寄件人聚合一下，方便看是哪些來源在塞信箱
    sender_count: dict[str, int] = {}
    sample_ids = message_ids[:200]  # metadata 抓 200 封統計就好
    for mid in sample_ids:
        msg = client.get_message(mid, headers=["From"])
        sender = header_value(msg, "From")
        # 只取 email 的 domain 部分
        if "@" in sender:
            domain = sender.split("@")[-1].rstrip(">").strip()
        else:
            domain = sender
        sender_count[domain] = sender_count.get(domain, 0) + 1

    print(f"\n寄件人 domain 統計 (前 {len(sample_ids)} 封樣本):")
    top = sorted(sender_count.items(), key=lambda x: -x[1])[:15]
    for domain, count in top:
        print(f"  {count:>5}  {domain}")

    action = config.get("action", "trash")
    if dry_run:
        print(f"\n[dry-run] 不會實際 {action}. 加上 --apply 才會執行.")
        return {"matched": len(message_ids), "removed": 0}

    print(f"\n執行 {action}...")
    if action == "delete":
        client.delete_permanently(message_ids)
    else:
        client.trash(message_ids)
    print(f"完成: {len(message_ids)} 封已 {action}")

    return {"matched": len(message_ids), "removed": len(message_ids)}
