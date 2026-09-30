"""Gera um Reels (motion) 1080x1920 da CongoApp, 30 fps, sem áudio.

Uso:
  python3 scripts/reel.py saida.mp4 '{"cenas":[
      {"texto":"ABRIU A|GELADEIRA|*DE NOVO?*","fundo":"preto","dur":2.6},
      {"texto":"E NADA|*MUDOU.*","fundo":"amarelo","dur":2.2}
  ],"assinatura":"Pediu, chegou.","chamada":"Acesse pelo link do perfil"}'

- Cada cena: linhas separadas por "|", destaque entre *asteriscos*, fundo "preto" ou "amarelo".
- A última cena (marca + chamada) é adicionada automaticamente.
- Movimento: linhas sobem por trás de máscara (easeOutExpo, escalonadas),
  "respiração" de câmera, corte com varredura amarela entre cenas, grão por cima.
- Áudio (narração) é mixado depois, no GitHub Actions (scripts/preparar_midia.py),
  porque a nuvem do Claude não baixa arquivos do Higgsfield.
"""
import html
import json
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card import AMARELO, PRETO, GRAO, fonte  # noqa: E402

FPS = 30
W, H = 1080, 1920
DUR_FINAL = 2.8
TRANS = 0.28  # duração da varredura entre cenas


def linhas_html(texto, cor_destaque):
    out = []
    for i, l in enumerate(texto.split("|")):
        l = html.escape(l)
        l = re.sub(r"\*(.+?)\*", rf'<span style="color:{cor_destaque}">\1</span>', l)
        out.append(f'<div class="mask"><div class="ln" data-i="{i}">{l}</div></div>')
    return "".join(out)


