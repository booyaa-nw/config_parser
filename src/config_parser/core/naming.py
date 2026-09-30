# core/naming.py
#
# Excel(core/excel/writer.py)とJSON(core/json_export.py)の両出力で
# 共通して使う出力ファイルのベース名(hostname_version_タイムスタンプ)を
# 1箇所にまとめる。core/pipeline.pyが1回だけ呼び出し、同じbase_nameを
# 両方の出力層に渡すことで、同一実行のExcel/JSONファイルが名前で
# 対応付けられるようにする(2026-09-26追加、CLI実装に伴う共通化)。
from __future__ import annotations

from datetime import datetime

from .doc_access import get_hostname


def make_export_base_name(doc: dict) -> str:
    """旧ExcelWriter._book_name()相当。マイクロ秒まで含めることで、
    同一hostname/versionのファイルを短時間に複数export(バッチ処理等)
    しても衝突しにくくしている(最終防御は各出力層の一意化処理側)。"""
    header = doc.get("header", {})
    hostname = get_hostname(doc)
    version = header.get("version", "unknown")
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    return f"{hostname}_{version}_{timestamp}"
