# ftnt/fos/formatters/__init__.py
#
# 実装済みCategoryFormatterの一覧。「Formatterのファイル1つ＝Excelシート1つ
# ＝将来Webview化する場合の1画面」の原則により、ここに登録されているものが
# そのままExcelエクスポート対象(将来的にはWeb画面一覧)になる。
#
# 未実装のカテゴリ(例: firewall_proxy-policy, ipsec_vpn等)は単にここに
# 追加されていないだけであり、core/excel/writer.py 側で個別に
# スキップ処理を書く必要はない。
#
# 2026-09-26追記: firewall_ippool/vip/vipgrp/service_custom/service_group を
# 追加(実データで検証済み、architecture/config-parser-design.md参照)。
# `system_interface`はこうぢさんの指示により今回は対象外。
# `firewall_proxy-policy`は実サンプル4件のいずれにも該当コンフィグが
# 存在せず、フィールド構成を実データで検証できないため今回は見送った
# (architecture/config-parser-design.mdの「未確定・要相談」に記載、
# 実機のexplicit proxyサンプルが手に入り次第あらためて対応)。
# 動的ルーティング(router bgp/ospf/rip/isis/multicast等)も同様に、
# 具体的な依頼が無く複雑度も高いため今回はスコープ外。
from config_parser.ftnt.fos.formatters.firewall_address import FirewallAddress
from config_parser.ftnt.fos.formatters.firewall_addrgrp import FirewallAddrgrp
from config_parser.ftnt.fos.formatters.firewall_ippool import FirewallIppool
from config_parser.ftnt.fos.formatters.firewall_policy import FirewallPolicy
from config_parser.ftnt.fos.formatters.firewall_service_custom import FirewallServiceCustom
from config_parser.ftnt.fos.formatters.firewall_service_group import FirewallServiceGroup
from config_parser.ftnt.fos.formatters.firewall_vip import FirewallVip
from config_parser.ftnt.fos.formatters.firewall_vipgrp import FirewallVipgrp
from config_parser.ftnt.fos.formatters.router_static import RouterStatic
from config_parser.ftnt.fos.formatters.system_global import SystemGlobal
from config_parser.ftnt.fos.formatters.system_ha import SystemHa

FORMATTERS = [
    SystemGlobal(),
    SystemHa(),
    FirewallAddress(),
    FirewallAddrgrp(),
    FirewallIppool(),
    FirewallVip(),
    FirewallVipgrp(),
    FirewallServiceCustom(),
    FirewallServiceGroup(),
    FirewallPolicy(),
    RouterStatic(),
]
