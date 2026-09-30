"""Publica no Instagram @congoapp_ os posts da fila (posts/fila/*.json).

Cada JSON da fila:
  feed : {"tipo":"feed","imagem":"posts/fila/X.jpg","legenda":"...","criado_em":epoch}
  story: {"tipo":"story","imagem":"posts/fila/X.jpg","criado_em":epoch}
  reels: {"tipo":"reels","video":"posts/fila/X.mp4","capa":"posts/fila/X.jpg" (opcional),
          "legenda":"...","narracao":"texto falado" (opcional, ElevenLabs),"criado_em":epoch}

Usa a API oficial do Instagram (login do Instagram), host graph.instagram.com.
Segredos exigidos no GitHub: IG_TOKEN e IG_USER_ID.
"""
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://graph.instagram.com/v21.0"
REPO = os.environ.get("GITHUB_REPOSITORY", "wmatheuslacerda/congoapp-posts")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
TOKEN = os.environ["IG_TOKEN"].strip().strip("\"'")
IG_USER_ID = os.environ["IG_USER_ID"].strip()

FILA = Path("posts/fila")
PUBLICADOS = Path("posts/publicados")


def chamar(metodo, caminho, params):
    params = {**params, "access_token": TOKEN}
    dados = urllib.parse.urlencode(params).encode()
    url = f"{API}/{caminho}"
    if metodo == "GET":
        req = urllib.request.Request(f"{url}?{dados.decode()}")
    else:
        req = urllib.request.Request(url, data=dados, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{metodo} {caminho} -> {e.code}: {e.read().decode()}")


def raw(caminho):
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{caminho}"


def publicar(post):
    """tipo: "feed" (padrão, imagem), "story" (imagem 9:16) ou "reels" (vídeo 9:16)."""
    tipo = post.get("tipo", "feed")
    if tipo == "reels":
        params = {"media_type": "REELS", "video_url": raw(post["video"]),
                  "caption": post.get("legenda", ""), "share_to_feed": "true"}
        if post.get("capa"):
            params["cover_url"] = raw(post["capa"])
        tentativas, pausa = 60, 5  # vídeo leva mais para processar
    elif tipo == "story":
        params = {"media_type": "STORIES", "image_url": raw(post["imagem"])}
        tentativas, pausa = 20, 3
    else:
        params = {"image_url": raw(post["imagem"]), "caption": post["legenda"]}
        tentativas, pausa = 20, 3
    container = chamar("POST", f"{IG_USER_ID}/media", params)["id"]

    for _ in range(tentativas):
        status = chamar("GET", container, {"fields": "status_code"})["status_code"]
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram recusou a mídia ({tipo})")
        time.sleep(pausa)

    midia = chamar("POST", f"{IG_USER_ID}/media_publish", {"creation_id": container})["id"]
    try:
        return chamar("GET", midia, {"fields": "permalink"}).get("permalink") or f"story:{midia}"
    except RuntimeError:
        return f"{tipo}:{midia}"


def mover_arquivos(post, destino):
    for campo in ("imagem", "video", "capa"):
        if post.get(campo) and Path(post[campo]).exists():
            novo = destino / Path(post[campo]).name
            shutil.move(post[campo], novo)
            post[campo] = str(novo)


def main():
    PUBLICADOS.mkdir(parents=True, exist_ok=True)
    arquivos = sorted(FILA.glob("*.json"))
    if not arquivos:
        print("Fila vazia.")
        return
    falhou = False
    descartes = Path("posts/descartados")
    for arq in arquivos:
        post = json.loads(arq.read_text(encoding="utf-8"))
        # Evita rajada: post com "criado_em" (epoch UTC) há mais de 3h é descartado, não publicado.
        if time.time() - post.get("criado_em", time.time()) > 3 * 3600 and not post.get("forcar"):
            descartes.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arq), descartes / arq.name)
            mover_arquivos(post, descartes)
            print(f"Descartado (antigo): {arq.name}")
            continue
        try:
            link = publicar(post)
            post["publicado_em"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            post["link"] = link
            print(f"Publicado: {link}")
            mover_arquivos(post, PUBLICADOS)
            (PUBLICADOS / arq.name).write_text(
                json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
            arq.unlink()
        except Exception as e:  # registra o erro e segue para o próximo
            falhou = True
            print(f"ERRO em {arq.name}: {e}", file=sys.stderr)
    if falhou:
        sys.exit(1)


if __name__ == "__main__":
    main()
