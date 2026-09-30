"""Roda no GitHub Actions ANTES de publicar.

Para cada Reels da fila com "audio_url" (narração gerada no Higgsfield/ElevenLabs):
baixa o áudio, mixa no vídeo com FFmpeg (estende o último quadro se a voz for mais longa),
grava um NOVO arquivo *_final.mp4 (nome novo evita cache do raw.githubusercontent)
e atualiza o JSON. O workflow faz commit/push antes de publicar.
"""
import json
import subprocess
import urllib.request
from pathlib import Path

FILA = Path("posts/fila")


def duracao(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(arq)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def main():
    mudou = False
    for arq in sorted(FILA.glob("*.json")):
        post = json.loads(arq.read_text(encoding="utf-8"))
        if post.get("tipo") != "reels" or not post.get("audio_url") or post.get("audio_ok"):
            continue
        video = Path(post["video"])
        audio = video.with_suffix(".audio")
        try:
            req = urllib.request.Request(post["audio_url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                audio.write_bytes(r.read())
        except Exception as e:  # sem áudio, publica o vídeo mudo
            print(f"Áudio indisponível para {arq.name}: {e}")
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
