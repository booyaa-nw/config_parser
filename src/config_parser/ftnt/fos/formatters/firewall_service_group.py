# ftnt/fos/formatters/firewall_service_group.py
#
# 新規実装(2026-09-26)。実データ4サンプル合計24件(1サンプルあたり4件、
# 各サンプルで内容は同一のプリセットグループ: Email Access/Web Access/
# Windows AD/Exchange Server)に対して実際に動かして検証した。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallServiceGroup(CategoryFormatter):
    field_names = {
        "__layout__": {"layout": "simple", "sheetname": "service group", "global": False},
        "name":       {"width": 25, "default_value": []},
        "member":     {"width": 40, "default_value": []},
        "color":      {"width": 8,  "default_value": ["0"]},
        "comment":    {"width": 30, "default_value": []},
        "uuid":       {"width": 38, "default_value": []},
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_service_group", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = self.apply_defaults(deepcopy(raw_obj[obj_name]), field_names)
        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        return record
