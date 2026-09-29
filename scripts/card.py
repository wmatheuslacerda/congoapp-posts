"""Gera o card 1080x1350 (4:5) da CongoApp.

Uso:
  python3 scripts/card.py saida.jpg "LINHA 1|LINHA 2|*DESTAQUE*" "Texto de apoio" "Selo"

- Linhas separadas por "|". Palavra ou linha entre *asteriscos* sai em amarelo.
- Identidade: fundo preto, amarelo #FFB400, caixa alta pesada, rodapé com @congoapp_.
"""
import html
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

AMARELO = "#FFB400"


def marcar(texto):
    texto = html.escape(texto)
    return re.sub(r"\*(.+?)\*", rf'<span style="color:{AMARELO}">\1</span>', texto)


def gerar(saida, titulo, apoio="", selo=""):
    linhas = "".join(f"<div>{marcar(l)}</div>" for l in titulo.split("|"))
    pagina = f"""<!doctype html><html><head><meta charset="utf-8"><style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{width:1080px;height:1350px;background:#0B0B0B;color:#fff;
      font-family:"Liberation Sans",Arial,sans-serif;position:relative;overflow:hidden}}
    .faixa{{position:absolute;left:0;top:0;width:1080px;height:22px;background:{AMARELO}}}
    .selo{{position:absolute;left:88px;top:120px;background:{AMARELO};color:#0B0B0B;
      font-weight:700;font-size:34px;padding:12px 26px;border-radius:40px;letter-spacing:1px;
      text-transform:uppercase}}
    .titulo{{position:absolute;left:88px;right:88px;top:300px;font-weight:700;
      font-size:108px;line-height:1.02;letter-spacing:-3px;text-transform:uppercase}}
    .apoio{{position:absolute;left:88px;right:88px;bottom:250px;font-size:44px;
      line-height:1.3;color:#D9D9D9}}
    .rodape{{position:absolute;left:88px;right:88px;bottom:96px;display:flex;
      justify-content:space-between;align-items:center;font-size:38px}}
    .marca{{font-weight:700;font-size:56px;letter-spacing:-1px}}
    .marca span{{color:{AMARELO}}}
    .user{{color:#9A9A9A}}
    </style></head><body>
    <div class="faixa"></div>
    {f'<div class="selo">{html.escape(selo)}</div>' if selo else ''}
    <div class="titulo">{linhas}</div>
    {f'<div class="apoio">{marcar(apoio)}</div>' if apoio else ''}
    <div class="rodape"><div class="marca">congo<span>APP</span></div><div class="user">@congoapp_</div></div>
    </body></html>"""
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": 1080, "height": 1350})
        pg.set_content(pagina)
        pg.screenshot(path=str(saida), type="jpeg", quality=92)
        nav.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    Path(args[0]).parent.mkdir(parents=True, exist_ok=True)
    gerar(args[0], args[1], args[2] if len(args) > 2 else "", args[3] if len(args) > 3 else "")
