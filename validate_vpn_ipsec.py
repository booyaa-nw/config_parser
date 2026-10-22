"""vpn_ipsec_phase1 / vpn_ipsec_phase2 Formatterの実データ検証スクリプト。

実サンプル2件(FG_7.6_config01.conf / FG_7.6_config01_vdom.conf、どちらも
VPNウィザードで作成したdialup接続2件: test_ipsec1, test_remote01)に対して
実際にprocess_file()を動かし、以下を検証する。

- FG_7.2系サンプル(ipsec vpn設定が無い)では ipsec_phase1/ipsec_phase2 の
  カテゴリ自体がJSON出力に現れない(空カテゴリのシート/キーを作らない仕様)。
- FG_7.6系サンプルでは phase1/phase2 ともに2件ずつ、キー集合が
  field_namesの表示列と完全一致する。
- phase2の`src`/`dst`派生ロジック: addr-type=nameのエントリは
  `src-name`/`dst-name`の値がそのまま出ること、addr-type省略(→subnet
  デフォルト)のエントリは `src-subnet`/`dst-subnet`のデフォルト値から
  "0.0.0.0/0.0.0.0" が組み立てられること。
- phase2の`phase1name`で対応するphase1トンネル名と突合せできること。

実行方法: `uv run --project tools/config_parser python tools/config_parser/validate_vpn_ipsec.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent / "common" / "src"))
sys.path.insert(0, str(ROOT / "src"))

from config_parser.ftnt.fos import process_file  # noqa: E402

SAMPLE_DIR = ROOT / "tests" / "fg_config_sample"

NO_IPSEC_SAMPLES = [
    SAMPLE_DIR / "FG_7.2_config01.conf",
    SAMPLE_DIR / "FG_7.2_config01_vdom.conf",
]
IPSEC_SAMPLES = [
    SAMPLE_DIR / "FG_7.6_config01.conf",
    SAMPLE_DIR / "FG_7.6_config01_vdom.conf",
]

EXPECTED_PHASE1_KEYS = {
    "name", "type", "interface", "remote-gw", "ike-version", "peertype",
    "proposal", "dhgrp", "net-device", "mode-cfg", "eap", "transport",
    "ipv4-start-ip", "ipv4-end-ip", "dns-mode", "ipv4-split-include",
    "save-password", "wizard-type", "comments",
}
EXPECTED_PHASE2_KEYS = {
    "name", "phase1name", "proposal", "dhgrp", "src-addr-type", "src",
    "dst-addr-type", "dst", "comments",
}


def load_categories(sample_path, export_dir):
    import json

    result = process_file(str(sample_path), export_dir=str(export_dir), json_only=True)
    merged = {}
    for p in result.json_paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        for cat, body in doc.get("categories", {}).items():
            merged.setdefault(cat, []).extend(body["records"])
    return merged


def main():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        # 1. ipsec vpn設定が無いサンプルでは、カテゴリ自体が出現しないこと
        for sample in NO_IPSEC_SAMPLES:
            cats = load_categories(sample, tmp)
            assert "ipsec_phase1" not in cats, sample
            assert "ipsec_phase2" not in cats, sample
        print("OK: ipsec vpn未設定サンプル(FG_7.2系2件)でカテゴリが出現しないこと")

        # 2. ipsec vpn設定があるサンプルでの検証
        for sample in IPSEC_SAMPLES:
            cats = load_categories(sample, tmp)

            phase1_records = cats["ipsec_phase1"]
            phase2_records = cats["ipsec_phase2"]
            assert len(phase1_records) == 2, (sample, phase1_records)
            assert len(phase2_records) == 2, (sample, phase2_records)

            for r in phase1_records:
                assert set(r) == EXPECTED_PHASE1_KEYS, (sample, set(r))
            for r in phase2_records:
                assert set(r) == EXPECTED_PHASE2_KEYS, (sample, set(r))

            by_name_p1 = {r["name"][0]: r for r in phase1_records}
            by_name_p2 = {r["name"][0]: r for r in phase2_records}

            assert set(by_name_p1) == {"test_ipsec1", "test_remote01"}, sample
            assert set(by_name_p2) == {"test_ipsec1", "test_remote01"}, sample

            # phase1name でphase1側トンネル名と突合せできること
            for name, p2 in by_name_p2.items():
                assert p2["phase1name"] == [name], (sample, name, p2["phase1name"])
                assert name in by_name_p1, (sample, name)

            # test_remote01: mode-cfg/eap/ipv4-start-ip等が明示設定されている側
            remote01 = by_name_p1["test_remote01"]
            assert remote01["mode-cfg"] == ["enable"]
            assert remote01["eap"] == ["enable"]
            assert remote01["ipv4-start-ip"] == ["192.168.222.0"]
            assert remote01["wizard-type"] == ["dialup-forticlient"]

            # test_ipsec1: 上記が未設定側(デフォルト値にフォールバック)
            ipsec1 = by_name_p1["test_ipsec1"]
            assert ipsec1["mode-cfg"] == ["disable"]
            assert ipsec1["eap"] == ["disable"]
            assert ipsec1["ipv4-start-ip"] == []
            assert ipsec1["wizard-type"] == ["dialup-fortigate"]

            # src/dst派生: addr-type=nameのエントリ(test_ipsec1)は-name値、
            # addr-type省略=subnetデフォルトのエントリ(test_remote01)は
            # src-subnet/dst-subnetのデフォルト値から組み立てられること
            p2_ipsec1 = by_name_p2["test_ipsec1"]
            assert p2_ipsec1["src-addr-type"] == ["name"]
            assert p2_ipsec1["src"][0].endswith("_local") or p2_ipsec1["src"][0].endswith("_local02")
            assert p2_ipsec1["dst-addr-type"] == ["name"]
            assert p2_ipsec1["dst"] == ["test_ipsec1_remote"]

            p2_remote01 = by_name_p2["test_remote01"]
            assert p2_remote01["src-addr-type"] == ["subnet"], (sample, p2_remote01)
            assert p2_remote01["src"] == ["0.0.0.0/0.0.0.0"], (sample, p2_remote01)
            assert p2_remote01["dst-addr-type"] == ["subnet"]
            assert p2_remote01["dst"] == ["0.0.0.0/0.0.0.0"]

        print("OK: ipsec vpn設定ありサンプル(FG_7.6系2件)でphase1/phase2ともに"
              "キー集合一致・phase1name突合せ・src/dst派生ロジックを確認")

    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
