# ftnt/fos/formatters/vpn_ipsec_phase1.py
#
# こうぢさんより「`fg_config_parser/vpn_ipsec_parser.py`(旧booya_config_parser、
# 未完成のプロトタイプ)を参考にipsecvpnを追加してほしい」という依頼を受けて
# 新規実装(2026-10-22)。旧実装はphase1/phase2を1シートに横並び合成する
# 独自レンダラー(export/ha.py相当の専用コード)を試みていたが、
# `field_names`自体が未設定(`params.config_vdom.field_names`にphase1/phase2の
# 定義が無く、実際には動作しないコードだった)うえ、旧`export/excel.py`側にも
# `category == 'ipsec_vpn': continue`という明示的なスキップがあり、
# このプロジェクトでは一度も完成していなかった。
#
# 本実装では、決定事項1の原則「1 Formatterファイル=1 Excelシート=
# (将来)1 Web画面」に合わせ、phase1-interfaceとphase2-interfaceを
# それぞれ独立したFormatter(本ファイルと vpn_ipsec_phase2.py)に分割した。
# phase2側に`phase1name`列を残しているので、どのphase1トンネルに
# 対応するかはそちらで追える(firewall_vip/vipgrpのような「関連カテゴリは
# 別シートだがキーで突合せ可能」という既存パターンと同じ考え方)。
#
# 実データ検証(2026-10-22): `tests/fg_config_sample/FG_7.6_config01[_vdom].conf`
# (novdom/vdom各1件、どちらもVPNウィザードで作成したdialup接続2件、
# FG_7.2系サンプルにはvpn ipsec設定自体が存在しない)。rootのみに
# データがあり、ext-vdom側には無いことも確認済み(他の多くのカテゴリと
# 同様、未使用vdomでは空リストになるだけで正常に動作する)。
#
# **重要: psksecretは表示列に含めていない**(セキュリティ上の判断)。
# 生コンフィグ上は`ENC <暗号化文字列>`という、その機器固有の内部鍵で
# 暗号化された不可逆のblobであり平文PSKそのものではないが、社外共有や
# 複数人での閲覧が想定されるExcel/JSONの出力物に暗号化済みとはいえ鍵材料を
# 含めるのは望ましくないと判断し、意図的に除外した。設定有無だけ分かれば
# 十分という場合は`psk-configured`的な真偽値列を別途追加できるので、
# 必要であればこうぢさんに確認のうえ追加する。
#
# **未検証のデフォルト値(要フォローアップ)**: 実サンプル2件(test_ipsec1/
# test_remote01)はどちらもVPNウィザードで作成したdialup接続(`type dynamic`)
# で、`type`/`ike-version`/`peertype`/`dhgrp`はどちらの接続も値を明示していた
# ため、「未設定時にFortiOSが実際にどう振る舞うか」を実データで確認できて
# いない。これらの`default_value`(`static`/`1`/`any`/`14`)はFortiOSの
# 一般的な仕様に基づく推測値。また`remote-gw`(拠点間=static接続のリモート
# ゲートウェイIP)は実サンプルがdialup接続のみのため一度も出現しておらず、
# フィールド自体の実在は確認済みだが値が入ったケースは未検証。実際の
# 拠点間(static)接続のサンプルが手に入り次第、あらためて確認すること。
from __future__ import annotations

from copy import deepcopy

from config_parser.core.doc_access import get_vdom_section
from config_parser.core.formatter_base import CategoryFormatter


class VpnIpsecPhase1(CategoryFormatter):
    field_names = {
        "__layout__":          {"layout": "simple", "sheetname": "ipsec_phase1", "global": False},
        "name":                {"width": 25, "default_value": []},
        "type":                {"width": 10, "default_value": ["static"]},
        "interface":           {"width": 15, "default_value": []},
        "remote-gw":           {"width": 20, "default_value": []},
        "ike-version":         {"width": 6,  "default_value": ["1"]},
        "peertype":            {"width": 10, "default_value": ["any"]},
        "proposal":            {"width": 35, "default_value": []},
        "dhgrp":               {"width": 15, "default_value": ["14"]},
        "net-device":          {"width": 10, "default_value": ["disable"]},
        "mode-cfg":            {"width": 10, "default_value": ["disable"]},
        "eap":                 {"width": 8,  "default_value": ["disable"]},
        "transport":           {"width": 8,  "default_value": ["auto"]},
        "ipv4-start-ip":       {"width": 16, "default_value": []},
        "ipv4-end-ip":         {"width": 16, "default_value": []},
        "dns-mode":            {"width": 8,  "default_value": ["manual"]},
        "ipv4-split-include":  {"width": 25, "default_value": []},
        "save-password":       {"width": 10, "default_value": ["disable"]},
        "wizard-type":         {"width": 20, "default_value": []},
        "comments":            {"width": 35, "default_value": []},
    }

    # 生コンフィグ側にしか存在しない、派生計算専用のキー(表示列ではないのでfield_namesには入れない)
    _raw_defaults: dict = {}

    def extract_records(self, doc, vdom_name):
        vdom_obj = get_vdom_section(doc, vdom_name)
        return vdom_obj.get("vpn_ipsec_phase1-interface", [])

    def build_record(self, raw_obj, field_names):
        obj_name = next(iter(raw_obj))
        tmp_line = deepcopy(raw_obj[obj_name])
        tmp_line = self.apply_defaults(tmp_line, field_names)

        record = {k: tmp_line[k] for k in field_names if k != "__layout__"}
        record["name"] = [obj_name]
        return record
