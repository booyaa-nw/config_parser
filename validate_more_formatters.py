"""firewall_policy/firewall_addrgrp/system_global/router_staticの4 Formatter
を実サンプル4件に対して実際に動かし、
- 全レコードでキー集合がfield_namesの表示列と完全一致すること
- firewall_policyのsrcaddr/dstaddr override(internet-service系)が
  実際に発火し、空にならないこと
- firewall_policyのgroups/users(identity-based)が正しく取れること
- router_staticのblackholeルートのdevice/gateway overrideが正しいこと
- 全カテゴリを合わせてExcel出力までできること(core/excel経由)
を確認する検証スクリプト(pytestの単体テストではなく手動実行用)。

実行方法(カレントディレクトリに依存せず、どこから実行してもよい):
    uv run --project tools/config_parser python tools/config_parser/validate_more_formatters.py
"""
from pathlib import Path

from openpyxl import load_workbook

from config_parser.core.doc_access import iter_vdom_names
from config_parser.core.excel.writer import ExcelWriter
from config_parser.ftnt.fos.formatters import FORMATTERS
from config_parser.ftnt.fos.formatters.firewall_addrgrp import FirewallAddrgrp
from config_parser.ftnt.fos.formatters.firewall_policy import FirewallPolicy
from config_parser.ftnt.fos.formatters.router_static import RouterStatic
from config_parser.ftnt.fos.formatters.system_global import SystemGlobal
from config_parser.ftnt.fos.parse import parse_config_file

# 実サンプルは tests/fg_config_sample/ に同梱(このファイルからの相対パス)。
SAMPLE_DIR = Path(__file__).parent / "tests" / "fg_config_sample"
SAMPLES = {
    "7.2_novdom": str(SAMPLE_DIR / "FG_7.2_config01.conf"),
    "7.2_multivdom": str(SAMPLE_DIR / "FG_7.2_config01_vdom.conf"),
    "7.6_novdom": str(SAMPLE_DIR / "FG_7.6_config01.conf"),
    "7.6_vdom": str(SAMPLE_DIR / "FG_7.6_config01_vdom.conf"),
}

# "tmp/"配下はリポジトリの.gitignoreで除外済み(検証時の使い捨て出力)。
OUT_DIR = Path(__file__).parent / "tmp" / "export_validate_more"


def check_formatter(formatter, docs, label):
    total = 0
    for doc in docs:
        for vdom_name in (["global"] if formatter.resolve_field_names(doc)["__layout__"].get("global") else iter_vdom_names(doc)):
            records, field_names = formatter.format(doc, vdom_name)
            display_keys = {k for k in field_names if k != "__layout__"}
            for rec in records:
                total += 1
                assert set(rec.keys()) == display_keys, (label, set(rec.keys()) ^ display_keys)
    print(f"  {label}: {total} records, keys OK")
    return total


def main():
    docs = [parse_config_file(p) for p in SAMPLES.values()]

    print("=== キー集合の一致チェック ===")
    check_formatter(SystemGlobal(), docs, "system_global")
    check_formatter(FirewallAddrgrp(), docs, "firewall_addrgrp")
    n_policy = check_formatter(FirewallPolicy(), docs, "firewall_policy")
    check_formatter(RouterStatic(), docs, "router_static")

    print()
    print("=== firewall_policy: internet-service系のsrcaddr/dstaddr override確認 ===")
    doc = parse_config_file(SAMPLES["7.2_multivdom"])
    formatter = FirewallPolicy()
    records, _ = formatter.format(doc, "root")
    for rec in records:
        if rec["id"] in (["4"], ["5"]):
            print(f"  id={rec['id']} srcaddr={rec['srcaddr']} dstaddr={rec['dstaddr']}")
            assert rec["srcaddr"], "srcaddr が空になってはいけない(internet-service-src override)"
            assert rec["dstaddr"] or rec["id"] == ["4"], "dstaddr が空になってはいけない"

    print()
    print("=== firewall_policy: groups/users(identity-based)確認 ===")
    doc76 = parse_config_file(SAMPLES["7.6_novdom"])
    records76, _ = formatter.format(doc76, "root")
    id4 = next(r for r in records76 if r["id"] == ["4"])
    id10 = next(r for r in records76 if r["id"] == ["10"])
    print(f"  id=4 groups={id4['groups']} users={id4['users']}")
    print(f"  id=10 groups={id10['groups']} users={id10['users']}")
    assert id4["groups"] == ["user_group"]
    assert id4["users"] == ["local_user", "local_user2"]
    assert id10["groups"] == ["Guest-group"]

    print()
    print("=== router_static: blackholeルートのdevice/gateway override確認 ===")
    rs = RouterStatic()
    records, _ = rs.format(doc76, "root")
    for rec in records:
        if rec["id"] in (["2"], ["3"], ["4"]):
            print(f"  id={rec['id']} device={rec['device']} gateway={rec['gateway']} dst={rec['dst']}")
            assert rec["device"] == ["blackhole"]
            assert rec["gateway"] == ["Null"]

    print()
    print("=== core/excel でのフルexport(全6 formatter) ===")
    writer = ExcelWriter(FORMATTERS)
    for label, path in SAMPLES.items():
        doc = parse_config_file(path)
        book_path = writer.export(doc, export_dir=str(OUT_DIR))
        wb = load_workbook(book_path)
        print(f"  [{label}] {book_path.name}: {wb.sheetnames}")

    print()
    print(f"OK: 全formatterでキー集合一致・派生ロジック確認・Excel出力まで成功 (policy合計{n_policy}件)")


if __name__ == "__main__":
    main()
