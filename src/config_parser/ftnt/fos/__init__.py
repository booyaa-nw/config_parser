# ftnt/fos/__init__.py
#
# `from config_parser.ftnt.fos import process_file` の1行でFortiOS
# (FortiGate/MSW)設定ファイル1件のExcel/JSON変換を呼び出せるようにする
# ショートカット(2026-09-26追加、こうぢさんの依頼「他のスクリプトから
# インポートできるようにしておく」への対応)。cli.py自身もこの関数を使う。
from __future__ import annotations

from config_parser.core.pipeline import ProcessResult, process_config_file
from config_parser.ftnt.fos.formatters import FORMATTERS
from config_parser.ftnt.fos.parse import parse_config_file


def process_file(file_path: str, **kwargs) -> ProcessResult:
    """kwargsはcore.pipeline.process_config_file()にそのまま渡す
    (export_dir/json_output/json_dir/json_only)。"""
    return process_config_file(file_path, FORMATTERS, parse_config_file, **kwargs)
