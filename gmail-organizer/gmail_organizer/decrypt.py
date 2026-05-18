"""批次解密下載下來的信用卡帳單 PDF.

使用 pikepdf (qpdf 的 Python 包裝). 依設定檔的密碼清單依序嘗試,
解開後寫到 output_dir, 維持原本的 年/銀行/ 目錄結構.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pikepdf


class DecryptResult:
    __slots__ = ("path", "status", "password_index", "issuer", "error")

    def __init__(
        self,
        path: Path,
        status: str,
        password_index: int | None = None,
        issuer: str | None = None,
        error: str | None = None,
    ) -> None:
        self.path = path
        self.status = status  # 'decrypted' | 'not_encrypted' | 'no_password' | 'skipped' | 'error'
        self.password_index = password_index
        self.issuer = issuer
        self.error = error


def _candidate_passwords(
    issuer: str | None,
    global_passwords: list[str],
    per_issuer: dict[str, list[str]],
) -> list[str]:
    """產生這個檔案要試的密碼順序: 先 issuer 專屬, 再全域, 去重."""
    seen: set[str] = set()
    ordered: list[str] = []
    if issuer and per_issuer.get(issuer):
        for p in per_issuer[issuer]:
            if p not in seen:
                seen.add(p)
                ordered.append(p)
    for p in global_passwords:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def _walk_pdfs(root: Path) -> Iterable[Path]:
    for p in sorted(root.rglob("*.pdf")):
        if p.is_file():
            yield p


def _issuer_from_relpath(rel: Path) -> str | None:
    """statements/2024/cathaybk/xxx.pdf -> 'cathaybk'."""
    parts = rel.parts
    if len(parts) >= 2:
        return parts[1]  # parts[0] 是 year
    if len(parts) >= 1:
        return parts[0]
    return None


def _try_decrypt(
    src: Path,
    dst: Path,
    passwords: list[str],
    dry_run: bool,
) -> tuple[str, int | None, str | None]:
    """嘗試解密單一 PDF.

    Returns: (status, password_index, error_message)
    """
    # 先確認是不是加密的
    try:
        with pikepdf.open(str(src)) as pdf:
            if not pdf.is_encrypted:
                if dry_run:
                    return "not_encrypted", None, None
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                return "not_encrypted", None, None
    except pikepdf.PasswordError:
        # 確實是加密的, 繼續往下試密碼
        pass
    except Exception as exc:  # noqa: BLE001
        return "error", None, str(exc)

    for idx, pw in enumerate(passwords):
        try:
            with pikepdf.open(str(src), password=pw) as pdf:
                if dry_run:
                    return "decrypted", idx, None
                dst.parent.mkdir(parents=True, exist_ok=True)
                pdf.save(str(dst))
                return "decrypted", idx, None
        except pikepdf.PasswordError:
            continue
        except Exception as exc:  # noqa: BLE001
            return "error", None, str(exc)

    return "no_password", None, None


def run(
    config: dict[str, Any],
    dry_run: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    input_dir = Path(config.get("input_dir", "./statements"))
    output_dir = Path(config.get("output_dir", "./statements_decrypted"))
    global_passwords: list[str] = config.get("passwords") or []
    per_issuer: dict[str, list[str]] = config.get("per_issuer") or {}
    copy_on_failure: bool = config.get("copy_on_failure", False)

    if not input_dir.exists():
        raise FileNotFoundError(f"找不到 input_dir: {input_dir}")

    if not global_passwords and not per_issuer:
        raise ValueError(
            "config.decrypt 沒設任何密碼. 至少要在 passwords 或 per_issuer 提供一個."
        )

    pdfs = list(_walk_pdfs(input_dir))
    if limit:
        pdfs = pdfs[:limit]
    print(f"找到 {len(pdfs)} 個 PDF 檔案")

    results: list[DecryptResult] = []

    for i, src in enumerate(pdfs, 1):
        rel = src.relative_to(input_dir)
        dst = output_dir / rel
        issuer = _issuer_from_relpath(rel)
        candidates = _candidate_passwords(issuer, global_passwords, per_issuer)

        if dst.exists() and not dry_run:
            results.append(DecryptResult(rel, "skipped", issuer=issuer))
            continue

        status, pw_idx, err = _try_decrypt(src, dst, candidates, dry_run)
        result = DecryptResult(rel, status, password_index=pw_idx, issuer=issuer, error=err)
        results.append(result)

        marker = {
            "decrypted": "✓",
            "not_encrypted": "·",
            "no_password": "✗",
            "skipped": "-",
            "error": "!",
        }.get(status, "?")
        suffix = ""
        if status == "decrypted":
            suffix = f" (密碼 #{pw_idx + 1})"
        elif status == "error":
            suffix = f" ({err})"
        elif status == "no_password":
            suffix = f" (試過 {len(candidates)} 組密碼)"

        print(f"  [{i}/{len(pdfs)}] {marker} {rel}{suffix}")

        if status == "no_password" and copy_on_failure and not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    summary: dict[str, int] = {}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1

    print("\n統計:")
    labels = {
        "decrypted": "成功解密",
        "not_encrypted": "原本就沒加密",
        "no_password": "密碼都試過了還是不行",
        "skipped": "目標檔已存在, 跳過",
        "error": "讀取/寫入錯誤",
    }
    for key, label in labels.items():
        if summary.get(key):
            print(f"  {label}: {summary[key]}")

    # 列出解不開的, 方便手動處理
    failures = [r for r in results if r.status == "no_password"]
    if failures:
        print(f"\n以下 {len(failures)} 個檔案解不開, 請手動確認或補密碼到 config:")
        for r in failures[:20]:
            print(f"  - {r.path}  (issuer={r.issuer})")
        if len(failures) > 20:
            print(f"  ... 還有 {len(failures) - 20} 個")

    if dry_run:
        print("\n[dry-run] 沒有實際寫檔. 加上 --apply 才會輸出解密後的 PDF.")

    return {
        "total": len(pdfs),
        "decrypted": summary.get("decrypted", 0),
        "not_encrypted": summary.get("not_encrypted", 0),
        "no_password": summary.get("no_password", 0),
        "skipped": summary.get("skipped", 0),
        "error": summary.get("error", 0),
    }
