# ftnt/fos/formatters/firewall_policy.py
#
# 旧 formatter/firewall_policy.py の書き直し。実データ(7.2/7.6サンプル、
# 計25件のfirewall_policy)に対して実際に動かして検証した。
#
# 旧たたき台からの変更点(2026-09-25、実データ検証にて発覚・対応):
#   1. `id`列だけ他の列と違いlist([...])に包まれていなかった(horizontal
#      レンダラーはstr/listどちらでも表示できてしまうため実害は無かったが、
#      style.cell_text()の前提=「フィールド値は常にlist」から外れていたため
#      揃えた)。
#   2. `groups`/`users`(identity-basedポリシーのユーザー/グループ指定)が
#      旧field_namesに無く、実サンプルに2件存在した(7.6_novdomのid=4, id=10)
#      にもかかわらずExcel上から情報が欠落していた。新たに列として追加した。
#   3. srcaddr/dstaddrの「internet-service(-src)がenabledの場合は
#      internet-service(-src)-nameで上書きする」派生ロジックは、実データ
#      (7.2_multivdomのid=4: internet-service-srcのみenable、id=5: 両方
#      enable)で実際にsrcaddr/dstaddrキー自体が生コンフィグから消える
#      ケースを確認し、旧ロジックのまま維持した。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class FirewallPolicy(CategoryFormatter):
    field_names = {
        "__layout__":          {"layout": "simple", "sheetname": "policy", "global": False},
        "id":                  {"width": 7,  "default_value": []},
        "status":              {"width": 6,  "default_value": ["enable"]},
        "name":                {"width": 25, "default_value": []},
        "srcintf":             {"width": 15, "default_value": []},
        "dstintf":             {"width": 15, "default_value": []},
        "srcaddr":             {"width": 25, "default_value": []},
        "dstaddr":             {"width": 25, "default_value": []},
        "groups":              {"width": 20, "default_value": []},
        "users":               {"width": 20, "default_value": []},
        "schedule":            {"width": 8,  "default_value": []},
        "service":             {"width": 15, "default_value": []},
        "action":              {"width": 7,  "default_value": ["deny"]},
        "nat":                 {"width": 7,  "default_value": ["disable"]},
        "poolname":            {"width": 25, "default_value": []},
        "logtraffic":          {"width": 8,  "default_value": ["utm"]},
        "av-profile":          {"width": 15, "default_value": []},
        "webfilter-profile":   {"width": 15, "default_value": []},
        "dnsfilter-profile":   {"width": 15, "default_value": []},
        "emailfilter-profile": {"width": 15, "default_value": []},
        "dlp-sensor":          {"width": 15, "default_value": []},
        "ips-sensor":          {"width": 15, "default_value": []},
        "application-list":    {"width": 15, "default_value": []},
        "inspection-mode":     {"width": 15, "default_value": ["flow"]},
        "ssl-ssh-profile":     {"width": 15, "default_value": []},
        "comments":            {"width": 30, "default_value": []},
    }

    _raw_defaults = {
        "nat": ["disable"], "ippool": ["disable"], "poolname": [],
        "internet-service": ["disable"], "internet-service-name": [],
        "internet-service-src": ["disable"], "internet-service-src-name": [],
        "srcaddr": [], "dstaddr": [], "groups": [], "users": [],
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("firewall_policy", [])

    def build_record(self, raw_obj, field_names):
        obj_id = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_id])
        tmp_line.setdefault("name", [obj_id])
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        # internet-service(-src) が有効な場合、srcaddr/dstaddrは
        # コンフィグ上に現れず、代わりにinternet-service(-src)-nameが
        # 実質的なアドレス指定になる(1対1ではない変換の例)。
        if tmp_line["internet-service-src"] == ["enable"]:
            srcaddr = tmp_line["internet-service-src-name"]
        else:
            srcaddr = tmp_line["srcaddr"]

        if tmp_line["internet-service"] == ["enable"]:
            dstaddr = tmp_line["internet-service-name"]
        else:
            dstaddr = tmp_line["dstaddr"]

        return {
            "id": [obj_id],
            "status": tmp_line["status"],
            "name": tmp_line["name"],
            "srcintf": tmp_line["srcintf"],
            "dstintf": tmp_line["dstintf"],
            "srcaddr": srcaddr,
            "dstaddr": dstaddr,
            "groups": tmp_line["groups"],
            "users": tmp_line["users"],
            "schedule": tmp_line["schedule"],
            "service": tmp_line["service"],
            "action": tmp_line["action"],
            "nat": tmp_line["nat"],
            "poolname": tmp_line["poolname"],
            "logtraffic": tmp_line["logtraffic"],
            "av-profile": tmp_line["av-profile"],
            "webfilter-profile": tmp_line["webfilter-profile"],
            "dnsfilter-profile": tmp_line["dnsfilter-profile"],
            "emailfilter-profile": tmp_line["emailfilter-profile"],
            "dlp-sensor": tmp_line["dlp-sensor"],
            "ips-sensor": tmp_line["ips-sensor"],
            "application-list": tmp_line["application-list"],
            "inspection-mode": tmp_line["inspection-mode"],
            "ssl-ssh-profile": tmp_line["ssl-ssh-profile"],
            "comments": tmp_line["comments"],
        }
