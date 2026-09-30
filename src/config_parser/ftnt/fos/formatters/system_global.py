# ftnt/fos/formatters/system_global.py
#
# 旧 formatter/global_config/system_global.py の書き直し。実データ4サンプル
# の system_global に対して実際に動かして検証した。system_ha同様の
# singletonカテゴリ(edit一覧ではない単一設定ブロック)で、'virtical'
# レイアウトをcompositeなしの単純なケースとして検証する。
#
# 旧たたき台からの変更点:
#   1. `'set admin-reset-button'` というキー名の誤字(先頭に"set "が
#      混入していた)を`'admin-reset-button'`に修正。
#   2. `alias`列を追加: 実サンプル4件全てに存在する実データ
#      (GUI上のホスト名エイリアス)だが旧field_namesに無かった。
#   3. 7.6系だけに存在する新しめの設定(`fortitoken-cloud-region`,
#      `gui-firmware-upgrade-warning`, `gui-theme`)は今回は見送り、
#      「未確定・要相談」としてdesign-parser-design.mdに記載
#      (バージョン差分をfield_namesにどう表現するかの実例候補)。
#   4. `timezone`の値の形式が7.2系(数値コード "60") と7.6系
#      (IANA名 "Asia/Tokyo") で異なることを実データで確認したが、
#      値をそのまま表示するだけなら変換は不要なため、当面は無変換で
#      表示する(将来field_names_overridesを使う実例候補として明記)。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_global_section
from config_parser.core.formatter_base import CategoryFormatter


class SystemGlobal(CategoryFormatter):
    field_names = {
        "__layout__": {
            "layout": "virtical", "sheetname": "global", "global": True,
            "header_width": 40, "value_width": 30,
        },
        "hostname":                                  {"default_value": []},
        "alias":                                      {"default_value": []},
        "management-vdom":                            {"default_value": ["root"]},
        "vdom-mode":                                   {"default_value": ["no-vdom"]},
        "timezone":                                    {"default_value": []},
        "virtual-switch-vlan":                         {"default_value": ["disable"]},
        "wireless-controller":                         {"default_value": ["enable"]},
        "switch-controller":                           {"default_value": ["disable"]},
        "gui-display-hostname":                        {"default_value": ["disable"]},
        "admin-scp":                                   {"default_value": ["disable"]},
        "admintimeout":                                {"default_value": ["5"]},
        "gui-auto-upgrade-setup-warning":              {"default_value": ["disable"]},
        "gui-forticare-registration-setup-warning":    {"default_value": ["enable"]},
        "admin-reset-button":                          {"default_value": ["enable"]},
        "daily-restart":                               {"default_value": ["disable"]},
        "restart-time":                                {"default_value": ["00:00:00"]},
    }

    def extract_records(self, doc, vdom_name):
        section = get_global_section(doc)
        sysg = section.get("system_global")
        return [sysg] if sysg else []

    def build_record(self, raw_obj, field_names):
        tmp_line = deepcopy(raw_obj)
        tmp_line = self.apply_defaults(tmp_line, field_names)
        return {k: tmp_line[k] for k in field_names if k != "__layout__"}
