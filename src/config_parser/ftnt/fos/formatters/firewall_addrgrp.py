# ftnt/fos/formatters/firewall_addrgrp.py
#
# 旧 formatter/firewall_addrgrp.py の書き直し。実データ(7.2/7.6サンプル、
# 計24件のfirewall_addrgrp)に対して実際に動かして検証した。
#
# 'virtical'レイアウト(フィールド=行、レコード=列)をfirewall_address同様の
# edit一覧カテゴリで検証する初のケース(system_haはsingletonカテゴリだった)。
#
# 旧たたき台からの変更点:
#   - `remark`列を削除: firewall_address同様、実サンプル全件grepしても
#     firewall addrgrpには一度も出現せず、実在しないフィールドだった。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallAddrgrp(CategoryFormatter):
    field_names = {
        "__layout__":     {
            "layout": "virtical", "sheetname": "address group", "global": False,
            "header_width": 20, "value_width": 25,
        },
        "name":           {"default_value": []},
        "type":           {"default_value": ["default"]},
        "member":         {"default_value": []},
        "exclude":        {"default_value": ["disable"]},
        "exclude-member": {"default_value": []},
        "allow-routing":  {"default_value": ["disable"]},
        "comment":        {"default_value": []},
    }

    _raw_defaults = {
        "type": ["default"], "member": [], "exclude": ["disable"],
        "exclude-member": [], "allow-routing": ["disable"], "comment": [],
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_addrgrp", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_name])
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        return {
            "name": [obj_name],
            "type": tmp_line["type"],
            "member": tmp_line["member"],
            "exclude": tmp_line["exclude"],
            "exclude-member": tmp_line["exclude-member"],
            "allow-routing": tmp_line["allow-routing"],
            "comment": tmp_line["comment"],
        }
