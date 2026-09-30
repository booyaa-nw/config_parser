# ftnt/fos/formatters/firewall_service_custom.py
#
# 新規実装(2026-09-26)。実データ4サンプル合計520件(FortiGuard標準サービス
# 定義+カスタムサービス。1サンプルあたり86〜88件)に対して実際に動かして
# 検証した。
#
# 実データにはunset由来のNone値(例: PINGの`icmpcode`、ALL_ICMPの
# `icmptype`)が含まれる。apply_defaults()のsetdefault()はキーが既に
# 存在する場合(値がNoneでも)上書きしないため、Noneはそのまま各列に残る。
# style.cell_text()がNoneを空文字列として描画するため、Excel上は
# 単に空欄になり実害はない。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallServiceCustom(CategoryFormatter):
    field_names = {
        "__layout__":      {"layout": "simple", "sheetname": "service custom", "global": False},
        "name":            {"width": 25, "default_value": []},
        "category":        {"width": 20, "default_value": ["General"]},
        "protocol":        {"width": 15, "default_value": ["TCP/UDP/SCTP"]},
        "protocol-number": {"width": 12, "default_value": []},
        "tcp-portrange":   {"width": 20, "default_value": []},
        "udp-portrange":   {"width": 20, "default_value": []},
        "sctp-portrange":  {"width": 20, "default_value": []},
        "icmptype":        {"width": 10, "default_value": []},
        "icmpcode":        {"width": 10, "default_value": []},
        "fqdn":            {"width": 25, "default_value": []},
        "proxy":           {"width": 10, "default_value": ["disable"]},
        "session-ttl":     {"width": 10, "default_value": ["0"]},
        "color":           {"width": 8,  "default_value": ["0"]},
        "comment":         {"width": 30, "default_value": []},
        "uuid":            {"width": 38, "default_value": []},
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_service_custom", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = self.apply_defaults(deepcopy(raw_obj[obj_name]), field_names)
        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        return record
