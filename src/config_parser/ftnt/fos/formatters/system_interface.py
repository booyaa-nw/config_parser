# ftnt/fos/formatters/system_interface.py
#
# 新規実装(2026-10-02)。こうぢさんより「interfaceの実装を進めてください」
# という依頼を受けて対応。
#
# config_system_interfaceは他カテゴリと異なり、マルチvdom構成でも
# `config global`配下に1つのリストとしてまとまっており(vdomごとに
# 分かれていない)、各エントリ自身が持つ`vdom`キーでどのvdomに属するかを
# 示す(実サンプル4件で確認済み)。novdomの場合も各エントリに
# `set vdom "root"`が明示的に入っている。そのため、本Formatterは
# `__layout__.global = False`(vdom単位でシート分割する対象)としつつ、
# extract_records()は`get_global_section(doc)`から取得した全件リストを
# 自分で`vdom`キーによってvdom_nameにフィルタする、という他カテゴリには
# 無いパターンを取る(firewall_address等はget_vdom_sectionでvdom単位に
# 既に分かれたデータを取るだけなのに対し、system_interfaceはFormatter
# 自身がvdomによる絞り込みを担う)。
#
# サブネットマスク→CIDR変換は、決定事項10(design doc)で予告していた通り
# router_static.pyと同じ`common.iptools.calc.ipv4.dotted_mask_to_cidr()`を
# 使う。
#
# 実データ検証で判明した挙動(`validate_system_interface.py`参照):
#   - `type`が明示されないエントリが実サンプル中に複数存在するが、全て
#     `vlanid`+`interface`(親インタフェース)を持つ、switch-controller経由の
#     VLANサブインタフェース(FortiLink配下のVLAN、例: quarantine/voice等)
#     だった。FortiOSはこの構成の場合`type`を明示的に書き出さないため、
#     本Formatterでは「`type`未設定かつ`vlanid`設定あり」の場合に限り
#     表示上`vlan`を派生値として補う(firewall_addressの`address`集約と
#     同様、1対1ではない派生ロジック)。
#   - `ip`(IPv4アドレス+ネットマスク)が未設定のエントリ(DHCP/PPPoEや
#     IP未設定のポート)が多数あり、これをrouter_staticの`dst`のように
#     "0.0.0.0/0"をデフォルト表示にしてしまうと「IP未設定」と
#     「0.0.0.0/0が設定されている」の区別がつかなくなる。そのため`ip`は
#     値が実際に存在する場合のみ"ip/cidr"形式に変換し、無い場合は空表示
#     にする(router_staticの`dst`とは異なり、空をそのまま許容する設計)。
#   - `config ipv6`サブブロック(editを持たない単一dict)は今回スコープ外
#     とした。system_haの`ha-mgmt-interfaces`のような edit一覧のサブテーブル
#     (compositeレイアウト前提)とは構造が異なり単純に流用できないこと、
#     依頼内容がIPv4の疎通・設計確認を主眼としていると判断したことによる
#     (要すればフォローアップで追加検討)。
#   - いくつかのswitch-controller系トグル項目(`switch-controller-
#     igmp-snooping`等)は実サンプル中に有効化された状態でしか出現せず、
#     デフォルト値(disable)はFortiOSの一般的な仕様に基づく推測であり、
#     実データでの両方向(enable/disable)の確認はできていない点に留意。
from __future__ import annotations

from copy import deepcopy

from common.iptools.calc.ipv4 import dotted_mask_to_cidr
from config_parser.core.doc_access import get_global_section
from config_parser.core.formatter_base import CategoryFormatter


class SystemInterface(CategoryFormatter):
    field_names = {
        "__layout__":                        {"layout": "simple", "sheetname": "interface", "global": False},
        "name":                               {"width": 20, "default_value": []},
        "type":                               {"width": 12, "default_value": ["physical"]},
        "role":                               {"width": 8,  "default_value": []},
        "ip":                                 {"width": 20, "default_value": []},
        "mode":                               {"width": 10, "default_value": ["static"]},
        "status":                             {"width": 8,  "default_value": ["up"]},
        "allowaccess":                        {"width": 25, "default_value": []},
        "alias":                              {"width": 25, "default_value": []},
        "description":                        {"width": 30, "default_value": []},
        "interface":                          {"width": 15, "default_value": []},
        "vlanid":                             {"width": 8,  "default_value": []},
        "member":                             {"width": 25, "default_value": []},
        "device-identification":              {"width": 10, "default_value": ["disable"]},
        "security-mode":                      {"width": 15, "default_value": []},
        "src-check":                          {"width": 10, "default_value": ["enable"]},
        "fortilink":                          {"width": 10, "default_value": ["disable"]},
        "lldp-reception":                     {"width": 10, "default_value": []},
        "lldp-transmission":                  {"width": 10, "default_value": []},
        "switch-controller-feature":          {"width": 18, "default_value": []},
        "switch-controller-access-vlan":      {"width": 10, "default_value": ["disable"]},
        "switch-controller-nac":              {"width": 15, "default_value": []},
        "switch-controller-dynamic":          {"width": 15, "default_value": []},
        "switch-controller-traffic-policy":   {"width": 15, "default_value": []},
        "switch-controller-igmp-snooping":    {"width": 10, "default_value": ["disable"]},
        "switch-controller-dhcp-snooping":    {"width": 10, "default_value": ["disable"]},
        "replacemsg-override-group":          {"width": 20, "default_value": []},
        "ip-managed-by-fortiipam":            {"width": 10, "default_value": ["disable"]},
        "color":                              {"width": 6,  "default_value": ["0"]},
        "snmp-index":                         {"width": 8,  "default_value": []},
    }

    # 生コンフィグ側にしか存在しない、派生計算専用のキー
    # (表示列ではないのでfield_namesには入れない。"vdom"はvdomフィルタ専用)
    _raw_defaults = {
        "vdom": [], "ip": [], "type": [],
    }

    def extract_records(self, doc, vdom_name):
        # system_interfaceは他カテゴリと異なり`config global`配下に
        # 全vdom分がまとまっているため、自分でvdomキーによる絞り込みを行う。
        global_obj = get_global_section(doc)
        all_entries = global_obj.get("system_interface", [])
        result = []
        for entry in all_entries:
            name = next(iter(entry))
            entry_vdom = entry[name].get("vdom", ["root"])
            entry_vdom = entry_vdom[0] if entry_vdom else "root"
            if entry_vdom == vdom_name:
                result.append(entry)
        return result

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_name])
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        # type: 未設定かつvlanid設定ありの場合のみ'vlan'を派生表示
        # (switch-controller経由VLANサブインタフェース、上部コメント参照)。
        raw_type = tmp_line["type"]
        if raw_type:
            interface_type = raw_type
        elif tmp_line["vlanid"]:
            interface_type = ["vlan"]
        else:
            interface_type = ["physical"]

        # ip: 値が実在する場合のみ"ip/cidr"形式に変換。未設定(DHCP/PPPoE等)は
        # 空のまま(router_staticのdstと異なり"0.0.0.0/0"をデフォルト表示に
        # しない、上部コメント参照)。
        raw_ip = tmp_line["ip"]
        if raw_ip and len(raw_ip) == 2:
            ip_addr, ip_mask = raw_ip
            ip_display = [f"{ip_addr}/{dotted_mask_to_cidr(ip_mask)}"]
        else:
            ip_display = []

        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        record["type"] = interface_type
        record["ip"] = ip_display
        return record
