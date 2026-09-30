# core/excel/layouts.py
#
# 旧実装(export/excel.py の export_book() 内if/elif + export/horizontal.py +
# export/virtical.py + export/ha.py)にあった「カテゴリ名 or レイアウト種別
# によるハードコードされた分岐」を、field_names['__layout__']['layout'] の
# 値をキーにした登録制(LAYOUT_RENDERERS)に置き換える。
#
# 各レンダラーの入力は、CategoryFormatter.format() の戻り値そのまま
# (records: list[dict]、field_names: __layout__を含む解決済み辞書)に統一し、
# vdom_name/category名や生のconfig_objには一切依存しない
# (= Formatterがどのカテゴリのものかexcel層は関知しない)。
#
# 新しいlayoutを追加したい場合は、レンダラー関数を書いて
# @register_layout('新しい名前') を付けるだけでよい。
from __future__ import annotations

from copy import deepcopy

from . import style

# ---------------------------------------------------------------------
# レイアウト名 -> レンダラー関数 の登録制レジストリ
# ---------------------------------------------------------------------
LAYOUT_RENDERERS: dict[str, "LayoutRenderer"] = {}


def register_layout(name: str):
    def _decorator(fn):
        LAYOUT_RENDERERS[name] = fn
        return fn
    return _decorator


def render(ws, header_row: int, records: list[dict], field_names: dict) -> int:
    """layoutを解決して該当レンダラーを呼ぶ共通エントリポイント。
    戻り値は書き込んだ最終行番号(次のブロックの開始行計算に使う)。
    """
    layout = field_names["__layout__"]["layout"]
    try:
        renderer = LAYOUT_RENDERERS[layout]
    except KeyError:
        raise ValueError(
            f"未登録のlayout種別です: {layout!r} "
            f"(登録済み: {sorted(LAYOUT_RENDERERS)})"
        )
    return renderer(ws, header_row, records, field_names)


def _display_fields(field_names: dict) -> list[str]:
    """__layout__と、compositeのsubtable指定フィールドを除いた、
    通常セルとして表示するフィールド名の並び。"""
    return [
        k for k, meta in field_names.items()
        if k != "__layout__" and "subtable" not in meta
    ]


# ---------------------------------------------------------------------
# simple: 汎用的な水平テーブル(1レコード=1行、フィールド=列)
# firewall_address / firewall_policy など、ほとんどのカテゴリで使う既定レイアウト。
# ---------------------------------------------------------------------
@register_layout("simple")
def render_horizontal(ws, header_row: int, records: list[dict], field_names: dict) -> int:
    fields = _display_fields(field_names)
    widths = {k: field_names[k].get("width") for k in fields}

    for col, field_name in enumerate(fields, start=1):
        style.write_header_cell(ws, header_row, col, field_name, widths[field_name])

    row = header_row
    for row, record in enumerate(records, start=header_row + 1):
        for col, field_name in enumerate(fields, start=1):
            value = record.get(field_name)
            style.write_cell(ws, row, col, style.cell_text(value))

    return row


# ---------------------------------------------------------------------
# virtical: フィールド=行、レコード=列(system_global等、フィールド数が多く
# レコード数が少ない=1〜数件のカテゴリ向け)。
# ---------------------------------------------------------------------
@register_layout("virtical")
def render_vertical(ws, header_row: int, records: list[dict], field_names: dict) -> int:
    fields = _display_fields(field_names)
    header_width = field_names["__layout__"].get("header_width")
    value_width = field_names["__layout__"].get("value_width")

    for r, field_name in enumerate(fields, start=header_row):
        style.write_header_cell(ws, r, 1, field_name, header_width)

    last_row = header_row + len(fields) - 1
    for col, record in enumerate(records, start=2):
        for r, field_name in enumerate(fields, start=header_row):
            value = record.get(field_name)
            style.write_cell(ws, r, col, style.cell_text(value), width=value_width)

    return last_row


# ---------------------------------------------------------------------
# composite: virticalのメインブロック + 1つ以上の「サブテーブル」フィールド
# (system_ha の ha-mgmt-interfaces など、1カテゴリの中に入れ子のedit一覧を
# 持つケース)。旧実装ではexport/ha.pyとしてsystem_ha専用に個別実装されて
# いたが、"どのフィールドがサブテーブルか"をfield_names側の宣言
# (`{'subtable': {'field_names': {...}}}`)に持たせることで、カテゴリ名を
# 一切知らない汎用レンダラーにした。
# ---------------------------------------------------------------------
@register_layout("composite")
def render_composite(ws, header_row: int, records: list[dict], field_names: dict) -> int:
    row = render_vertical(ws, header_row, records, field_names)

    subtable_fields = [
        (k, meta) for k, meta in field_names.items()
        if k != "__layout__" and "subtable" in meta
    ]

    for field_name, meta in subtable_fields:
        row += 2  # メインブロックとの間に1行空ける
        style.write_subtable_title(ws, row, 1, field_name)
        row += 1

        sub_field_names = deepcopy(meta["subtable"]["field_names"])
        sub_field_names["__layout__"] = {"layout": "simple"}

        # compositeカテゴリは(system_haのように)通常レコード数が0か1件だが、
        # 複数件の場合も一応サブテーブルを縦に連結して壊れないようにしておく。
        sub_records: list[dict] = []
        for record in records:
            sub_records.extend(record.get(field_name, []))

        row = render_horizontal(ws, row, sub_records, sub_field_names)

    return row
