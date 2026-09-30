# core/formatter_base.py
#
# architecture/config-parser-design.md (Claude Project) 決定事項2の実装。
# Formatterには正規化済みのコンフィグ全体(header含む)を渡し、
# Formatter側で自分のカテゴリを取り出し・バージョン差分を吸収する。
from __future__ import annotations

from copy import deepcopy


class CategoryFormatter:
    """1カテゴリ = 1 Excelシート = (将来) 1 Web画面、に対応するFormatterの基底クラス。"""

    field_names: dict = {}            # サブクラスで定義(__layout__を含む)
    field_names_overrides: list = []  # [(条件関数, 上書きfield_names差分dict), ...] バージョン/モデル差分用

    def resolve_field_names(self, doc: dict) -> dict:
        """headerのversion/modelを見て、field_namesにバージョン差分をマージした最終版を返す。"""
        header = doc.get("header", {})
        resolved = deepcopy(self.field_names)
        for condition, override in self.field_names_overrides:
            if condition(header):
                for key, patch in override.items():
                    resolved.setdefault(key, {}).update(patch)
        return resolved

    def format(self, doc: dict, vdom_name: str) -> tuple[list[dict], dict]:
        """doc: header/global/vdomを含む正規化済みの設定全体。
        戻り値は (レコードのリスト, 解決済みfield_names) のタプル
        (Excel/Web両方の出力層がそのまま使える形)。
        通常サブクラスはこのメソッドをオーバーライドせず、
        extract_records() と build_record() だけを実装する。
        """
        field_names = self.resolve_field_names(doc)
        raw_records = self.extract_records(doc, vdom_name)
        records = [self.build_record(r, field_names) for r in raw_records]
        return records, field_names

    def extract_records(self, doc: dict, vdom_name: str) -> list:
        """docから自分のカテゴリに該当する生レコード列を取り出す。サブクラスで実装。"""
        raise NotImplementedError

    def build_record(self, raw_obj, field_names: dict) -> dict:
        """1レコード分の生dictを、field_namesのdefault_valueで補完し、
        必要な派生ロジック(アドレスタイプ分岐など)を適用してフラットな表示用dictにする。
        サブクラスで実装。"""
        raise NotImplementedError

    @staticmethod
    def apply_defaults(raw_obj: dict, field_names: dict) -> dict:
        """field_namesのdefault_valueを使って一括でsetdefaultする共通ヘルパー。
        表示フィールドの単純なデフォルト補完はこれで済ませ、
        build_record内では派生ロジック(1対1でない変換)だけを書く。"""
        obj = deepcopy(raw_obj)
        for key, meta in field_names.items():
            if key == "__layout__":
                continue
            obj.setdefault(key, meta.get("default_value", []))
        return obj


def version_lt(v: str):
    """field_names_overridesの条件関数の例: headerのversionが指定バージョン未満かどうか。"""

    def _cond(header: dict) -> bool:
        cur = tuple(int(x) for x in header["version"].split("."))
        target = tuple(int(x) for x in v.split("."))
        return cur < target

    return _cond
