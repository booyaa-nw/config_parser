"""firewall_address.py の書き直し版を、実サンプル4件(7.2 novdom/multivdom,
7.6 novdom/vdom)全てのfirewall_addressレコードに対して実際に動かし、
- 全レコードでaddressが空にならないこと(=未対応のtypeが無いこと)
- typeごとの代表例がおかしな値になっていないこと
- レコードのキー集合がfield_namesの表示列と完全一致すること
を確認する検証スクリプト(pytestの単体テストではなく手動実行用)。

実行方法(カレントディレクトリに依存せず、どこから実行してもよい):
    uv run --project tools/config_parser python tools/config_parser/validate_firewall_address.py
"""
from pathlib import Path

from config_parser.core.doc_access import iter_vdom_names
from config_parser.ftnt.fos.formatters.firewall_address import FirewallAddress
from config_parser.ftnt.fos.parse import parse_config_file

# 実サンプルは tests/fg_config_sample/ に同梱(このファイルからの相対パス)。
SAMPLE_DIR = Path(__file__).parent / "tests" / "fg_config_sample"
SAMPLES = {
    "7.2_novdom": str(SAMPLE_DIR / "FG_7.2_config01.conf"),
    "7.2_multivdom": str(SAMPLE_DIR / "FG_7.2_config01_vdom.conf"),
    "7.6_novdom": str(SAMPLE_DIR / "FG_7.6_config01.conf"),
    "7.6_vdom": str(SAMPLE_DIR / "FG_7.6_config01_vdom.conf"),
}


def main():
    formatter = FirewallAddress()
    total = 0
    empty_address = []
    by_type_example = {}

    for label, path in SAMPLES.items():
        doc = parse_config_file(path)
        for vdom_name in iter_vdom_names(doc):
            records, field_names = formatter.format(doc, vdom_name)
            for rec in records:
                total += 1
                t = tuple(rec["type"])
                by_type_example.setdefault(t, (label, vdom_name, rec))
                if not rec["address"]:
                    empty_address.append((label, vdom_name, rec["name"], rec["type"]))

    print(f"total records: {total}")
    print(f"records with EMPTY address: {len(empty_address)}")
    for e in empty_address:
        print("  EMPTY:", e)

    print()
    print("=== per-type example (name -> address) ===")
    for t, (label, vdom_name, rec) in sorted(by_type_example.items()):
        print(f"  {t!s:25} [{label}/{vdom_name}] {rec['name']!r:30} -> {rec['address']!r} "
              f"(interface={rec['interface']!r})")

    # field_names sanity: __layout__ present, no stray raw keys leaked into a record
    _, field_names = formatter.format(parse_config_file(SAMPLES["7.2_novdom"]), "root")
    assert "__layout__" in field_names
    display_keys = {k for k in field_names if k != "__layout__"}
    sample_rec = by_type_example[("ipmask",)][2]
    assert set(sample_rec.keys()) == display_keys, (set(sample_rec.keys()), display_keys)
    print()
    print("OK: record keys exactly match field_names display columns:", sorted(display_keys))

    assert not empty_address, "未対応のtypeがある(address空のレコードが存在する)"
    print()
    print("OK: 全レコードでaddressが空にならないことを確認")


if __name__ == "__main__":
    main()
