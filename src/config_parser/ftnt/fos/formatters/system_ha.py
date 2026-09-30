# ftnt/fos/formatters/system_ha.py
#
# core/excel/layouts.py の 'composite' レイアウト(旧export/ha.py相当)を
# 実データで検証するために書いたFormatter。`config system ha`はカテゴリ内に
# `config ha-mgmt-interfaces`という入れ子のedit一覧を持つ、firewall_address等
# とは異なる「単一設定ブロック(dict)＋入れ子リスト」という形をしている。
#
# `config system ha`自体は(firewall_addressのようなedit一覧ではなく)
# 単一のset群なので、parse.py側でもdictとして返る(listにならない)。
# そのためextract_recordsは「0件 or 1件のdictを含むlist」を返す。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_global_section
from config_parser.core.formatter_base import CategoryFormatter


class SystemHa(CategoryFormatter):
    field_names = {
        "__layout__": {
            "layout": "composite", "sheetname": "ha", "global": True,
            "header_width": 22, "value_width": 30,
        },
        "group-id":       {"width": 12, "default_value": ["0"]},
        "group-name":     {"width": 25, "default_value": []},
        "mode":           {"width": 15, "default_value": ["standalone"]},
        "hbdev":          {"width": 35, "default_value": []},
        "ha-mgmt-status": {"width": 15, "default_value": ["disable"]},
        "override":       {"width": 12, "default_value": ["disable"]},
        "priority":       {"width": 10, "default_value": ["128"]},
        # サブテーブル: 1配下のha-mgmt-interfaces(edit一覧)を、メイン
        # ブロックの下に別の横テーブルとして描画する(core/excel/layouts.py
        # のrender_composite参照)。
        "ha-mgmt-interfaces": {
            "default_value": [],
            "subtable": {
                "field_names": {
                    "id":        {"width": 8},
                    "interface": {"width": 20},
                    "gateway":   {"width": 20},
                },
            },
        },
    }

    _raw_defaults = {
        "group-id": ["0"], "group-name": [], "mode": ["standalone"],
        "hbdev": [], "ha-mgmt-status": ["disable"], "override": ["disable"],
        "priority": ["128"], "ha-mgmt-interfaces": [],
    }

    def extract_records(self, doc, vdom_name):
        # system_ha は edit一覧ではなく単一dictのカテゴリなので、
        # 0件 or 1件のlistに揃えてbuild_recordに渡す。
        section = get_global_section(doc)
        ha = section.get("system_ha")
        return [ha] if ha else []

    def build_record(self, raw_obj, field_names):
        # raw_objはfirewall_addressのような{name: {...}}ではなく、
        # 既にsystem_ha自体の属性dict。
        tmp_line = deepcopy(raw_obj)
        for key, default in self._raw_defaults.items():
            tmp_line.setdefault(key, default)
        tmp_line = self.apply_defaults(tmp_line, field_names)

        mgmt_interfaces = []
        for entry in tmp_line["ha-mgmt-interfaces"]:
            edit_id = next(iter(entry))
            sub = entry[edit_id]
            mgmt_interfaces.append({
                "id": [edit_id],
                "interface": sub.get("interface", []),
                "gateway": sub.get("gateway", []),
            })

        return {
            "group-id": tmp_line["group-id"],
            "group-name": tmp_line["group-name"],
            "mode": tmp_line["mode"],
            "hbdev": tmp_line["hbdev"],
            "ha-mgmt-status": tmp_line["ha-mgmt-status"],
            "override": tmp_line["override"],
            "priority": tmp_line["priority"],
            "ha-mgmt-interfaces": mgmt_interfaces,
        }
