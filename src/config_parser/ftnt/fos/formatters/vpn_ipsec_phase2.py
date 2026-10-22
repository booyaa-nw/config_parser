# ftnt/fos/formatters/vpn_ipsec_phase2.py
#
# vpn_ipsec_phase1.pyと対で新規実装(2026-10-22、こうぢさんより
# `fg_config_parser/vpn_ipsec_parser.py`を参考にipsecvpn追加の依頼)。
# 背景・経緯の詳細はvpn_ipsec_phase1.pyのヘッダコメントを参照。
#
# `phase1name`列でどのphase1トンネル(vpn_ipsec_phase1.pyの`name`)に
# 対応するかを突合せできるようにしている(1シートに合成はせず、
# firewall_vip/vipgrpと同様の「別シート+キーで関連付け」方式)。
#
# **src/dstの派生ロジック(firewall_addressのaddress集約と同じ考え方)**:
# FortiOSの`phase2-interface`は`src-addr-type`/`dst-addr-type`の値に応じて
# 実際の値を持つ生キーが変わる(`name`なら`src-name`、`subnet`なら
# `src-subnet`<ip> <mask>の2値、等)。表示列はtype列とは別に、実際の
# アドレスを1列にまとめた`src`/`dst`を用意し、型に応じてどちらを見るかを
# build_record側で振り分ける。
#
# **実データ検証(2026-10-22)**: 実サンプル2件(`FG_7.6_config01[_vdom].conf`、
# どちらも`src-addr-type`/`dst-addr-type`は`name`型)。**`subnet`型の分岐は
# 実サンプルに該当データが無く未検証**(FortiOSの一般的な仕様に基づく
# 実装)。`range`/`ip`等、他のaddr-type分岐は今回未対応(該当サンプルが
# 無いため。該当データが手に入れば firewall_address の _derive_address() と
# 同様の形で追加できる)。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class VpnIpsecPhase2(CategoryFormatter):
    field_names = {
        "__layout__":    {"layout": "simple", "sheetname": "ipsec_phase2", "global": False},
        "name":          {"width": 25, "default_value": []},
        "phase1name":    {"width": 25, "default_value": []},
        "proposal":      {"width": 35, "default_value": []},
        "dhgrp":         {"width": 15, "default_value": ["14"]},
        "src-addr-type": {"width": 10, "default_value": ["subnet"]},
        "src":           {"width": 25, "default_value": []},
        "dst-addr-type": {"width": 10, "default_value": ["subnet"]},
        "dst":           {"width": 25, "default_value": []},
        "comments":      {"width": 35, "default_value": []},
    }

    # 生コンフィグ側にしか存在しない、派生計算専用のキー(表示列ではないのでfield_namesには入れない)
    _raw_defaults = {
        "src-name": [], "dst-name": [],
        "src-subnet": ["0.0.0.0", "0.0.0.0"], "dst-subnet": ["0.0.0.0", "0.0.0.0"],
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("vpn_ipsec_phase2-interface", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_name])
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        record["src"] = self._derive_addr(tmp_line["src-addr-type"], tmp_line, "src")
        record["dst"] = self._derive_addr(tmp_line["dst-addr-type"], tmp_line, "dst")
        return record

    @staticmethod
    def _derive_addr(addr_type: list[str], tmp_line: dict, prefix: str) -> list[str]:
        """src-addr-type/dst-addr-typeの値に応じて、実際のアドレス値を
        持つ生キー(-name/-subnet等)から1つの表示フィールドへ集約する
        (firewall_address._derive_address()と同じ、1対1ではない変換)。"""
        t = addr_type[0] if addr_type else "subnet"
        if t == "name":
            return tmp_line[f"{prefix}-name"]
        if t == "subnet":
            # "subnet"型は未検証(実サンプルに該当データが無い)。
            return ["/".join(tmp_line[f"{prefix}-subnet"])]
        # range/ip等、他のaddr-typeは未対応(該当サンプルが無いため)。
        return []
