# core/json_export.py
#
# JSON出力層(2026-09-26新規、CLI実装に伴い追加)。core/excel/writer.pyの
# 「1 Formatter = 1シート」の原則を踏襲しつつ、こうぢさんの依頼
# 「マルチvdom時にファイル出力をbase+global, root, 各vdom単位」に対応する
# ため、Excelのように1ブックにまとめるのではなく、出力ファイル自体を
# スコープ(global / vdom名)単位で分割する。
#
# iter_vdom_names(doc)はnovdomの場合["root"]、multivdomの場合は宣言されて
# いる全vdom名を返すため、「global用ファイル1つ + vdom単位ファイル」という
# 同じ組み立て方でnovdom/multivdom両対応でき、特別分岐は不要。
from __future__ import annotations

import json
import re
from pathlib import Path

from .doc_access import iter_vdom_names

_INVALID_FILENAME_CHARS = re.compile(r'[:\\/?*\[\]<>|"]')


def export_json(doc: dict, formatters: list, out_dir: str, base_name: str) -> list[Path]:
    """formatters(CategoryFormatterのリスト)をscope(global/vdom名)単位で
    JSONファイルに書き出す。戻り値は実際に書き出したファイルパスのリスト
    (該当レコードが1件も無いスコープのファイルは作らない、Excel出力の
    「空カテゴリはシートを作らない」方針と揃えている)。
    """
    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    global_formatters = [f for f in formatters if f.resolve_field_names(doc)["__layout__"].get("global", False)]
    vdom_formatters = [f for f in formatters if f not in global_formatters]

    written: list[Path] = []

    global_categories = _collect_categories(doc, global_formatters, "global")
    if global_categories:
        written.append(_write_scope_file(out_dir_path, base_name, "global", doc, global_categories))

    for vdom_name in iter_vdom_names(doc):
        categories = _collect_categories(doc, vdom_formatters, vdom_name)
        if categories:
            written.append(_write_scope_file(out_dir_path, base_name, vdom_name, doc, categories))

    return written


def _collect_categories(doc: dict, formatters: list, vdom_name: str) -> dict:
    """{sheetname: {"field_names": ..., "records": [...]}} の形にまとめる。
    sheetnameをキーにしているのはExcel出力(core/excel/writer.py)と同じ命名を
    使うことで、将来Webview化する際にも両出力の対応関係が分かりやすいように
    するため。field_namesも併せて含めているのは、他スクリプトや将来のWeb画面
    が列定義(幅・デフォルト値・レイアウト種別)を読み取れるようにするため。
    """
    categories = {}
    for formatter in formatters:
        records, field_names = formatter.format(doc, vdom_name)
        if not records:
            continue
        sheetname = field_names["__layout__"]["sheetname"]
        categories[sheetname] = {
            "field_names": field_names,
            "records": records,
        }
    return categories


def _write_scope_file(out_dir: Path, base_name: str, scope: str, doc: dict, categories: dict) -> Path:
    safe_scope = _INVALID_FILENAME_CHARS.sub("_", scope)
    path = out_dir / f"{base_name}_{safe_scope}.json"
    payload = {
        "header": doc.get("header", {}),
        "scope": scope,
        "categories": categories,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
