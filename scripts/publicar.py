"""Publica no Instagram @congoapp_ os posts da fila (posts/fila/*.json).

Cada JSON da fila:
{
  "imagem": "posts/fila/2026-09-30-10h07.jpg",
  "legenda": "texto + hashtags",
  "pauta": "almoco"
}

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


def publicar(post):
    imagem_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{post['imagem']}"
    container = chamar("POST", f"{IG_USER_ID}/media",
                       {"image_url": imagem_url, "caption": post["legenda"]})["id"]

    # Espera o Instagram processar a imagem
    for _ in range(20):
        status = chamar("GET", container, {"fields": "status_code"})["status_code"]
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram recusou a imagem {imagem_url}")
        time.sleep(3)

    midia = chamar("POST", f"{IG_USER_ID}/media_publish", {"creation_id": container})["id"]
    return chamar("GET", midia, {"fields": "permalink"})["permalink"]


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
            img = Path(post["imagem"])
            if img.exists():
                shutil.move(str(img), descartes / img.name)
            print(f"Descartado (antigo): {arq.name}")
            continue
        try:
            link = publicar(post)
            post["publicado_em"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            post["link"] = link
            print(f"Publicado: {link}")
            imagem = Path(post["imagem"])
            if imagem.exists():
                destino = PUBLICADOS / imagem.name
                shutil.move(str(imagem), destino)
                post["imagem"] = str(destino)
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
