"""grammar.lark / parse.py の動作検証。

実サンプル(FOS 7.2 novdom/multivdom, FOS 7.6+MSW novdom/vdom)を対象に、
- ヘッダ情報の抽出
- novdom/multivdomの構造分岐
- 複数行にまたがる引用符付き文字列(コメント、証明書PEM)
- 1つのsetに複数値を持つフィールド(macaddr)
- 数値editキー(firewall policyのid)
- managed-switch(MSW)の2段ネストedit
などが壊れずにパースできることを確認する。

実サンプルはこのファイルと同じ`tests/`配下の`fg_config_sample/`に同梱している
(このファイルからの相対パスで参照するため、リポジトリごとどこにcloneしても
動作する。カレントディレクトリには依存しない)。見つからない場合は該当テストを
自動的にskipする。

実行方法:
    uv run pytest tools/config_parser/tests/test_parse.py -v
"""
from pathlib import Path

import pytest

from config_parser.ftnt.fos.parse import parse_config_file

SAMPLE_DIR = Path(__file__).parent / "fg_config_sample"
NOVDOM = SAMPLE_DIR / "FG_7.2_config01.conf"
MULTIVDOM = SAMPLE_DIR / "FG_7.2_config01_vdom.conf"

pytestmark = pytest.mark.skipif(
    not (NOVDOM.exists() and MULTIVDOM.exists()),
    reason=f"実サンプルファイルが見つからない ({SAMPLE_DIR})",
)

# FortiOS 7.6系 + MSW(FortiSwitch managed-switch)2台構成のサンプル。
FOS76_NOVDOM = SAMPLE_DIR / "FG_7.6_config01.conf"
FOS76_VDOM = SAMPLE_DIR / "FG_7.6_config01_vdom.conf"

fos76_skip = pytest.mark.skipif(
    not (FOS76_NOVDOM.exists() and FOS76_VDOM.exists()),
    reason=f"FOS7.6+MSWサンプルが見つからない ({SAMPLE_DIR})",
)


def test_novdom_header():
    doc = parse_config_file(NOVDOM)
    assert doc["header"]["model"] == "FGT60F"
    assert doc["header"]["version"] == "7.2.10"
    assert doc["header"]["vdom"] == 0
    assert "root" in doc
    assert "vdom" not in doc
    assert "global" not in doc


def test_multivdom_header_and_split():
    doc = parse_config_file(MULTIVDOM)
    assert doc["header"]["vdom"] == 1
    vdom_names = [next(iter(v)) for v in doc["vdom"]]
    assert vdom_names == ["root", "ext-vdom"]
    assert "global" in doc
    assert "system_global" in doc["global"]


def test_multivdom_hostname_and_alias_quoted_value():
    doc = parse_config_file(MULTIVDOM)
    sysg = doc["global"]["system_global"]
    assert sysg["hostname"] == ["FG60F-Primary"]
    assert sysg["alias"] == ["ラボFW01"]


def test_multiline_quoted_value_with_embedded_newline():
    """set description "コメント\nテスト" のように、値の途中に本物の改行が
    入っているケース。旧実装(正規表現+shlexの行単位処理)が壊れやすかった箇所。
    """
    doc = parse_config_file(MULTIVDOM)
    iface = doc["global"]["system_interface"]
    dmz = next(rec for entry in iface for name, rec in entry.items() if name == "dmz")
    assert dmz["description"] == ["コメント\nテスト"]


def test_multiline_pem_certificate_value():
    doc = parse_config_file(MULTIVDOM)
    certs = doc["global"]["certificate_local"]
    ca = next(rec for entry in certs for name, rec in entry.items() if name == "Fortinet_CA_SSL")
    pk = ca["private-key"][0]
    assert pk.startswith("-----BEGIN ENCRYPTED PRIVATE KEY-----")
    assert pk.endswith("-----END ENCRYPTED PRIVATE KEY-----")
    assert pk.count("\n") > 20  # 30行程度のPEMブロックが1つの値として保持されている


