"""Gera cards 1080x1350 (4:5) da CongoApp com acabamento editorial.

Uso (JSON na linha de comando ou arquivo):
  python3 scripts/card.py saida.jpg '{"layout":"amarelo","kicker":"...","titulo":"LINHA|LINHA|*DESTAQUE*","apoio":"...","faixa":"PEDIU, CHEGOU"}'

Layouts:
  amarelo  - fundo amarelo da marca, tipografia preta gigante
  noite    - fundo preto, faixa amarela diagonal (fita) com texto repetido
  pergunta - fundo preto, pergunta enorme + resposta em bloco amarelo

Regras de estilo (não mudar sem motivo):
  - Anton (condensada) só para o título, Inter para o resto
  - uma cor de destaque: amarelo #FFB800 sobre preto #0E0E0E
  - grão sutil em tudo (tira o aspecto "digital limpo" de IA)
  - alinhamento à esquerda, margem 80px, nada centralizado
"""
import base64
import html
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "assets" / "fonts"
LOGO = RAIZ / "assets" / "logo.png"  # opcional: mascote/logo oficial

AMARELO = "#FFB800"
PRETO = "#0E0E0E"


def fonte(nome):
    return base64.b64encode((FONTES / nome).read_bytes()).decode()


def marcar(texto, cor):
    texto = html.escape(texto)
    return re.sub(r"\*(.+?)\*", rf'<span style="color:{cor}">\1</span>', texto)


GRAO = (
    "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
    "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 .55 0'/></filter>"
    "<rect width='100%' height='100%' filter='url(%23n)'/></svg>\")"
)


def css_base():
    return f"""
    @font-face{{font-family:Anton;src:url(data:font/woff2;base64,{fonte('anton-latin-400-normal.woff2')})}}
    @font-face{{font-family:Inter;font-weight:500;src:url(data:font/woff2;base64,{fonte('inter-latin-500-normal.woff2')})}}
    @font-face{{font-family:Inter;font-weight:700;src:url(data:font/woff2;base64,{fonte('inter-latin-700-normal.woff2')})}}
    @font-face{{font-family:Inter;font-weight:900;src:url(data:font/woff2;base64,{fonte('inter-latin-900-normal.woff2')})}}
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{width:1080px;height:1350px;position:relative;overflow:hidden;font-family:Inter}}
    .grao{{position:absolute;inset:0;background-image:{GRAO};opacity:.09;mix-blend-mode:multiply;pointer-events:none;z-index:50}}
    .meta{{position:absolute;left:80px;right:80px;top:72px;display:flex;justify-content:space-between;
      font-weight:700;font-size:24px;letter-spacing:3px;text-transform:uppercase}}
    .titulo{{font-family:Anton;text-transform:uppercase;line-height:.96;letter-spacing:-1px}}
    .rodape{{position:absolute;left:80px;right:80px;bottom:72px;display:flex;justify-content:space-between;
      align-items:flex-end;font-weight:700;font-size:26px;letter-spacing:1px}}
    .marca{{font-family:Inter;font-weight:900;font-size:46px;letter-spacing:-2px;text-transform:lowercase}}
    .regra{{position:absolute;left:80px;right:80px;height:3px}}
    """


HORA = re.compile(r"\b\d{1,2}\s*(h|hs|:\d{2})\b|\b(das|às|as)\s+\d{1,2}\b", re.I)


def kicker(d, padrao):
    """Nunca mostra horário no card: o post pode sair em outro minuto."""
    k = d.get("kicker") or padrao
    return padrao if HORA.search(k) else k


