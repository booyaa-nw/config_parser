# ftnt/fos/formatters/router_static.py
#
# 旧 formatter/router_static.py の書き直し。実データ4サンプル(計8件)に
# 対して実際に動かして検証した。
#
# 依存関係についての注意(2026-09-25更新): 旧実装(booyaa_old)は
# `booyaa.ipcalc.ipv4.IPv4.ipmask2cidr()`を使ってサブネットマスク→CIDR
# 変換を行っていたが、現行のbooyaaモノレポではこの処理は`tools/ipcalc`
# ではなく共通ライブラリ`tools/common`(`common.iptools.calc.ipv4`)に
# 移設済み(旧`booyaa.ipcalc`/`booyaa.common.iptools.py`からの移行、
# `operations/tool-registry.md`のcommon行を参照)。該当関数は
# `common.iptools.calc.ipv4.dotted_mask_to_cidr()`("255.255.255.0" -> 24)。
# 当初この検証用PoCには`_netmask_to_cidr()`という簡易自前実装を置いていたが、
# `tools/common`の実装(src/common/iptools/calc/ipv4.py 一式)をこのPoC環境に
# 取り込み、実際に`dotted_mask_to_cidr()`をそのまま使う形に差し替えて
# 動作を確認した(下記import・検証スクリプト参照)。**実際にtools/config_parser
# へ組み込む際は、`pyproject.toml`にuv workspace経由で`common`への依存
# (`[tool.uv.sources] common = { workspace = true }`)を追加し、このPoCと
# 同じ`from common.iptools.calc.ipv4 import dotted_mask_to_cidr`をそのまま
# 使えばよい(変換ロジックの二重管理を避けるため、自前実装への逆戻りはしない)。**
#
# 旧たたき台からの変更点(実データ検証にて発覚):
#   1. `id`列を他の列と同様list([...])で統一(firewall_policy同様の修正)。
#   2. `vrf`列を追加: 実サンプル(7.6_novdomのblackholeルート3件)に
#      実在したが旧field_namesに無かった。
#   3. `sdwan-zone`分岐は旧コードのまま維持したが、**4サンプル中どれにも
#      該当データが無く未検証**(要フォローアップとして明記)。
from __future__ import annotations

from copy import deepcopy

from common.iptools.calc.ipv4 import dotted_mask_to_cidr
from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class RouterStatic(CategoryFormatter):
    field_names = {
        "__layout__": {"layout": "simple", "sheetname": "router_static", "global": False},
        "id":         {"width": 5,  "default_value": []},
        "status":     {"width": 6,  "default_value": ["enable"]},
        "device":     {"width": 25, "default_value": []},
        "dst":        {"width": 20, "default_value": []},
        "gateway":    {"width": 20, "default_value": []},
        "distance":   {"width": 5,  "default_value": ["10"]},
        "priority":   {"width": 5,  "default_value": ["1"]},
        "vrf":        {"width": 5,  "default_value": ["0"]},
        "comment":    {"width": 30, "default_value": []},
    }

    _raw_defaults = {
        "status": ["enable"], "dst": ["0.0.0.0", "0.0.0.0"], "gateway": [],
        "distance": ["10"], "priority": ["1"], "blackhole": ["disable"],
        "vrf": ["0"], "comment": [], "device": [], "sdwan-zone": [],
    }

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("router_static", [])

    def build_record(self, raw_obj, field_names):
        obj_id = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_id])
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        # device: SD-WANゾーン指定 > blackhole > 通常の出力interface、の優先順位
        # (1対1ではない変換の例。旧コードのロジックを維持)
        gateway = tmp_line["gateway"]
        if tmp_line["sdwan-zone"]:
            device = tmp_line["sdwan-zone"]
        elif tmp_line["blackhole"] == ["enable"]:
            device = ["blackhole"]
            gateway = ["Null"]
        else:
            device = tmp_line["device"]

        dst_ip, dst_mask = tmp_line["dst"][0], tmp_line["dst"][1]
        dst = [f"{dst_ip}/{dotted_mask_to_cidr(dst_mask)}"]

        return {
            "id": [obj_id],
            "status": tmp_line["status"],
            "device": device,
            "dst": dst,
            "gateway": gateway,
            "distance": tmp_line["distance"],
            "priority": tmp_line["priority"],
            "vrf": tmp_line["vrf"],
            "comment": tmp_line["comment"],
        }