def montar_pagina(dados):
    cenas = dados["cenas"]
    blocos = []
    for c in cenas:
        amarelo = c.get("fundo") == "amarelo"
        fundo, cor, dest = (AMARELO, PRETO, "#FFFFFF") if amarelo else (PRETO, "#F4F1EA", AMARELO)
        tam = c.get("tam", 170)
        blocos.append(
            f'<section class="cena" style="background:{fundo};color:{cor}">'
            f'<div class="cam"><div class="kick" style="color:{cor};opacity:.55">{html.escape(c.get("kicker", "Congonhinhas · PR"))}</div>'
            f'<div class="tit" style="font-size:{tam}px">{linhas_html(c["texto"], dest)}</div></div></section>'
        )
    assinatura = html.escape(dados.get("assinatura", "Pediu, chegou."))
    chamada = html.escape(dados.get("chamada", "Acesse pelo link do perfil"))
    blocos.append(
        f'<section class="cena final" style="background:{AMARELO};color:{PRETO}"><div class="cam">'
        f'<div class="logo"><div class="mask"><div class="ln" data-i="0">congo<span style="color:#fff">app</span></div></div></div>'
        f'<div class="ass"><div class="mask"><div class="ln" data-i="1">{assinatura}</div></div></div>'
        f'<div class="cta"><div class="mask"><div class="ln" data-i="2"><b>{chamada} ↑</b></div></div></div>'
        f'</div></section>'
    )
    durs = [float(c.get("dur", 2.4)) for c in cenas] + [DUR_FINAL]
    css = f"""
    @font-face{{font-family:Anton;src:url(data:font/woff2;base64,{fonte('anton-latin-400-normal.woff2')})}}
    @font-face{{font-family:Inter;font-weight:500;src:url(data:font/woff2;base64,{fonte('inter-latin-500-normal.woff2')})}}
    @font-face{{font-family:Inter;font-weight:900;src:url(data:font/woff2;base64,{fonte('inter-latin-900-normal.woff2')})}}
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{width:{W}px;height:{H}px;overflow:hidden;background:{PRETO};position:relative}}
    .cena{{position:absolute;inset:0;display:none}}
    .cam{{position:absolute;inset:0;transform-origin:30% 45%}}
    .kick{{position:absolute;left:84px;top:560px;font-family:Inter;font-weight:900;font-size:32px;letter-spacing:4px;text-transform:uppercase}}
    .tit{{position:absolute;left:78px;right:60px;top:650px;font-family:Anton;text-transform:uppercase;line-height:1.0;letter-spacing:-1px}}
    .mask{{overflow:hidden;padding-top:.06em}}
    .ln{{will-change:transform}}
    .final .logo{{position:absolute;left:84px;top:700px;font-family:Inter;font-weight:900;font-size:190px;letter-spacing:-8px;line-height:1}}
    .final .ass{{position:absolute;left:88px;top:930px;font-family:Anton;font-size:120px;text-transform:uppercase}}
    .final .cta{{position:absolute;left:88px;right:88px;top:1170px;font-family:Inter;font-size:46px;letter-spacing:1px;text-transform:uppercase}}
    .wipe{{position:absolute;left:0;right:0;height:{H}px;background:{AMARELO};z-index:40;transform:translateY(100%)}}
    .grao{{position:absolute;inset:0;background-image:{GRAO};opacity:.10;mix-blend-mode:multiply;z-index:50}}
    """
    js = f"""
    const DURS={json.dumps(durs)}, TR={TRANS};
    const cenas=[...document.querySelectorAll('.cena')];
    const wipe=document.querySelector('.wipe');
    const expo=t=>t>=1?1:1-Math.pow(2,-10*t);
    const clamp=t=>Math.max(0,Math.min(1,t));
    window.TOTAL=DURS.reduce((a,b)=>a+b,0);
    window.setTime=function(t){{
      let ini=0, idx=DURS.length-1;
      for(let i=0;i<DURS.length;i++){{ if(t<ini+DURS[i]){{idx=i;break;}} ini+=DURS[i]; }}
      const lt=t-ini;
      cenas.forEach((c,i)=>c.style.display=i===idx?'block':'none');
      const cena=cenas[idx];
      // respiração de câmera
      const k=lt/DURS[idx];
      cena.querySelector('.cam').style.transform=`scale(${{1+0.045*k}}) translateY(${{-10*k}}px)`;
      // linhas entrando por trás da máscara
      cena.querySelectorAll('.ln').forEach(el=>{{
        const i=+el.dataset.i, p=expo(clamp((lt-0.08-i*0.11)/0.55));
        el.style.transform=`translateY(${{(1-p)*110}}%)`;
      }});
      const kick=cena.querySelector('.kick'); if(kick) kick.style.transform=`translateX(${{(1-expo(clamp(lt/0.5)))*-40}}px)`;
      // varredura amarela no fim de cada cena (menos a última)
      const fim=DURS[idx]-lt;
      if(idx<DURS.length-1 && fim<TR){{ const p=1-fim/TR; wipe.style.transform=`translateY(${{(1-expo(p))*100}}%)`; }}
      else if(idx>0 && lt<TR){{ const p=lt/TR; wipe.style.transform=`translateY(${{-expo(p)*100}}%)`; }}
      else wipe.style.transform='translateY(100%)';
    }};
    """
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(blocos)}<div class='wipe'></div><div class='grao'></div><script>{js}</script></body></html>"


def gerar(saida, dados):
    pagina = montar_pagina(dados)
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pg = nav.new_page(viewport={"width": W, "height": H})
        pg.set_content(pagina)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        total = pg.evaluate("window.TOTAL")
        n = int(total * FPS)
        ff = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(saida)],
            stdin=subprocess.PIPE)
        for f in range(n):
            pg.evaluate(f"window.setTime({f / FPS})")
            ff.stdin.write(pg.screenshot(type="jpeg", quality=92))
        ff.stdin.close()
        ff.wait()
        nav.close()
    if ff.returncode != 0:
        raise SystemExit("ffmpeg falhou")
    return total


if __name__ == "__main__":
    saida, arg = sys.argv[1], sys.argv[2]
    dados = json.loads(Path(arg).read_text(encoding="utf-8")) if arg.endswith(".json") else json.loads(arg)
    dur = gerar(saida, dados)
    print(f"ok {saida} {dur:.1f}s")
