"""Gmail Organizer CLI 進入點."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import yaml

from . import archive, cleanup, decrypt, statements
from .auth import DEFAULT_CREDENTIALS_PATH, DEFAULT_TOKEN_PATH, get_service
from .gmail_client import GmailClient


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise click.ClickException(
            f"找不到 {path}. 從 config.example.yaml 複製一份過去並修改."
        )
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _make_client(credentials: Path, token: Path) -> GmailClient:
    service = get_service(credentials_path=credentials, token_path=token)
    return GmailClient(service)


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=Path("config.yaml"),
    show_default=True,
    help="設定檔路徑.",
)
@click.option(
    "--credentials",
    type=click.Path(path_type=Path),
    default=DEFAULT_CREDENTIALS_PATH,
    show_default=True,
    help="Google OAuth client 的 credentials.json.",
)
@click.option(
    "--token",
    type=click.Path(path_type=Path),
    default=DEFAULT_TOKEN_PATH,
    show_default=True,
    help="存放授權 token 的檔案 (第一次執行會自動產生).",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path, credentials: Path, token: Path) -> None:
    """Gmail 整理工具: 歸檔廣告、清理舊信、下載信用卡帳單."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["credentials"] = credentials
    ctx.obj["token"] = token


@cli.command("archive-promos")
@click.option("--apply", "apply_changes", is_flag=True, help="實際執行 (預設 dry-run).")
@click.option("--limit", type=int, default=None, help="最多處理幾封 (測試用).")
@click.pass_context
def archive_promos_cmd(ctx: click.Context, apply_changes: bool, limit: int | None) -> None:
    """自動歸檔促銷/廣告信."""
    config = _load_config(ctx.obj["config_path"]).get("archive_promos", {})
    client = _make_client(ctx.obj["credentials"], ctx.obj["token"])
    archive.run(client, config, dry_run=not apply_changes, limit=limit)


@cli.command("cleanup-old")
@click.option("--apply", "apply_changes", is_flag=True, help="實際執行 (預設 dry-run).")
@click.option("--limit", type=int, default=None, help="最多處理幾封 (測試用).")
@click.pass_context
def cleanup_old_cmd(ctx: click.Context, apply_changes: bool, limit: int | None) -> None:
    """把長時間沒互動的未讀信丟垃圾桶."""
    config = _load_config(ctx.obj["config_path"]).get("cleanup_old", {})
    client = _make_client(ctx.obj["credentials"], ctx.obj["token"])
    cleanup.run(client, config, dry_run=not apply_changes, limit=limit)


@cli.command("download-statements")
@click.option("--apply", "apply_changes", is_flag=True, help="實際執行 (預設 dry-run).")
@click.option("--limit", type=int, default=None, help="最多處理幾封 (測試用).")
@click.pass_context
def download_statements_cmd(
    ctx: click.Context, apply_changes: bool, limit: int | None
) -> None:
    """搜尋信用卡帳單信件, 下載 PDF 附件並建立索引 CSV."""
    config = _load_config(ctx.obj["config_path"]).get("statements", {})
    client = _make_client(ctx.obj["credentials"], ctx.obj["token"])
    statements.run(client, config, dry_run=not apply_changes, limit=limit)


@cli.command("decrypt-statements")
@click.option("--apply", "apply_changes", is_flag=True, help="實際執行 (預設 dry-run).")
@click.option("--limit", type=int, default=None, help="最多處理幾個檔案 (測試用).")
@click.pass_context
def decrypt_statements_cmd(
    ctx: click.Context, apply_changes: bool, limit: int | None
) -> None:
    """批次解密下載下來的信用卡帳單 PDF (不需要 Gmail 授權)."""
    config = _load_config(ctx.obj["config_path"]).get("decrypt", {})
    decrypt.run(config, dry_run=not apply_changes, limit=limit)


@cli.command("auth")
@click.pass_context
def auth_cmd(ctx: click.Context) -> None:
    """測試授權: 打開瀏覽器走 OAuth 流程, 印出帳號資訊."""
    service = get_service(
        credentials_path=ctx.obj["credentials"], token_path=ctx.obj["token"]
    )
    profile = service.users().getProfile(userId="me").execute()
    click.echo(f"已授權: {profile['emailAddress']}")
    click.echo(f"信件總數: {profile['messagesTotal']}")
    click.echo(f"討論串總數: {profile['threadsTotal']}")


if __name__ == "__main__":
    cli()
