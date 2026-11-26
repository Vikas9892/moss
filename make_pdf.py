import markdown, pathlib, sys
import re
md = pathlib.Path("ONE_PAGER.md").read_text(encoding="utf-8")
md = re.sub(r'(?m)^((?!- |\d\. ).+)\n(?=- |\d\. )', r'\1\n\n', md)  # python-markdown needs a blank line before lists
body = markdown.markdown(md)
css = """@page{size:A4;margin:11mm 13mm}body{font:9.6pt/1.36 Calibri,'Segoe UI',Arial,sans-serif;color:#1a1a1a;margin:0}
h1{font-size:16pt;margin:0 0 2px}h2{font-size:11.5pt;margin:9px 0 2px;padding-bottom:1px;border-bottom:1.5px solid #2f6f4e;color:#2f6f4e}
p{margin:2px 0}ul,ol{margin:1px 0 2px;padding-left:16px}li{margin:0.5px 0}code{font:8.6pt Consolas,monospace;background:#f1f3f2;padding:0 2px;border-radius:2px}"""
pathlib.Path(sys.argv[1]).write_text(f"<!doctype html><meta charset=utf-8><title>Moss review - Vikas Tiwari</title><style>{css}</style>{body}", encoding="utf-8")

