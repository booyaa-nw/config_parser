# ftnt/fos/formatters/firewall_address.py
#
# architecture/config-parser-design.md 記載の書き直し例を、実データ
# (7.2/7.6サンプル、計 firewall_address 115件)に対して実際に動かして検証し、
# その過程で見つかった実データ特有のケースを反映した版。
#
# 設計メモのたたき台からの変更点(2026-09-25、実データ検証にて発覚):
#   1. `type: wildcard` の `address` が、生キーの2要素list(ip, mask)を
#      そのまま返していた(表示フィールドは1つに集約する方針のはずが、
#      wildcardだけ2要素のリストになってしまうバグ)。ipmask同様
#      "ip/mask" の1文字列に結合するよう修正。
#   2. `type: interface-subnet` が未対応だった(実サンプルに2件あり、
#      fall-throughでaddressが空になっていた)。ipmaskと同じ
#      subnet結合ロジックに合流させた。またこのtypeでは、bindされた
#      interfaceが(associated-interfaceではなく)生キー`interface`に
#      入っているため、`interface`表示列はこちらも見るようにした。
#   3. `type: dynamic` の`address`が常に`sub-type`固定になっていたが、
#      実データには次の3パターンがあることが分かった:
#        - sub-type=ems-tag: 値を持たない(EMSタグ名は本コンフィグ側には
#          出てこない)ので、従来通りsub-typeをそのまま表示する。
#        - sub-type=clearpass-spt: 実際の値は`clearpass-spt`キーに入る
#          (例: "healthy")。従来のままだと全行"clearpass-spt"表示に
#          なってしまい値が失われるため、値があればそちらを優先する。
#        - Fabricコネクタ経由(sub-typeキー自体が無く、`sdn`+`filter`を
#          持つ)のケース。従来ロジックだとaddressが空になっていたため、
#          sdn(+filter)を表示するようにした。
#   4. 設計メモのfield_namesにあった `remark` は、実サンプル全件を
#      grepしても一度も出現せず(`firewall address`に存在しないフィールド、
#      恐らく別カテゴリからの持ち越し)。実データに基づき削除した。
#   5. `cache-ttl` / `fabric-object` は実データでは常にデフォルト値のまま
#      (設定変更されたサンプルが無かった)。フィールド自体は
#      FortiOS上に実在するため残すが、常にdefault_value表示になる点は
#      留意。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallAddress(CategoryFormatter):
    field_names = {
        "__layout__":    {"layout": "simple", "sheetname": "address", "global": False},
        "name":          {"width": 35, "default_value": []},
        "interface":     {"width": 15, "default_value": []},
        "type":          {"width": 12, "default_value": ["ipmask"]},
        "address":       {"width": 35, "default_value": []},
        "allow-routing": {"width": 10, "default_value": ["disable"]},
        "comment":       {"width": 30, "default_value": []},
        "cache-ttl":     {"width": 8,  "default_value": ["0"]},
        "fabric-object": {"width": 10, "default_value": ["disable"]},
    }

    # 生コンフィグ側にしか存在しない、派生計算専用のキー(表示列ではないのでfield_namesには入れない)
    _raw_defaults = {
        "subnet": ["0.0.0.0", "0.0.0.0"],
        "start-ip": [], "end-ip": [], "fqdn": [], "wildcard": [],
        "country": [], "sub-type": [], "macaddr": [],
        "sdn": [], "filter": [], "clearpass-spt": [],
        "associated-interface": [], "interface": [],
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_address", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_name])
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        addr_type = tmp_line["type"][0] if tmp_line["type"] else "ipmask"
        address = self._derive_address(addr_type, tmp_line)
        interface = tmp_line["associated-interface"] or tmp_line["interface"]

        return {
            "name": obj_name,
            "interface": interface,
            "type": tmp_line["type"],
            "address": address,
            "allow-routing": tmp_line["allow-routing"],
            "comment": tmp_line["comment"],
            "cache-ttl": tmp_line["cache-ttl"],
            "fabric-object": tmp_line["fabric-object"],
        }

    @staticmethod
    def _derive_address(addr_type: str, tmp_line: dict) -> list[str]:
        """複数の生キー→1つの表示フィールド`address`への集約(1対1ではない変換)。"""
        if addr_type in ("ipmask", "interface-subnet"):
            return ["/".join(tmp_line["subnet"])]
        if addr_type == "iprange":
            return [f"{tmp_line['start-ip'][0]}-{tmp_line['end-ip'][0]}"]
        if addr_type == "fqdn":
            return tmp_line["fqdn"]
        if addr_type == "wildcard":
            return ["/".join(tmp_line["wildcard"])]
        if addr_type == "geography":
            return tmp_line["country"]
        if addr_type == "mac":
            return tmp_line["macaddr"]
        if addr_type == "dynamic":
            if tmp_line["sdn"]:
                sdn_addr = tmp_line["sdn"][0]
                if tmp_line["filter"]:
                    sdn_addr += f" ({tmp_line['filter'][0]})"
                return [sdn_addr]
            if tmp_line["sub-type"] == ["clearpass-spt"] and tmp_line["clearpass-spt"]:
                return tmp_line["clearpass-spt"]
            return tmp_line["sub-type"]
        return []
