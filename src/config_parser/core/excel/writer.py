# core/excel/writer.py
#
# 旧 export/excel.py の ExportExcel クラスの置き換え。
#
# 旧実装との最大の違い: export_book()は「あらかじめ全カテゴリ分
# 整形済みのformatted_config_obj」を丸ごと受け取り、category名を
# 直接見て分岐していた。新設計ではCategoryFormatterのリスト
# (=実装済みカテゴリの一覧、1ファイル=1シートの原則そのもの)を受け取り、
# 各Formatterに対してdoc全体を渡して呼び出す。
#
# これにより:
#   - 未実装カテゴリ(旧実装の `elif category == 'ipsec_vpn': continue`)は
#     formattersのリストに含めないだけで自動的にスキップされる、
#     export層側の特別扱いが不要になった。
#   - system_ha専用だったexport/ha.pyは、field_names側の
#     `{'subtable': {...}}` 宣言を読む汎用compositeレンダラーに
#     置き換わり(core/excel/layouts.py)、export層はsystem_haという
#     カテゴリ名を一切知らない。
from __future__ import annotations

import re
from pathlib import Path

from openpyxl import Workbook

from ..doc_access import iter_vdom_names
from ..naming import make_export_base_name
from . import style
from .font import set_japanese_font
from .layouts import render

_INVALID_SHEETNAME_CHARS = re.compile(r"[:\\/?*\[\]]")
_MAX_SHEETNAME_LEN = 31


class ExcelWriter:
    """formatters: CategoryFormatterインスタンスのリスト
    (通常は ftnt/fos/formatters/__init__.py の FORMATTERS のような、
    vendor/機種ファミリーごとの登録済み一覧をそのまま渡す)。
    """

    def __init__(self, formatters: list):
        self.formatters = formatters

    def export(self, doc: dict, export_dir: str = "./tmp/export", base_name: str | None = None) -> Path:
        """base_name: 未指定ならmake_export_base_name(doc)で生成する。
        core/pipeline.pyがExcel/JSON両出力で同じbase_nameを使い回すために
        指定できるようにしてある(2026-09-26追加、CLI実装に伴う変更)。"""
        export_dir_path = Path(export_dir)
        export_dir_path.mkdir(parents=True, exist_ok=True)
        is_multivdom = doc["header"]["vdom"] == 1

        wb = Workbook()
        wb.remove(wb.worksheets[0])
        used_sheetnames: set[str] = set()

        global_formatters = [f for f in self.formatters if f.resolve_field_names(doc)["__layout__"].get("global", False)]
        vdom_formatters = [f for f in self.formatters if f not in global_formatters]

        # global系(system_global/system_ha等、vdomに属さないカテゴリ)を先頭に
        # まとめて出す。vdom単位ではないので並び替えの対象外。
        for formatter in global_formatters:
            self._write_formatter_sheet(wb, doc, formatter, "global", used_sheetnames, is_multivdom)

        # 2026-09-26変更: シート順序をFormatter(カテゴリ)単位ではなく
        # vdom単位でグルーピングするよう変更(こうぢさんの依頼: "root address,
        # root address group, root ..., ext-vdom address, ext-vdom address
        # group, ext-vdom ..."のように、vdomごとにシートをまとめたい)。
        # 変更前はFormatter順を外側・vdomを内側にしていたため、
        # "root address, ext-vdom address, root address group, ..."のように
        # カテゴリ単位でインターリーブされていた。
        for vdom_name in iter_vdom_names(doc):
            for formatter in vdom_formatters:
                self._write_formatter_sheet(wb, doc, formatter, vdom_name, used_sheetnames, is_multivdom)

        if base_name is None:
            base_name = make_export_base_name(doc)
        book_path = self._unique_book_path(export_dir_path, base_name)
        wb.save(book_path)
        set_japanese_font(book_path)
        return book_path

    @staticmethod
    def _write_formatter_sheet(wb, doc, formatter, vdom_name, used_sheetnames, is_multivdom) -> None:
        records, field_names = formatter.format(doc, vdom_name)
        if not records:
            # 空カテゴリはシートを作らない。旧実装は全カテゴリ分無条件で
            # シートを作っていたが、実データだと未使用vdomで大量の空シートが
            # 発生するため変更した(要相談としてarchitecture/config-parser-
            # design.mdに明記)。
            return

        is_global = field_names["__layout__"].get("global", False)
        base_sheetname = field_names["__layout__"]["sheetname"]
        if is_global or not is_multivdom:
            label = base_sheetname
        else:
            label = f"{vdom_name} {base_sheetname}"
        sheetname = ExcelWriter._unique_sheetname(label, used_sheetnames)

        ws = wb.create_sheet(sheetname)
        style.write_sheet_title(ws, 1, 1, sheetname)
        render(ws, header_row=3, records=records, field_names=field_names)

    @staticmethod
    def _unique_book_path(export_dir: Path, base_name: str) -> Path:
        candidate = export_dir / f"{base_name}.xlsx"
        n = 2
        while candidate.exists():
            candidate = export_dir / f"{base_name}_{n}.xlsx"
            n += 1
        return candidate

    @staticmethod
    def _unique_sheetname(label: str, used: set[str]) -> str:
        """Excelのシート名制約(31文字以内・`:\\/?*[]`禁止)への対応。
        旧実装では `# 31文字オーバーの対処 @todo` のまま未対応だった箇所。
        31文字超過時は末尾を削り、切り詰めにより名前が衝突する場合は
        連番を付けて一意にする。"""
        name = _INVALID_SHEETNAME_CHARS.sub("_", label)[:_MAX_SHEETNAME_LEN]
        candidate = name
        n = 2
        while candidate in used:
            suffix = f"_{n}"
            candidate = name[: _MAX_SHEETNAME_LEN - len(suffix)] + suffix
            n += 1
        used.add(candidate)
        return candidate
