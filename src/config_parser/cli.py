# cli.py
#
# config_parser: NW機器コンフィグをExcel/JSONへ変換するCLIエントリポイント
# (2026-09-26新規実装)。
#
# config_backup/net_configと同様、サブコマンドで対象の機器ファミリーを
# 指定する(`config_parser fgt <file>`、"モデル指定方法"をこうぢさんの
# 依頼通り揃えた)。将来Alaxala等を追加する場合はbuild_parser()に
# 新しいサブコマンドを追加していく想定(既存サブコマンドの引数には影響しない)。
#
# 実際の変換処理はcore/pipeline.py・ftnt/fos/__init__.pyのprocess_file()に
# 委譲しているため、本モジュールを経由せず
# `from config_parser.ftnt.fos import process_file` を直接importして
# 他スクリプトから使うこともできる(こうぢさんの依頼「他のスクリプトから
# インポートできるようにしておく」への対応)。
#
# `./bin`シムの起動方式(`python -m <モジュール>`)に合わせ、本モジュールは
# `if __name__ == '__main__':`からmain()を呼び出せるようにしてある。
from __future__ import annotations

import argparse
import sys
from textwrap import dedent

from rich.console import Console
from rich.table import Table

from config_parser.ftnt.fos import process_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="config_parser",
        description="NW機器コンフィグをExcelパラメータシートへ変換するツール",
    )
    subparsers = parser.add_subparsers(dest="model", required=True)

    _add_fgt_subcommand(subparsers)

    return parser


def _add_fgt_subcommand(subparsers) -> None:
    msg = dedent("""\
        ~~~ FortiGate / FortiSwitch(Managed Switch) Config -> Excel/JSON ~~~
        ## 単体指定(Excel出力のみ、既定)
        config_parser fgt backup01.conf

        ## 複数ファイルをまとめて変換
        config_parser fgt backup01.conf backup02.conf backup03.conf

        ## Excelに加えてJSONも出力する
        config_parser fgt backup01.conf --json

        ## JSONのみ出力する(Excelは出力しない、--jsonの指定は不要)
        config_parser fgt backup01.conf --json-only

        ## 出力先ディレクトリを変更(既定: ./booyaa_log/export)
        config_parser fgt backup01.conf -d ./out

        ## JSON出力先だけ別ディレクトリにする(既定: -d/--directoryと同じ)
        config_parser fgt backup01.conf --json --json-dir ./out/json

        マルチvdom構成の場合:
          - Excel出力は1ブックにまとめ、シートはvdom単位でグルーピングする
            (root系のシートをまとめて、続けてvdomごとのシートをまとめる)。
          - JSON出力はスコープ(global用 + vdom名ごと)単位でファイルを分割する
            (novdomの場合はglobal用+root用の計2ファイルになる)。
    """)

    p = subparsers.add_parser(
        "fgt",
        help="FortiGate/FortiSwitch(Managed Switch)のコンフィグをExcel/JSONへ変換",
        description=msg,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("files", nargs="+", metavar="FILE", help="変換対象のコンフィグファイル(複数指定可)")
    p.add_argument("-d", "--directory", default="./booyaa_log/export",
                    help="Excel出力先ディレクトリ(既定: ./booyaa_log/export)")
    p.add_argument("--json", action="store_true", help="Excelに加えてJSONも出力する")
    p.add_argument("--json-dir", metavar="DIR",
                    help="JSON出力先ディレクトリ(既定: -d/--directoryと同じ)")
    p.add_argument("--json-only", action="store_true",
                    help="JSONのみ出力し、Excelは出力しない(--jsonの指定は不要)")
    p.set_defaults(handler=_handle_fgt)


def _handle_fgt(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    console = Console()
    table = Table(title="config_parser fgt")
    table.add_column("File", style="cyan")
    table.add_column("Hostname", style="cyan")
    table.add_column("Excel", style="green")
    table.add_column("JSON", style="green")
    table.add_column("Message", style="white")

    ok_all = True
    for file_path in args.files:
        try:
            result = process_file(
                file_path,
                export_dir=args.directory,
                json_output=args.json,
                json_dir=args.json_dir,
                json_only=args.json_only,
            )
            excel_txt = str(result.excel_path) if result.excel_path else "-"
            json_txt = "\n".join(str(p) for p in result.json_paths) if result.json_paths else "-"
            table.add_row(file_path, result.hostname, excel_txt, json_txt, "[green]OK[/]")
        except Exception as e:  # noqa: BLE001 - CLIとしてはエラー内容をそのままMessage列に出す
            ok_all = False
            table.add_row(file_path, "-", "-", "-", f"[red]{e}[/]")

    console.print(table)
    return 0 if ok_all else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error(f"unsupported model: {args.model}")
        return 2

    try:
        return handler(args, parser)
    except KeyboardInterrupt:
        # config_backupと同様、Ctrl+C時はtracebackを出さず終了コード130で終了する。
        Console().print("\n[yellow]Interrupted by user.[/]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
