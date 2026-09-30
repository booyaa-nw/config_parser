"""firewall_ippool/firewall_vip/firewall_vipgrp/firewall_service_custom/
firewall_service_groupの5 Formatterを実サンプル4件に対して実際に動かし、
- 全レコードでキー集合がfield_namesの表示列と完全一致すること
- firewall_ippoolのtype別(overload/one-to-one/fixed-port-range/
  port-block-allocation)の値が正しく取れること
- firewall_vipのstatic-nat/port forward/FQDN参照、各パターンの値が
  正しく取れること
- firewall_service_customのunset由来のNone値(PINGのicmpcode等)が
  例外を起こさず扱えること
を確認する検証スクリプト(pytestの単体テストではなく手動実行用)。

実行方法(カレントディレクトリに依存せず、どこから実行してもよい):
    uv run --project tools/config_parser python tools/config_parser/validate_new_formatters.py
"""
from pathlib import Path

from config_parser.core.doc_access import iter_vdom_names
from config_parser.ftnt.fos.formatters.firewall_ippool import FirewallIppool
from config_parser.ftnt.fos.formatters.firewall_service_custom import FirewallServiceCustom
from config_parser.ftnt.fos.formatters.firewall_service_group import FirewallServiceGroup
from config_parser.ftnt.fos.formatters.firewall_vip import FirewallVip
from config_parser.ftnt.fos.formatters.firewall_vipgrp import FirewallVipgrp
from config_parser.ftnt.fos.parse import parse_config_file

# 実サンプルは tests/fg_config_sample/ に同梱(このファイルからの相対パス)。
SAMPLE_DIR = Path(__file__).parent / "tests" / "fg_config_sample"
SAMPLES = {
    "7.2_novdom": str(SAMPLE_DIR / "FG_7.2_config01.conf"),
    "7.2_multivdom": str(SAMPLE_DIR / "FG_7.2_config01_vdom.conf"),
    "7.6_novdom": str(SAMPLE_DIR / "FG_7.6_config01.conf"),
    "7.6_vdom": str(SAMPLE_DIR / "FG_7.6_config01_vdom.conf"),
}


def check_formatter(formatter, docs, label):
    total = 0
    for doc in docs:
        for vdom_name in iter_vdom_names(doc):
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
    check_formatter(FirewallIppool(), docs, "firewall_ippool")
    check_formatter(FirewallVip(), docs, "firewall_vip")
    check_formatter(FirewallVipgrp(), docs, "firewall_vipgrp")
    check_formatter(FirewallServiceCustom(), docs, "firewall_service_custom")
    check_formatter(FirewallServiceGroup(), docs, "firewall_service_group")

    print()
    print("=== firewall_ippool: type別の値確認(7.2_multivdom/root) ===")
    doc = parse_config_file(SAMPLES["7.2_multivdom"])
    records, _ = FirewallIppool().format(doc, "root")
    by_type = {}
    for rec in records:
        by_type.setdefault(rec["type"][0], rec)
    for t in ("overload", "one-to-one", "fixed-port-range", "port-block-allocation"):
        assert t in by_type, f"type={t}のippoolレコードが見つからない"
        print(f"  type={t}: {by_type[t]['name']} startip={by_type[t]['startip']} endip={by_type[t]['endip']}")
    assert by_type["fixed-port-range"]["port-per-user"] == ["32"]
    assert by_type["port-block-allocation"]["block-size"] == ["256"]

    print()
    print("=== firewall_vip: static-nat/port forward/FQDN参照の確認(7.2_multivdom/root) ===")
    records, _ = FirewallVip().format(doc, "root")
    by_name = {rec["name"][0]: rec for rec in records}
    assert by_name["vip_test01"]["extip"] == ["1.1.1.1"]
    assert by_name["vip_test01"]["mappedip"] == ["10.0.0.1"]
    assert by_name["vip_test02"]["type"] == ["fqdn"]
    assert by_name["vip_test02"]["mapped-addr"] == ["test-allow-routing-02"]
    assert by_name["vip_test04"]["portforward"] == ["enable"]
    assert by_name["vip_test04"]["mappedport"] == ["60000"]
    print("  static-nat/fqdn参照/port forwardの各パターン、値OK")

    print()
    print("=== firewall_vipgrp: member複数値の確認(7.2_multivdom/root) ===")
    records, _ = FirewallVipgrp().format(doc, "root")
    grp2 = next(r for r in records if r["name"] == ["test_vip_group2"])
    assert grp2["member"] == ["vip_test01", "vip_test05"]
    print(f"  {grp2['name']}: member={grp2['member']}")

    print()
    print("=== firewall_service_custom: unset由来のNone値の扱い確認(7.2_multivdom/root) ===")
    records, _ = FirewallServiceCustom().format(doc, "root")
    ping = next(r for r in records if r["name"] == ["PING"])
    all_icmp = next(r for r in records if r["name"] == ["ALL_ICMP"])
    assert ping["icmpcode"] is None, "PINGのicmpcodeはunset(None)のはず"
    assert all_icmp["icmptype"] is None, "ALL_ICMPのicmptypeはunset(None)のはず"
    print(f"  PING: icmptype={ping['icmptype']} icmpcode={ping['icmpcode']}")
    print(f"  ALL_ICMP: protocol={all_icmp['protocol']} icmptype={all_icmp['icmptype']}")

    print()
    print("OK: 新規5 Formatter(ippool/vip/vipgrp/service_custom/service_group)の"
          "キー集合一致・派生ロジック・None値の扱いを確認")


if __name__ == "__main__":
    main()
