# ftnt/fos/formatters/firewall_ippool.py
#
# 新規実装(2026-09-26)。実データ4サンプル中、7.2_vdom/root(5件)・
# 7.6_novdom/root(4件)・7.6_vdom/root(4件)の計13件に対して実際に動かして
# 検証した(type: overload/one-to-one/fixed-port-range/port-block-allocation
# の4パターン全てが実データに存在)。
#
# field_names一覧は、architecture/config-parser-design.md 決定事項1で
# こうぢさんご自身から「目標形」として提示されたものをベースにしている。
# ただし`remark`列は、firewall_address/firewall_addrgrpと同じ経緯
# (実サンプル全件grepしても一度も出現しない、旧実装からの持ち越しとみられる
# 実在しないフィールド)のため、今回も削除した。`arp-intf`/
# `associated-interface`は実サンプルには出現しない(=常にdefault_value表示)が、
# 実在するフィールドとして残してある(cache-ttl/fabric-object等、他の
# Formatterでも同様の扱いの前例あり)。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallIppool(CategoryFormatter):
    field_names = {
        "__layout__":           {"layout": "simple", "sheetname": "ippool", "global": False},
        "name":                 {"width": 25, "default_value": []},
        "type":                 {"width": 20, "default_value": ["overload"]},
        "startip":              {"width": 16, "default_value": []},
        "endip":                {"width": 16, "default_value": []},
        "source-startip":       {"width": 16, "default_value": []},
        "source-endip":         {"width": 16, "default_value": []},
        "arp-reply":            {"width": 10, "default_value": ["enable"]},
        "arp-intf":             {"width": 15, "default_value": []},
        "associated-interface": {"width": 18, "default_value": []},
        "port-per-user":        {"width": 12, "default_value": []},
        "block-size":           {"width": 10, "default_value": []},
        "num-blocks-per-user":  {"width": 14, "default_value": []},
        "tcp-session-quota":    {"width": 14, "default_value": []},
        "udp-session-quota":    {"width": 14, "default_value": []},
        "icmp-session-quota":   {"width": 14, "default_value": []},
        "comment":              {"width": 30, "default_value": []},
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_ippool", [])

    def build_record(self, raw_obj, field_names):
        # 生キー(startip/endip/type等)は表示列名とすべて1対1で対応しており、
        # firewall_addressのような派生ロジックが不要なため、field_namesの
        # キー一覧をそのままapply_defaults→詰め替えするだけで済む。
        obj_name = next(iter(raw_obj))
        tmp_line = self.apply_defaults(deepcopy(raw_obj[obj_name]), field_names)
        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        return record
