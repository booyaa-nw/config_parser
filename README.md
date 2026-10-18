# config_parser

NW機器コンフィグ(現状はFortiOS: FortiGate本体 + MSW/FortiSwitch managed-switch)を
dictに変換し、バージョン/モデル差分吸収・デフォルト値補完のうえ、Excelパラメータ
シート(・JSON)へ出力するツール。設計方針・決定事項は Claude Project の
`architecture/config-parser-design.md` を参照。

## 実装状況(2026-10-02時点)

パイプラインの4段階(Lark Parse → Materialize → Format(カテゴリ単位) → Excel/JSON
Export)に加え、CLIエントリポイント(`config_parser fgt <file>`)まで実装・実データ
検証済み。実装済みカテゴリは12個(下記モジュール構成を参照)。`firewall_proxy-policy`
と動的ルーティング(router bgp/ospf/rip/isis/multicast等)は実サンプルが無い/スコープ
確定していないため見送り(詳細は`architecture/config-parser-design.md`の
「未確定・要相談」参照)。

## モジュール構成

- `src/config_parser/ftnt/fos/grammar.lark` / `parse.py` — FortiOS(fos)コンフィグ用の
  Lark文法・パーサー。`config`/`edit`/`set`/`unset`/`next`/`end`の構造とクォート処理
  (複数行文字列)のみを文法で扱い、カテゴリ名の意味づけは`FosTransformer`側で行う。
  `parser="lalr"`採用(Earley版と出力が完全一致することを確認したうえで、約25倍高速)。
- `src/config_parser/core/formatter_base.py` — `CategoryFormatter`基底クラス。
  「1 Formatterファイル = 1 Excelシート = (将来)1 Web画面」の原則。サブクラスは
  `extract_records()`/`build_record()`のみ実装すればよく、デフォルト値補完は
  `field_names`の`default_value`に一本化されている。
- `src/config_parser/core/doc_access.py` — novdom/multivdomの構造差を吸収する
  共通ヘルパー(`get_vdom_section`/`get_global_section`/`iter_vdom_names`/`get_hostname`)。
- `src/config_parser/core/naming.py` — Excel/JSON共通の出力ベースファイル名
  (`hostname_version_タイムスタンプ`)生成。
- `src/config_parser/core/excel/` — `ExcelWriter`(旧`ExportExcel`の置き換え)。
  `field_names['__layout__']['layout']`(`simple`/`virtical`/`composite`)をキーにした
  レンダラー登録制で、カテゴリ名直書きの分岐が無い。未実装カテゴリは対象
  Formatterのリストに含めないだけで自動的にスキップされる。シートはvdom単位で
  グルーピングされる(root系のシートをまとめて出力→続けてext-vdom系、のように)。
- `src/config_parser/core/json_export.py` — JSON出力層。スコープ
  (global用 + vdom名ごと)単位でファイルを分割する(下記「JSON出力」参照)。
- `src/config_parser/core/pipeline.py` — `process_config_file()`。1設定ファイルの
  parse→Excel/JSON出力までをCLI・他スクリプトの両方から同じ関数として呼べるように
  した層。ベンダー/機種ファミリーに依存しない(`formatters`/`parse_fn`を呼び出し側
  から渡す設計)。
- `src/config_parser/ftnt/fos/__init__.py` — `process_file(path, **kwargs)`。FortiOS
  向けに`FORMATTERS`/`parse_config_file`を固定した`process_config_file()`のショート
  カット。他スクリプトから使う場合はこれをそのままimportすればよい(下記参照)。
- `src/config_parser/cli.py` — CLIエントリポイント。`config_parser fgt <file...>`
  (config_backup/net_configと同じ、サブコマンドで機器ファミリーを指定する方式)。
- `src/config_parser/ftnt/fos/formatters/` — 実装済み12 Formatter:
  `system_global`(singleton/virtical)、`system_ha`(composite、HA管理IF一覧の
  サブテーブル込み)、`system_interface`(simple。`config global`配下に全vdom分が
  まとまっている特殊構造のためFormatter自身がエントリの`vdom`キーで絞り込む。
  vlanid設定時の`type: vlan`派生、ip/cidr変換、IPv6サブブロックは今回スコープ外)、
  `firewall_address`(simple、typeごとの派生アドレス表示)、
  `firewall_addrgrp`、`firewall_ippool`、`firewall_vip`、`firewall_vipgrp`、
  `firewall_service_custom`、`firewall_service_group`、`firewall_policy`
  (internet-service系のsrcaddr/dstaddr override、identity-basedのgroups/users含む)、
  `router_static`(blackhole/sdwan-zoneの優先順位、サブネットマスク→CIDR変換)。

## CLIの使い方

