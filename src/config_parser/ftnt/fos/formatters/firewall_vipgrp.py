# ftnt/fos/formatters/firewall_vipgrp.py
#
# 新規実装(2026-09-26)。実データは7.2_vdom/rootの2件のみ(interface/member/
# uuidキーを実際に使用)。comment/colorは実サンプルには出現しなかったが、
# firewall_vipと同様にVIPグループにも存在する標準フィールドのため列として
# 残した。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallVipgrp(CategoryFormatter):
    field_names = {
        "__layout__": {"layout": "simple", "sheetname": "vip group", "global": False},
        "name":       {"width": 25, "default_value": []},
        "interface":  {"width": 15, "default_value": []},
        "member":     {"width": 30, "default_value": []},
        "color":      {"width": 8,  "default_value": ["0"]},
        "comment":    {"width": 30, "default_value": []},
        "uuid":       {"width": 38, "default_value": []},
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_vipgrp", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = self.apply_defaults(deepcopy(raw_obj[obj_name]), field_names)
        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        return record
