# core/pipeline.py
#
# 「1設定ファイルを読み込み、Excel/JSON出力まで一気通貫で行う」処理を、
# CLI(cli.py)からもライブラリとして直接importして使う側からも同じ関数で
# 呼べるようにする層(2026-09-26新規、こうぢさんの依頼「他のスクリプトから
# インポートできるようにしておく」への対応)。
#
# parse_fn/formattersを呼び出し側から渡す設計にしているのは、本モジュール
# 自体をベンダー/機種ファミリーに依存させないため(将来Alaxala等を追加する
# 際も、ftnt/fos側と同じ形でこの関数を再利用できる)。
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .doc_access import get_hostname
from .excel.writer import ExcelWriter
from .json_export import export_json
from .naming import make_export_base_name


@dataclass
class ProcessResult:
    """process_config_file()の戻り値。CLI側の結果表示にも、他スクリプトが
    importして使う場合にも、そのまま使える形にしてある。"""

    source_file: str
    hostname: str
    excel_path: Path | None = None
    json_paths: list[Path] = field(default_factory=list)


def process_config_file(
    file_path: str,
    formatters: list,
    parse_fn: Callable[[str], dict],
    export_dir: str = "./booyaa_log/export",
    json_output: bool = False,
    json_dir: str | None = None,
    json_only: bool = False,
) -> ProcessResult:
    """設定ファイル1件をparse_fn()で読み込み、formatters(CategoryFormatter
    のリスト)を使ってExcel/JSON出力する。

    - json_only=True の場合、Excel出力はスキップしJSONのみ出力する
      (--json は指定しなくてもJSON出力が有効になる)。
    - json_dir を省略した場合、JSONもexport_dirに出力する。
    - Excel/JSON共通のbase_name(hostname_version_タイムスタンプ)を
      1回だけ生成して両方の出力層に渡すことで、同一実行のファイル同士が
      名前で対応付けられるようにしている。
    """
    doc = parse_fn(file_path)
    base_name = make_export_base_name(doc)
    result = ProcessResult(source_file=str(file_path), hostname=get_hostname(doc))

    if not json_only:
        writer = ExcelWriter(formatters)
        result.excel_path = writer.export(doc, export_dir=export_dir, base_name=base_name)

    if json_output or json_only:
        result.json_paths = export_json(doc, formatters, json_dir or export_dir, base_name)

    return result