```
# 単体指定(Excel出力のみ、既定)
config_parser fgt backup01.conf

# 複数ファイルをまとめて変換
config_parser fgt backup01.conf backup02.conf backup03.conf

# Excelに加えてJSONも出力する
config_parser fgt backup01.conf --json

# JSONのみ出力する(Excelは出力しない、--jsonの指定は不要)
config_parser fgt backup01.conf --json-only

# 出力先ディレクトリを変更(既定: ./booyaa_log/export)
config_parser fgt backup01.conf -d ./out

# JSON出力先だけ別ディレクトリにする(既定: -d/--directoryと同じ)
config_parser fgt backup01.conf --json --json-dir ./out/json
```

### JSON出力(マルチvdom時のファイル分割)

Excel出力は(vdomの有無に関わらず)1ブックにまとめてシートを分ける一方、JSON出力は
こうぢさんの依頼により**ファイル自体をスコープ単位で分割**する。

- global用ファイル(`<base>_global.json`): `system_global`/`system_ha`等、vdomに
  属さないカテゴリ。
- vdom単位のファイル(`<base>_<vdom名>.json`): vdomごとに1ファイル。novdomの場合は
  vdom名が`root`固定になるため、実質「global用 + root用」の2ファイルになる。
  multivdomの場合はglobal用 + 宣言されているvdom数分のファイルになる。

各JSONファイルの中身は `{"header": {...}, "scope": "...", "categories": {"<sheetname>":
{"field_names": {...}, "records": [...]}}}` という形(`sheetname`はExcelのシート名と
共通)。レコードが1件も無いカテゴリはExcel同様に含めない。

### 他スクリプトからの利用

CLIを経由せず、直接importして使うこともできる:

```python
from config_parser.ftnt.fos import process_file

result = process_file(
    "backup01.conf",
    export_dir="./out",
    json_output=True,
)
print(result.hostname, result.excel_path, result.json_paths)
```

## 依存関係

- `lark` — コンフィグのパース。
- `openpyxl` — Excel出力。
- `rich` — CLIの結果テーブル表示(config_backup/net_configと同じ)。
- `common`(`tools/common`、uv workspace依存) — `router_static.py`・
  `system_interface.py`が`common.iptools.calc.ipv4.dotted_mask_to_cidr()`
  (サブネットマスク→CIDR変換)を使用。旧実装(`booyaa_old`)は
  `booyaa.ipcalc.ipv4.IPv4.ipmask2cidr()`を使っていたが、現行モノレポでは
  この処理は`tools/common`側に移設済み(`operations/tool-registry.md`参照)。

## 検証

実サンプル4件(`tests/fg_config_sample/FG_7.2_config01[_vdom].conf` /
`FG_7.6_config01[_vdom].conf`)を使う。これらは証明書の秘密鍵等を含みうる実機
コンフィグのため`.gitignore`で除外されており、各自ローカルに配置して使う想定
(無い場合、該当するテスト・検証スクリプトは自動的にskip/エラーになる)。

- `tests/test_parse.py` — 文法・パーサーのpytestテスト(12件)。
- `tests/test_pipeline.py` — CLI/pipeline/JSON出力のpytestテスト(11件、
  system_interfaceのvdom振り分け検証含む)。
  ```
  uv run pytest tools/config_parser -v
  ```
- `validate_firewall_address.py` / `validate_export.py` / `validate_more_formatters.py`
  / `validate_new_formatters.py` / `validate_system_interface.py` — Formatter/Excel
  出力を実サンプルに対して実際に動かして確認する検証スクリプト(pytestの単体テストで
  はなく手動実行用)。
  ```
  uv run --project tools/config_parser python tools/config_parser/validate_system_interface.py
  ```
  出力される.xlsx/.jsonは`tmp/`配下(`.gitignore`で除外済み)に書き出される。

## 次のアクション

- `firewall_proxy-policy`(explicit proxyのポリシー): 実サンプル4件のいずれにも
  該当コンフィグが存在せず、フィールド構成を実データで検証できないため見送り中。
  実機のexplicit proxyサンプルが手に入り次第対応。
- 動的ルーティング(`router bgp`/`ospf`/`rip`/`isis`/`multicast`等): 具体的な
  依頼が無く複雑度も高いため今回はスコープ外。
- `system_interface`の`config ipv6`サブブロック(ip6-mode/ip6-allowaccess等)は
  今回スコープ外(IPv4のみ実装)。IPv6設定の確認が必要になった時点で追加検討。
- いくつかのswitch-controller系トグル項目(`switch-controller-igmp-snooping`等)の
  デフォルト値は実データで両方向(enable/disable)を確認できておらず、FortiOSの
  一般的な仕様に基づく推測値である点に留意(`system_interface.py`のコメント参照)。
- 詳細は Claude Project の `architecture/config-parser-design.md` を参照。