def logo_html(tam):
    if LOGO.exists():
        b = base64.b64encode(LOGO.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{b}" style="height:{tam}px;display:block">'
    return ""


def layout_amarelo(d):
    titulo = "".join(f"<div>{marcar(l, '#fff')}</div>" for l in d["titulo"].split("|"))
    return f"""
    <style>body{{background:{AMARELO};color:{PRETO}}}
    .titulo{{position:absolute;left:74px;right:60px;top:210px;font-size:{d.get('tam',172)}px}}
    .regra{{background:{PRETO};bottom:250px}}
    .apoio{{position:absolute;left:80px;width:640px;bottom:290px;font-weight:500;font-size:38px;line-height:1.28}}
    .seta{{position:absolute;right:80px;bottom:292px;width:118px;height:118px;border-radius:50%;background:{PRETO};
      color:{AMARELO};display:flex;align-items:center;justify-content:center;font-size:58px;font-weight:900}}</style>
    <div class="meta"><span>{html.escape(kicker(d, 'Congonhinhas · PR'))}</span><span></span></div>
    <div class="titulo">{titulo}</div>
    <div class="apoio">{marcar(d.get('apoio',''), '#fff')}</div>
    <div class="seta">→</div>
    <div class="regra"></div>
    <div class="rodape"><div>{logo_html(64) or '<div class="marca">congoapp</div>'}</div><div>@congoapp_</div></div>
    """


def layout_noite(d):
    titulo = "".join(f"<div>{marcar(l, AMARELO)}</div>" for l in d["titulo"].split("|"))
    faixa = html.escape(d.get("faixa", "PEDIU, CHEGOU"))
    repet = (f"<span>{faixa}</span><b>✦</b>" * 12)
    return f"""
    <style>body{{background:{PRETO};color:#F4F1EA}}
    .titulo{{position:absolute;left:74px;right:60px;top:190px;font-size:{d.get('tam',176)}px}}
    .fita{{position:absolute;left:-120px;width:1400px;top:{d.get('fita_top',860)}px;height:104px;background:{AMARELO};
      transform:rotate(-6deg);display:flex;align-items:center;gap:26px;white-space:nowrap;overflow:hidden;
      font-family:Anton;font-size:56px;color:{PRETO};letter-spacing:1px;box-shadow:0 18px 40px rgba(0,0,0,.45)}}
    .fita b{{font-size:34px}}
    .apoio{{position:absolute;left:80px;width:760px;bottom:170px;font-weight:500;font-size:36px;line-height:1.3;color:#CFCBC2}}
    .meta{{color:#8C8880}}.rodape{{color:#8C8880}}.marca{{color:#F4F1EA}}</style>
    <div class="meta"><span>{html.escape(kicker(d, 'Congonhinhas · PR'))}</span><span></span></div>
    <div class="titulo">{titulo}</div>
    <div class="fita">{repet}</div>
    <div class="apoio">{marcar(d.get('apoio',''), AMARELO)}</div>
    <div class="rodape"><div>{logo_html(64) or '<div class="marca">congo<span style="color:'+AMARELO+'">app</span></div>'}</div><div>@congoapp_</div></div>
    """


def layout_pergunta(d):
    titulo = "".join(f"<div>{marcar(l, AMARELO)}</div>" for l in d["titulo"].split("|"))
    return f"""
    <style>body{{background:{PRETO};color:#F4F1EA}}
    .titulo{{position:absolute;left:74px;right:60px;top:200px;font-size:{d.get('tam',150)}px}}
    .resp{{position:absolute;left:80px;right:80px;bottom:200px;background:{AMARELO};color:{PRETO};
      border-radius:28px;padding:44px 48px;font-weight:700;font-size:40px;line-height:1.25}}
    .resp small{{display:block;font-size:22px;letter-spacing:3px;text-transform:uppercase;margin-bottom:14px;opacity:.7}}
    .meta{{color:#8C8880}}.rodape{{color:#8C8880}}.marca{{color:#F4F1EA}}</style>
    <div class="meta"><span>{html.escape(kicker(d, 'Pergunta do dia'))}</span><span></span></div>
    <div class="titulo">{titulo}</div>
    <div class="resp"><small>{html.escape(d.get('rotulo','Resposta'))}</small>{marcar(d.get('apoio',''), '#fff')}</div>
    <div class="rodape"><div>{logo_html(64) or '<div class="marca">congo<span style="color:'+AMARELO+'">app</span></div>'}</div><div>@congoapp_</div></div>
    """


LAYOUTS = {"amarelo": layout_amarelo, "noite": layout_noite, "pergunta": layout_pergunta}


def gerar(saida, dados):
    corpo = LAYOUTS[dados.get("layout", "amarelo")](dados)
    pagina = f"<!doctype html><html><head><meta charset='utf-8'><style>{css_base()}</style></head><body>{corpo}<div class='grao'></div></body></html>"
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": 1080, "height": 1350})
        pg.set_content(pagina)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(200)
        pg.screenshot(path=str(saida), type="jpeg", quality=93)
        nav.close()


if __name__ == "__main__":
    saida, arg = sys.argv[1], sys.argv[2]
    dados = json.loads(Path(arg).read_text(encoding="utf-8")) if arg.endswith(".json") else json.loads(arg)
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    gerar(saida, dados)
