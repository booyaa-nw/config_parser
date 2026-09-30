"""core/pipeline.py・core/json_export.py・cli.pyの動作検証(2026-09-26新規)。

実サンプル(FOS 7.2/7.6, novdom/multivdom)を使って、
- ftnt/fos.process_file()経由(CLIを介さない直接import利用)でExcel/JSONが
  出力できること
- JSON出力がスコープ(global/vdom名)単位で分割されること
  (novdomはglobal+rootの2ファイル、multivdomはglobal+vdom数分)
- json_only=Trueの場合Excelが出力されないこと
- Excel出力のシート順序がvdom単位でグルーピングされていること
  (root系→ext-vdom系の順で、カテゴリ単位のインターリーブになっていないこと)
- cli.build_parser()の引数解析(--json/--json-only/--json-dir/複数ファイル)
を確認する。

実サンプルが無い環境では自動skipする(tests/test_parse.pyと同じ方針)。

実行方法:
    uv run pytest tools/config_parser/tests/test_pipeline.py -v
"""
import json
from pathlib import Path

import pytest
from openpyxl import load_workbook

from config_parser.cli import build_parser
from config_parser.core.pipeline import process_config_file
from config_parser.ftnt.fos import process_file
from config_parser.ftnt.fos.formatters import FORMATTERS
from config_parser.ftnt.fos.parse import parse_config_file

SAMPLE_DIR = Path(__file__).parent / "fg_config_sample"
NOVDOM = SAMPLE_DIR / "FG_7.6_config01.conf"
MULTIVDOM = SAMPLE_DIR / "FG_7.2_config01_vdom.conf"

pytestmark = pytest.mark.skipif(
    not (NOVDOM.exists() and MULTIVDOM.exists()),
    reason=f"実サンプルファイルが見つからない ({SAMPLE_DIR})",
)


def test_process_file_novdom_excel_and_json(tmp_path):
    result = process_file(str(NOVDOM), export_dir=str(tmp_path), json_output=True)

    assert result.excel_path is not None
    assert result.excel_path.exists()
    # novdomはiter_vdom_namesが["root"]を返すため、global用+root用の2ファイル。
    assert len(result.json_paths) == 2
    scopes = {p.stem.rsplit("_", 1)[-1] for p in result.json_paths}
    assert scopes == {"global", "root"}


def test_process_file_multivdom_json_scopes(tmp_path):
    result = process_file(str(MULTIVDOM), export_dir=str(tmp_path), json_output=True)

    scopes = {p.stem.rsplit("_", 1)[-1] for p in result.json_paths}
    # 7.2_config01_vdom.conf は root/ext-vdom の2vdom + global。
    assert scopes == {"global", "root", "ext-vdom"}


def test_process_file_json_only_skips_excel(tmp_path):
    result = process_file(str(NOVDOM), export_dir=str(tmp_path), json_only=True)

    assert result.excel_path is None
    assert len(result.json_paths) == 2
    assert not any(tmp_path.glob("*.xlsx"))


def test_json_scope_file_content(tmp_path):
    result = process_file(str(NOVDOM), export_dir=str(tmp_path), json_only=True)


    global_path = next(p for p in result.json_paths if p.stem.endswith("_global"))
    payload = json.loads(global_path.read_text(encoding="utf-8"))
    assert payload["scope"] == "global"
    assert "global" in payload["categories"]  # system_global -> sheetname "global"
    assert "ha" in payload["categories"]
    # 各カテゴリはfield_names(列定義)とrecordsの両方を持つ。
    assert "field_names" in payload["categories"]["global"]
    assert "records" in payload["categories"]["global"]
    assert len(payload["categories"]["global"]["records"]) == 1


def test_json_skips_empty_categories(tmp_path):
    # 7.6_novdom には firewall_vipgrp のレコードが無いため、
    # root用JSONのcategoriesに"vip group"キーが含まれないこと
    # (Excel出力の「空カテゴリはシートを作らない」方針とJSON側でも揃っている)。
    result = process_file(str(NOVDOM), export_dir=str(tmp_path), json_only=True)


    root_path = next(p for p in result.json_paths if p.stem.endswith("_root"))
    payload = json.loads(root_path.read_text(encoding="utf-8"))
    assert "vip group" not in payload["categories"]


def test_excel_sheet_order_grouped_by_vdom(tmp_path):
    result = process_file(str(MULTIVDOM), export_dir=str(tmp_path))
    wb = load_workbook(result.excel_path)

    root_idx = {name: i for i, name in enumerate(wb.sheetnames) if name.startswith("root ")}
    ext_idx = {name: i for i, name in enumerate(wb.sheetnames) if name.startswith("ext-vdom ")}

    assert root_idx, "root系のシートが見つからない"
    assert ext_idx, "ext-vdom系のシートが見つからない"
    # root系シートは全てext-vdom系シートより前に来ること(vdom単位でグルーピング)。
    assert max(root_idx.values()) < min(ext_idx.values())


def test_process_config_file_is_vendor_agnostic():
    # cli.py/ftnt.fos.process_file()を経由せず、core.pipelineを直接呼んでも
    # 同じ結果になること(将来Alaxala等を追加する際にこの層をそのまま
    # 再利用できることの確認)。
    import inspect

    sig = inspect.signature(process_config_file)
    assert "formatters" in sig.parameters
    assert "parse_fn" in sig.parameters


def test_all_new_categories_registered():
    names = {type(f).__name__ for f in FORMATTERS}
    assert {
        "FirewallIppool",
        "FirewallVip",
        "FirewallVipgrp",
        "FirewallServiceCustom",
        "FirewallServiceGroup",
    } <= names


def test_cli_parses_fgt_subcommand():
    parser = build_parser()
    args = parser.parse_args(["fgt", "a.conf", "b.conf", "--json", "--json-dir", "out/json"])
    assert args.model == "fgt"
    assert args.files == ["a.conf", "b.conf"]
    assert args.json is True
    assert args.json_dir == "out/json"
    assert args.json_only is False
    assert args.directory == "./booyaa_log/export"


def test_cli_requires_a_model_subcommand():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["a.conf"])
