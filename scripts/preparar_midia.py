"""Roda no GitHub Actions ANTES de publicar.

Para cada Reels da fila com "narracao" (texto): gera a voz na API da ElevenLabs
(segredo ELEVENLABS_API_KEY; voz opcional em ELEVENLABS_VOICE_ID ou no campo "voz" do post),
mixa no vídeo com FFmpeg (estende o último quadro se a voz for mais longa),
grava um NOVO arquivo *_final.mp4 (nome novo evita cache do raw.githubusercontent)
e atualiza o JSON. O workflow faz commit/push antes de publicar.
Se a ElevenLabs falhar, o Reels segue sem narração.
"""
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

FILA = Path("posts/fila")
API = "https://api.elevenlabs.io/v1"
CHAVE = os.environ.get("ELEVENLABS_API_KEY", "").strip()
MODELO = "eleven_multilingual_v2"


def req(url, dados=None, aceitar="application/json"):
    r = urllib.request.Request(url, data=json.dumps(dados).encode() if dados else None,
                               headers={"xi-api-key": CHAVE, "Content-Type": "application/json",
                                        "Accept": aceitar})
    with urllib.request.urlopen(r, timeout=90) as resp:
        return resp.read()


def escolher_voz(post):
    voz = post.get("voz") or os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if voz:
        return voz
    vozes = json.loads(req(f"{API}/voices"))["voices"]
    # prefere voz masculina da biblioteca do usuário; senão a primeira disponível
    for v in vozes:
        if (v.get("labels") or {}).get("gender") == "male":
            return v["voice_id"]
    return vozes[0]["voice_id"]


# Pronúncia da marca: "CongoApp" tem que soar "congoép" (não "congo-app").
PRONUNCIA = [(re.compile(r"@?congo[\s\-]*app_?", re.IGNORECASE), "Congoép")]


def pronunciar(texto):
    for padrao, fala in PRONUNCIA:
        texto = padrao.sub(fala, texto)
    return texto


def narrar(texto, voz, destino):
    texto = pronunciar(texto)
    audio = req(f"{API}/text-to-speech/{voz}?output_format=mp3_44100_128",
                {"text": texto, "model_id": MODELO,
                 "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35,
                                    "use_speaker_boost": True}},
                aceitar="audio/mpeg")
    destino.write_bytes(audio)


def duracao(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(arq)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def main():
    mudou = False
    for arq in sorted(FILA.glob("*.json")):
        post = json.loads(arq.read_text(encoding="utf-8"))
        if post.get("tipo") != "reels" or not post.get("narracao") or "audio_ok" in post:
            continue
        video = Path(post["video"])
        audio = video.with_suffix(".mp3")
        try:
            if not CHAVE:
                raise RuntimeError("ELEVENLABS_API_KEY não configurada")
            voz = escolher_voz(post)
            narrar(post["narracao"], voz, audio)
            post["voz"] = voz
        except Exception as e:  # sem narração, publica o vídeo mudo
            print(f"Narração indisponível para {arq.name}: {e}")
            post["audio_ok"] = False
            arq.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
            mudou = True
            continue
        dv, da = duracao(video), duracao(audio)
        extra = max(0.0, da + 0.6 - dv)  # voz + respiro no fim
        final = video.with_name(video.stem + "_final.mp4")
        filtro_v = f"tpad=stop_mode=clone:stop_duration={extra:.2f}" if extra > 0 else "null"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio),
            "-filter_complex",
            f"[0:v]{filtro_v}[v];[1:a]adelay=250|250,loudnorm=I=-14:TP=-1.5:LRA=11,apad[a]",
            "-map", "[v]", "-map", "[a]", "-t", f"{max(dv, da + 0.85):.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(final)],
            check=True)
        audio.unlink()
        video.unlink()
        post["video"] = str(final)
        post["audio_ok"] = True
        arq.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Narração mixada: {final}")
        mudou = True
    print("MUDOU" if mudou else "SEM_MUDANCA")


if __name__ == "__main__":
    main()