def test_set_with_multiple_values():
    """set macaddr "a" "b" のように、1つのsetに複数の値がある場合。"""
    doc = parse_config_file(MULTIVDOM)
    root = next(v["root"] for v in doc["vdom"] if "root" in v)
    addr = next(
        rec for entry in root["firewall_address"] for name, rec in entry.items()
        if name == "test_device_mac"
    )
    assert addr["macaddr"] == [
        "00:00:00:00:00:00",
        "00:00:00:00:00:00-00:00:00:00:00:02",
    ]


def test_numeric_edit_key_firewall_policy():
    """firewall policyの edit 1 のように、edit名が(クォート無しの)数値のケース。"""
    doc = parse_config_file(MULTIVDOM)
    root = next(v["root"] for v in doc["vdom"] if "root" in v)
    policy = root["firewall_policy"]
    ids = [next(iter(entry)) for entry in policy]
    assert "1" in ids


def test_vdom_content_block_without_explicit_next():
    """マルチvdom構成のvdom本体( config vdom / edit <name> / ... / end )で
    editに対応する"next"が省略されているケースでも、正しくカテゴリ数が
    取れていること(=空dict/空listに壊れていないこと)を確認する。
    """
    doc = parse_config_file(MULTIVDOM)
    root = next(v["root"] for v in doc["vdom"] if "root" in v)
    ext = next(v["ext-vdom"] for v in doc["vdom"] if "ext-vdom" in v)
    assert len(root) > 50
    assert len(ext) > 50


# --- FortiOS 7.6系 + MSW(managed-switch)2台構成 -----------------------
# 7.2系サンプルでは検証できていなかった、実際のMSWコンフィグ(config
# switch-controller managed-switch、ポート単位のedit入れ子)が正しく
# パースできることを確認する。文法・parse.py自体は7.2向けに書いたものを
# 変更せずに使用しており、7.6系ヘッダ/MSWブロックへの追加対応は不要
# だったことも合わせて確認する。


@fos76_skip
def test_fos76_novdom_header():
    doc = parse_config_file(FOS76_NOVDOM)
    assert doc["header"]["model"] == "FGT60F"
    assert doc["header"]["version"] == "7.6.7"
    assert doc["header"]["vdom"] == 0
    assert "root" in doc


@fos76_skip
def test_fos76_managed_switch_two_units():
    """MSW2台(S224EPTF20005577 / S224EPTF20000388)がそれぞれ1エントリと
    して取れており、値が混ざっていないこと。"""
    doc = parse_config_file(FOS76_NOVDOM)
    msw = doc["root"]["switch-controller_managed-switch"]
    names = [next(iter(entry)) for entry in msw]
    assert names == ["S224EPTF20005577", "S224EPTF20000388"]

    sw1 = next(entry["S224EPTF20005577"] for entry in msw if "S224EPTF20005577" in entry)
    sw2 = next(entry["S224EPTF20000388"] for entry in msw if "S224EPTF20000388" in entry)
    assert sw1["sn"] == ["S224EPTF20005577"]
    assert sw2["sn"] == ["S224EPTF20000388"]


@fos76_skip
def test_fos76_managed_switch_ports_nested_edit():
    """managed-switch内の"config ports" / "edit portN"という2段目のedit
    ネストが壊れずに取れており、ポートごとの値(mac-addrなど)が正しく
    対応するユニットに属していること。"""
    doc = parse_config_file(FOS76_NOVDOM)
    msw = doc["root"]["switch-controller_managed-switch"]
    sw1 = next(entry["S224EPTF20005577"] for entry in msw if "S224EPTF20005577" in entry)
    ports = sw1["ports"]
    assert len(ports) == 28
    port1 = next(rec for entry in ports for name, rec in entry.items() if name == "port1")
    assert port1["mac-addr"] == ["e0:23:ff:df:18:e0"]


@fos76_skip
def test_fos76_vdom_managed_switch_under_root_vdom():
    """マルチvdom構成のサンプルでも、MSWがvdom(root)配下のカテゴリとして
    正しく現れること。"""
    doc = parse_config_file(FOS76_VDOM)
    assert doc["header"]["vdom"] == 1
    root = next(v["root"] for v in doc["vdom"] if "root" in v)
    msw = root["switch-controller_managed-switch"]
    names = [next(iter(entry)) for entry in msw]
    assert names == ["S224EPTF20005577", "S224EPTF20000388"]
