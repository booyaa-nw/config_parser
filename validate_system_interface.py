"""system_interface Formatterを実サンプル4件に対して実際に動かし、
- 全レコードでキー集合がfield_namesの表示列と完全一致すること
- マルチvdomサンプルで、root/ext-vdomそれぞれに正しい件数のインタフェース
  が振り分けられること(vdomフィールドによる絞り込みの確認)
- type派生ロジック(vlanid設定時の'vlan'補完)が正しく働くこと
- ip/cidr変換(dotted_mask_to_cidr経由)が正しいこと、未設定時は空になること
- aggregate(member)・物理(role)・vlan(interface/vlanid)の各パターンの値
を確認する検証スクリプト(pytestの単体テストではなく手動実行用)。

実行方法(カレントディレクトリに依存せず、どこから実行してもよい):
    uv run --project tools/config_parser python tools/config_parser/validate_system_interface.py
"""
from pathlib import Path

from config_parser.core.doc_access import iter_vdom_names
from config_parser.ftnt.fos.formatters.system_interface import SystemInterface
from config_parser.ftnt.fos.parse import parse_config_file

SAMPLE_DIR = Path(__file__).parent / "tests" / "fg_config_sample"
SAMPLES = {
    "7.2_novdom": str(SAMPLE_DIR / "FG_7.2_config01.conf"),
    "7.2_multivdom": str(SAMPLE_DIR / "FG_7.2_config01_vdom.conf"),
    "7.6_novdom": str(SAMPLE_DIR / "FG_7.6_config01.conf"),
    "7.6_vdom": str(SAMPLE_DIR / "FG_7.6_config01_vdom.conf"),
}


def main():
    formatter = SystemInterface()
    docs = {label: parse_config_file(p) for label, p in SAMPLES.items()}

    print("=== キー集合の一致チェック・vdom別件数 ===")
    total = 0
    for label, doc in docs.items():
        for vdom_name in iter_vdom_names(doc):
            records, field_names = formatter.format(doc, vdom_name)
            display_keys = {k for k in field_names if k != "__layout__"}
            for rec in records:
                total += 1
                assert set(rec.keys()) == display_keys, (label, set(rec.keys()) ^ display_keys)
            print(f"  {label}/{vdom_name}: {len(records)} records, keys OK")
    print(f"  合計: {total} records")

    print()
    print("=== 7.2_multivdom: root/ext-vdomの振り分け確認 ===")
    doc = docs["7.2_multivdom"]
    root_records, _ = formatter.format(doc, "root")
    ext_records, _ = formatter.format(doc, "ext-vdom")
    root_names = {r["name"][0] for r in root_records}
    ext_names = {r["name"][0] for r in ext_records}
    assert root_names.isdisjoint(ext_names), "root/ext-vdomで同名インタフェースが重複している"
    assert "wan1" in root_names
    print(f"  root: {len(root_records)}件, ext-vdom: {len(ext_records)}件、重複なしOK")

    print()
    print("=== type派生ロジック(vlanid設定時の'vlan'補完)確認 ===")
    by_name = {r["name"][0]: r for r in root_records}
    assert by_name["_default"]["type"] == ["vlan"], by_name["_default"]
    assert by_name["quarantine"]["type"] == ["vlan"], by_name["quarantine"]
    assert by_name["wan1"]["type"] == ["physical"]
    assert by_name["fortilink"]["type"] == ["aggregate"]
    print(f"  _default: type={by_name['_default']['type']} vlanid={by_name['_default']['vlanid']}")
    print(f"  quarantine: type={by_name['quarantine']['type']} vlanid={by_name['quarantine']['vlanid']}")
    print(f"  wan1(物理,型明示): type={by_name['wan1']['type']}")

    print()
    print("=== ip/cidr変換の確認(7.6_novdom) ===")
    doc76 = docs["7.6_novdom"]
    records76, _ = formatter.format(doc76, "root")
    by_name76 = {r["name"][0]: r for r in records76}
    assert by_name76["wan2"]["ip"] == ["172.16.201.207/24"], by_name76["wan2"]
    assert by_name76["wan1"]["ip"] == [], "DHCPのwan1はip未設定のはず"
    assert by_name76["dmz"]["ip"] == [], "ip未設定のdmzは空のはず"
    print(f"  wan2(static): ip={by_name76['wan2']['ip']}")
    print(f"  wan1(dhcp): ip={by_name76['wan1']['ip']}(空であることを確認)")

    print()
    print("=== aggregate(member)・role確認(7.2_multivdom/root) ===")
    assert by_name["fortilink"]["member"] == ["a", "b"]
    assert by_name["wan1"]["role"] == ["wan"]
    assert by_name["dmz"]["role"] == ["dmz"]
    assert by_name["a"]["role"] == [], "aggregateメンバー'a'には明示的なroleが無いはず"
    print(f"  fortilink: member={by_name['fortilink']['member']}")
    print(f"  wan1: role={by_name['wan1']['role']}, dmz: role={by_name['dmz']['role']}, a(role無し): {by_name['a']['role']}")

    print()
    print("OK: system_interfaceのキー集合一致・vdom振り分け・type派生・"
          "ip/cidr変換・member/roleを確認")


if __name__ == "__main__":
    main()
