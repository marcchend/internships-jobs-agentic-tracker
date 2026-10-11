"""Transforme le texte d'une lettre (sortie de read_file_content d'un Google Doc) en PDF d'une page.

Usage : python3 lettre_pdf.py lettre.txt sortie.pdf   (navigateur : variable CHROME, sinon détecté)

Le texte attendu : paragraphes séparés par des lignes vides, **gras** en Markdown.
Les lignes avant la date (« Paris, le ... » ou « Paris, 10 October ... ») forment l'en-tête
et les coordonnées du destinataire ; elles sont regroupées sans espace entre elles.
"""
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Chromium ou Chrome : variable CHROME si elle est définie, sinon le Chromium du conteneur Claude,
# sinon le premier navigateur trouvé dans le PATH.
CHROME = os.environ.get("CHROME") or next(
    (p for p in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome", shutil.which("chromium"),
                 shutil.which("chromium-browser"), shutil.which("google-chrome"), shutil.which("chrome"))
     if p and os.path.exists(p)),
    "chromium",
)
DATE_LINE = re.compile(r"^Paris, (le )?\d")


def to_html(text: str) -> str:
    text = text.replace("\\+", "+").replace("\\-", "-")
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    date_idx = next((i for i, p in enumerate(paras) if DATE_LINE.match(p)), None)

    def fmt(p: str) -> str:
        p = html.escape(p)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p).replace("\n", "<br>")

    blocks = []
    if date_idx is not None and date_idx >= 4:
        sender, recipient = paras[:4], paras[4:date_idx]
        blocks.append("<p>" + "<br>".join(fmt(p) for p in sender) + "</p>")
        if recipient:
            blocks.append("<p>" + "<br>".join(fmt(p) for p in recipient) + "</p>")
        rest = paras[date_idx:]
    else:
        rest = paras
    blocks += [f"<p>{fmt(p)}</p>" for p in rest]
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "@page{size:A4;margin:22mm 22mm}"
        "body{font-family:Arial,Helvetica,sans-serif;font-size:10.5pt;line-height:1.38}"
        "p{margin:0 0 9pt 0}"
        "</style></head><body>" + "\n".join(blocks) + "</body></html>"
    )


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "lettre.html"
        page.write_text(to_html(src.read_text(encoding="utf-8")), encoding="utf-8")
        subprocess.run(
            [CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", page.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
    print(f"{out} ({out.stat().st_size} octets)")


if __name__ == "__main__":
    main()
