# core/excel/font.py (旧 export/excel_font_change.py)
#
# openpyxlはExcelのテーマフォント(日本語用フォント)を直接は変更できないため、
# 保存後に.xlsx(=zip)内のtheme1.xmlを直接書き換える。ロジックはレイアウト
# dispatchの再設計と無関係のため、旧実装からほぼそのまま移設。
from __future__ import annotations

import zipfile
from pathlib import Path
from shutil import make_archive
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

_THEME_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def set_japanese_font(book_path: Path, font: str = "Yu Gothic UI") -> None:
    with TemporaryDirectory() as td:
        with zipfile.ZipFile(book_path, "r") as zip_ref:
            zip_ref.extractall(td)

        styles_path = Path(td, "xl", "theme", "theme1.xml")
        tree = ET.parse(styles_path)
        root = tree.getroot()

        for font_el in root.findall(".//a:font[@script='Jpan']", _THEME_NS):
            font_el.set("typeface", font)

        tree.write(styles_path, encoding="utf-8", xml_declaration=True)

        make_archive(base_name=str(book_path), format="zip", root_dir=td)
        Path(f"{book_path}.zip").replace(book_path)
