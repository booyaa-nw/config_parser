#!/usr/bin/env python3
"""FortiOS(fos) config parser -- LARK たたき台

段階1(Lex/Parse)を Lark で行い、Transformer でそのまま
段階2(materialize)相当の「素直な入れ子dict」まで組み立てる。

出力形状のイメージ(architecture/config-parser-design.md 参照):
    {
      "header": {...},
      "root": {...}                      # novdom (単一vdom)の場合
    }
  もしくは
    {
      "header": {...},
      "vdom": [{"root": {...}}, {"ext-vdom": {...}}],
      "global": {...}
    }
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from lark import Lark, Transformer, v_args

GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


def _unquote(s: str) -> str:
    """STRING トークン("...")の中身を取り出す(エスケープを軽く解除)。"""
    inner = s[1:-1]
    return re.sub(r"\\(.)", r"\1", inner)


class FosTransformer(Transformer):
    """Larkのパース木を、カテゴリ名キー・edit名キー・setは値のlist、という
    現行 config_obj 相当の入れ子dictへ変換する。
    """

    # --- 終端トークン -------------------------------------------------
    def STRING(self, tok):
        return _unquote(str(tok))

    def BARE(self, tok):
        return str(tok)

    def HEADER_LINE(self, tok):
        return str(tok)

    # --- 値・名前 -------------------------------------------------
    def value(self, children):
        return children[0]

    def name_part(self, children):
        return children[0]

    # --- header --------------------------------------------------
    def header_line(self, children):
        return children[0]

    # --- 文 ------------------------------------------------------
    def set_stmt(self, children):
        key = children[0]
        values = list(children[1:])
        return (key, values)

    def unset_stmt(self, children):
        key = children[0]
        return (key, None)

    def edit_stmt(self, children):
        # children: [value(edit名), *body items]
        name = children[0]
        body_items = children[1:]
        record = _fold_body(body_items)
        return {name: record}

    def config_stmt(self, children):
        # children: [name_part*, *body items] -- name_part は value と同じ文字列
        # name_part の数は可変なので、"config" の後に来る素の文字列トークンを
        # 先頭からできるだけ集め、残りを body として扱う。
        names = []
        idx = 0
        for c in children:
            if isinstance(c, str):
                names.append(c)
                idx += 1
            else:
                break
        body_items = children[idx:]
        category = "_".join(names)

        edit_dicts = [b for b in body_items if isinstance(b, dict)]
        kv_items = [b for b in body_items if isinstance(b, tuple)]

        if edit_dicts and not kv_items:
            # 複数entry(edit)を持つカテゴリ -> list
            value = edit_dicts
        elif kv_items and not edit_dicts:
            # setのみ、または"config"入れ子(単一)のみ -> dict
            value = _fold_body(kv_items)
        elif not edit_dicts and not kv_items:
            value = {}
        else:
            # 実データでは基本発生しない想定(setとeditが同居)だが、
            # 念のため両方保持しておく。
            value = {"__mixed_kv__": _fold_body(kv_items), "__mixed_edit__": edit_dicts}

        return (category, value)

    def stmt(self, children):
        return children[0]

    def start(self, children):
        header_lines = [c for c in children if isinstance(c, str) and c.startswith("#")]
        body_items = [c for c in children if isinstance(c, tuple)]
        doc = _fold_body(body_items)
        doc["header"] = parse_header(header_lines)
        return doc


def _fold_body(items):
    """(key, value) タプルの列を1つのdictにマージする。"""
    out = {}
    for key, value in items:
        if key in out:
            # 同名カテゴリ/キーの重複(実データでは想定外だが検知できるようにしておく)
            existing = out[key]
            if isinstance(existing, list) and isinstance(value, list):
                existing.extend(value)
            else:
                out.setdefault("__duplicate__", []).append((key, value))
        else:
            out[key] = value
    return out


def parse_header(header_lines: list[str]) -> dict:
    """先頭4行程度の '#'始まりヘッダ行をdictにする。

    例:
        #config-version=FGT60F-7.2.10-FW-build1706-240918:opmode=0:vdom=1:user=admin
        #conf_file_ver=494458110067093
        #buildno=1706
        #global_vdom=1
    """
    header: dict = {}
    for line in header_lines:
        body = line.lstrip("#")
        for part in body.split(":"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            header[k.strip()] = v.strip()

    if "config-version" in header:
        # FGT60F-7.2.10-FW-build1706-240918
        m = re.match(r"^(?P<model>[^-]+)-(?P<version>\d+\.\d+\.\d+)-.*-build(?P<build>\d+)-\d+$",
                      header["config-version"])
        if m:
            header["model"] = m.group("model")
            header["version"] = m.group("version")
            header["build_num"] = m.group("build")

    for int_key in ("opmode", "vdom", "global_vdom", "conf_file_ver", "buildno"):
        if int_key in header:
            try:
                header[int_key] = int(header[int_key])
            except ValueError:
                pass

    return header


def materialize(doc: dict) -> dict:
    """トップレベルの生dict(configカテゴリの集合)を、
    header/global/vdom(または header/root)の形に整理する。
    """
    header = doc.pop("header", {})
    out = {"header": header}

    if "vdom" in doc and isinstance(doc["vdom"], list):
        # config vdom (vdom一覧宣言) が edit/next の形で見えている場合、
        # そのまま vdom名の列として扱う。
        # 実データでは「vdom一覧宣言」と「各vdomの実データ」の両方が
        # トップレベルの "vdom" キーに畳み込まれてしまうため、
        # ここでは "各vdomの実データ" (setやconfigの中身を持つ方) を
        # 優先して残す。
        merged: dict[str, dict] = {}
        order: list[str] = []
        for entry in doc["vdom"]:
            for name, value in entry.items():
                if name not in merged:
                    merged[name] = {}
                    order.append(name)
                if isinstance(value, dict) and value:
                    merged[name] = value
        out["vdom"] = [{name: merged[name]} for name in order]
        doc.pop("vdom")

    if "global" in doc:
        out["global"] = doc.pop("global")

    # 残り(vdom/global以外)は root 直下(novdom)として扱う
    if doc:
        out["root"] = doc

    return out


_parser = None


def get_parser() -> Lark:
    global _parser
    if _parser is None:
        _parser = Lark(GRAMMAR_PATH.read_text(encoding="utf-8"), start="start", parser="lalr")
    return _parser


def parse_config_text(text: str) -> dict:
    if not text.endswith("\n"):
        text += "\n"
    tree = get_parser().parse(text)
    doc = FosTransformer().transform(tree)
    return materialize(doc)


def parse_config_file(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8-sig")
    return parse_config_text(text)


if __name__ == "__main__":
    path = sys.argv[1]
    t0 = time.time()
    result = parse_config_file(path)
    elapsed = time.time() - t0
    print(f"parsed {path} in {elapsed:.2f}s", file=sys.stderr)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
