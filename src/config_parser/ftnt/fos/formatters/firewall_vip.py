# ftnt/fos/formatters/firewall_vip.py
#
# 新規実装(2026-09-26)。実データ4サンプル中、7.2_vdom/root(5件)・
# 7.6_novdom/root(2件)・7.6_vdom/root(3件)・7.6_vdom/ext-vdom(1件)の
# 計11件に対して実際に動かして検証した。
#
# VIPはstatic-nat(extip/mappedip)・port forwarding(portforward enable +
# extport/mappedport/portmapping-type)・FQDN参照(type fqdn、extaddr/
# mapped-addrでfirewall_address名を参照)の3系統が実データに混在している。
# firewall_addressの`address`のような1列への集約は行わず、実コンフィグの
# キーをそのまま個別の列として残した(extip/extaddr、mappedip/mapped-addr
# はどちらか一方だけが実際に使われるが、集約ルールを恣意的に決めるより
# 生データをそのまま見せる方が誤解が少ないと判断)。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallVip(CategoryFormatter):
    field_names = {
        "__layout__":       {"layout": "simple", "sheetname": "vip", "global": False},
        "name":             {"width": 25, "default_value": []},
        "vip-id":           {"width": 8,  "default_value": []},
        "type":             {"width": 12, "default_value": ["static-nat"]},
        "extintf":          {"width": 12, "default_value": ["any"]},
        "extip":            {"width": 20, "default_value": []},
        "extaddr":          {"width": 20, "default_value": []},
        "mappedip":         {"width": 20, "default_value": []},
        "mapped-addr":      {"width": 20, "default_value": []},
        "portforward":      {"width": 12, "default_value": ["disable"]},
        "extport":          {"width": 14, "default_value": []},
        "mappedport":       {"width": 14, "default_value": []},
        "portmapping-type": {"width": 15, "default_value": ["1-to-1"]},
        "src-filter":       {"width": 25, "default_value": []},
        "srcintf-filter":   {"width": 15, "default_value": []},
        "service":          {"width": 20, "default_value": []},
        "color":            {"width": 8,  "default_value": ["0"]},
        "comment":          {"width": 30, "default_value": []},
        "uuid":             {"width": 38, "default_value": []},
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_vip", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = self.apply_defaults(deepcopy(raw_obj[obj_name]), field_names)
        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        return record
