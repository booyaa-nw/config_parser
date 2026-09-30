# core/doc_access.py
#
# novdom(root)/multivdomの構造差を吸収する共通ヘルパー。
# 現行実装の pre_format_config_obj / pre_format_global 相当を、
# Formatter側から呼べる形に切り出したもの。
from __future__ import annotations


def get_vdom_section(doc: dict, vdom_name: str) -> dict:
    """novdom(root)/multivdomの構造差を吸収して、指定vdomの設定dictを返す。"""
    if doc["header"]["vdom"] == 1:
        for vdom_obj in doc["vdom"]:
            name = next(iter(vdom_obj))
            if name == vdom_name:
                return vdom_obj[name]
        return {}
    return doc.get("root", {})


def get_global_section(doc: dict) -> dict:
    key = "global" if doc["header"]["vdom"] == 1 else "root"
    return doc.get(key, {})


def iter_vdom_names(doc: dict) -> list[str]:
    """multivdomなら宣言されている全vdom名、novdomなら["root"]を返す。
    複数vdomに対してFormatterを一括実行する際の反復用ヘルパー。
    """
    if doc["header"]["vdom"] == 1:
        return [next(iter(v)) for v in doc["vdom"]]
    return ["root"]


def get_hostname(doc: dict, default: str = "unknown") -> str:
    """global(novdomならroot)配下のsystem_global.hostnameを取り出す。
    Excelブック名の生成(core/excel/writer.py)で使用。"""
    system_global = get_global_section(doc).get("system_global", {})
    hostname = system_global.get("hostname")
    return hostname[0] if hostname else default
