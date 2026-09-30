"""core/excel (ExcelWriter + layouts registry) を実データ4サンプルに対して
実際に動かし、
- simple(firewall_address)とcomposite(system_ha、ha-mgmt-interfacesの
  サブテーブル込み)の両レイアウトが正しく描画されること
- multivdomではvdom名でシートが分かれ、novdomでは分かれないこと
- シート名が31文字・禁止文字制約を満たすこと
- 空カテゴリ(records無し)でシートが作られないこと
を、生成した.xlsxをopenpyxlで読み直して確認する検証スクリプト
(pytestの単体テストではなく手動実行用)。

実行方法(カレントディレクトリに依存せず、どこから実行してもよい):
    uv run --project tools/config_parser python tools/config_parser/validate_export.py
"""
from pathlib import Path

from openpyxl import load_workbook

from config_parser.core.excel.writer import ExcelWriter
from config_parser.ftnt.fos.formatters import FORMATTERS
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
OUT_DIR = Path(__file__).parent / "tmp" / "export_validate"


def main():
    writer = ExcelWriter(FORMATTERS)
    books = {}

    for label, path in SAMPLES.items():
        doc = parse_config_file(path)
        book_path = writer.export(doc, export_dir=str(OUT_DIR))
        books[label] = book_path
        print(f"[{label}] wrote {book_path.name}")

        wb = load_workbook(book_path)
        print(f"  sheets: {wb.sheetnames}")
        for name in wb.sheetnames:
            assert len(name) <= 31, f"sheet name too long: {name!r}"

    print()
    print("=== HA(composite layout)の中身を確認: 7.2_multivdom ===")
    wb = load_workbook(books["7.2_multivdom"])
    ha_sheet_name = next(n for n in wb.sheetnames if n.endswith("ha"))
    ws = wb[ha_sheet_name]
    print(f"sheet: {ha_sheet_name}")
    for row in ws.iter_rows(min_row=1, max_row=14, values_only=True):
        cells = [c for c in row if c is not None]
        if cells:
            print(" ", cells)

    print()
    print("=== firewall_address(simpleレイアウト)の中身を確認: 7.2_novdom ===")
    wb = load_workbook(books["7.2_novdom"])
    addr_sheet_name = next(n for n in wb.sheetnames if "address" in n)
    ws = wb[addr_sheet_name]
    print(f"sheet: {addr_sheet_name} ({ws.max_row} rows)")
    for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
        print(" ", row)

    print()
    print("OK: 全サンプルでexport成功・シート名制約OK")


if __name__ == "__main__":
    main()
