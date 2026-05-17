"""信用卡帳單搜尋、下載 PDF 附件、整理 metadata."""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Any

from .gmail_client import GmailClient, header_value


def build_query(config: dict[str, Any]) -> str:
    clauses: list[str] = ["has:attachment"]

    lookback = config.get("lookback_days", 730)
    clauses.append(f"newer_than:{lookback}d")

    # 寄件人 OR 主旨關鍵字 都接受
    or_parts: list[str] = []
    for domain in config.get("issuer_domains", []):
        or_parts.append(f"from:{domain}")
    for kw in config.get("subject_keywords", []):
        or_parts.append(f'subject:"{kw}"')

    if or_parts:
        clauses.append("(" + " OR ".join(or_parts) + ")")

    return " ".join(clauses)


def _iter_pdf_attachments(payload: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """走過 payload 樹, 產出 (filename, attachment_id) 給每個 PDF 附件."""
    filename = payload.get("filename", "") or ""
    mime = payload.get("mimeType", "") or ""
    body = payload.get("body", {}) or {}
    attachment_id = body.get("attachmentId")

    is_pdf = (
        attachment_id
        and (
            mime == "application/pdf"
            or filename.lower().endswith(".pdf")
        )
    )
    if is_pdf:
        yield filename or "attachment.pdf", attachment_id

    for part in payload.get("parts", []) or []:
        yield from _iter_pdf_attachments(part)


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\-.一-鿿]+", "_", name)
    return name.strip("_") or "attachment"


def _issuer_from_sender(from_header: str, known_domains: list[str]) -> str:
    _, addr = parseaddr(from_header)
    if "@" not in addr:
        return "unknown"
    domain = addr.split("@")[-1].lower()
    # 嘗試對應 known_domains 找出最具識別性的 domain
    for known in known_domains:
        if known in domain:
            return known.split(".")[0]
    return domain.split(".")[0]


def run(
    client: GmailClient,
    config: dict[str, Any],
    dry_run: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    query = build_query(config)
    print(f"搜尋條件: {query}")

    message_ids = list(client.search_message_ids(query, max_results=limit))
    print(f"找到 {len(message_ids)} 封可能是帳單的信件")

    if not message_ids:
        return {"matched": 0, "downloaded": 0}

    output_dir = Path(config.get("output_dir", "./statements"))
    issuer_domains = config.get("issuer_domains", [])

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    label_id: str | None = None
    apply_label = config.get("apply_label")
    if apply_label and not dry_run:
        label_id = client.ensure_label(apply_label)

    index_rows: list[dict[str, str]] = []
    downloaded = 0
    skipped_existing = 0
    no_pdf = 0
    labeled_ids: list[str] = []

    for idx, mid in enumerate(message_ids, 1):
        msg = client.get_message_full(mid)
        from_h = header_value(msg, "From")
        subject = header_value(msg, "Subject")
        date_h = header_value(msg, "Date")

        try:
            mail_dt = parsedate_to_datetime(date_h) if date_h else None
        except (TypeError, ValueError):
            mail_dt = None
        date_str = mail_dt.strftime("%Y-%m-%d") if mail_dt else "unknown-date"
        year = mail_dt.strftime("%Y") if mail_dt else "unknown"

        issuer = _issuer_from_sender(from_h, issuer_domains)
        pdfs = list(_iter_pdf_attachments(msg.get("payload", {})))

        if not pdfs:
            no_pdf += 1
            print(f"  [{idx}/{len(message_ids)}] (無 PDF 附件) {issuer} | {subject[:50]}")
            continue

        for original_name, att_id in pdfs:
            safe = _safe_filename(original_name)
            target_dir = output_dir / year / issuer
            target_path = target_dir / f"{date_str}_{safe}"

            row = {
                "date": date_str,
                "issuer": issuer,
                "from": from_h,
                "subject": subject,
                "filename": str(target_path.relative_to(output_dir)) if not dry_run else f"{year}/{issuer}/{date_str}_{safe}",
                "message_id": mid,
            }
            index_rows.append(row)

            if dry_run:
                print(f"  [{idx}/{len(message_ids)}] (dry-run) {row['filename']}")
                continue

            if target_path.exists():
                skipped_existing += 1
                continue

            data = client.get_attachment(mid, att_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)
            downloaded += 1
            print(f"  [{idx}/{len(message_ids)}] 下載 -> {target_path.relative_to(output_dir)}")

        if label_id and not dry_run:
            labeled_ids.append(mid)

    if labeled_ids:
        client.batch_modify(labeled_ids, add_labels=[label_id])

    # 寫一份索引 CSV 方便後續分析
    if index_rows and not dry_run:
        index_path = output_dir / "index.csv"
        write_header = not index_path.exists()
        with index_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["date", "issuer", "from", "subject", "filename", "message_id"],
            )
            if write_header:
                writer.writeheader()
            writer.writerows(index_rows)
        print(f"\n索引已更新: {index_path}")

    print(
        f"\n統計: 下載 {downloaded} / 跳過已存在 {skipped_existing} / "
        f"無 PDF {no_pdf} / 總信件 {len(message_ids)}"
    )

    if dry_run:
        print("\n[dry-run] 沒有實際下載. 確認名單沒問題後加上 --apply 執行.")

    return {
        "matched": len(message_ids),
        "downloaded": downloaded,
    }
