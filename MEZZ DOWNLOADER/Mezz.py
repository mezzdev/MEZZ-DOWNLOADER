import itertools
import os
import sys
import threading
import time
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import colorama
    from colorama import Style
    colorama.init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False


LOGO = r"""
███╗░░░███╗███████╗███████╗███████╗
████╗░████║██╔════╝╚══███╔╝╚══███╔╝
██╔████╔██║█████╗░░░░███╔╝░░░███╔╝░
██║╚██╔╝██║██╔══╝░░░███╔╝░░░███╔╝░░
██║░╚═╝░██║███████╗███████╗███████╗
╚═╝░░░░░╚═╝╚══════╝╚══════╝╚══════╝
"""

BOX_WIDTH = 44

def resource_path(relative_path):
    """
    Retourne le chemin absolu d'une ressource (ffmpeg, ...).
    Fonctionne en script normal et une fois compilé avec PyInstaller (--onefile).
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def find_ffmpeg():
    """Cherche un ffmpeg.exe livré à côté du programme, sinon utilise le PATH."""
    local_ffmpeg = resource_path("ffmpeg.exe")
    if os.path.isfile(local_ffmpeg):
        return local_ffmpeg
    return None


def bold(text):
    return f"{Style.BRIGHT}{text}{Style.RESET_ALL}" if HAS_COLOR else text


def dim(text):
    return f"{Style.DIM}{text}{Style.RESET_ALL}" if HAS_COLOR else text


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def setup_console():
    """Configure la console Windows : titre de la fenêtre + encodage UTF-8
    (nécessaire pour afficher correctement les caractères du logo et des cadres)."""
    if os.name == "nt":
        os.system("title MEZZ DOWNLOADER")
        os.system("chcp 65001 > nul")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def box_top(width=BOX_WIDTH):
    return "  " + dim("╔" + "═" * (width - 2) + "╗")


def box_bottom(width=BOX_WIDTH):
    return "  " + dim("╚" + "═" * (width - 2) + "╝")


def box_sep(width=BOX_WIDTH):
    return "  " + dim("╠" + "═" * (width - 2) + "╣")


def box_line(text="", width=BOX_WIDTH):
    inner = width - 4
    if len(text) > inner:
        text = text[: inner - 1] + "…"
    return f"  {dim('║')} {text.ljust(inner)} {dim('║')}"


def print_logo():
    print(bold(LOGO))


def print_header():
    print(box_top())
    print(box_line("DOWNLOADER · YOUTUBE + TIKTOK"))
    print(box_bottom())
    print()


def with_spinner(message, func, *args, **kwargs):
    """Exécute func(*args, **kwargs) dans un thread en affichant un spinner."""
    outcome = {}

    def worker():
        try:
            outcome["value"] = func(*args, **kwargs)
        except Exception as e:
            outcome["error"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    frames = itertools.cycle(["◐", "◓", "◑", "◒"])
    while t.is_alive():
        sys.stdout.write(f"\r  {next(frames)} {message}")
        sys.stdout.flush()
        time.sleep(0.12)

    sys.stdout.write("\r" + " " * (len(message) + 4) + "\r")
    sys.stdout.flush()

    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


def format_duration(seconds):
    if not seconds:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def platform_label(info):
    extractor = (info.get("extractor_key") or info.get("extractor") or "").lower()
    if "tiktok" in extractor:
        return "TikTok"
    if "youtube" in extractor:
        return "YouTube"
    return info.get("extractor_key") or "Inconnue"


def format_speed(speed):
    if not speed:
        return "-- Mo/s"
    return f"{speed / 1_000_000:.1f} Mo/s"


def format_eta(eta):
    if eta is None:
        return "--:--"
    m, s = divmod(int(eta), 60)
    return f"{m}:{s:02d}"


def print_progress_bar(percent, speed=None, eta=None, width=32, done=False):
    filled = int(width * percent / 100)
    bar = "█" * filled + "░" * (width - filled)
    info = "" if done else f"   {format_speed(speed)}   ETA {format_eta(eta)}"
    sys.stdout.write(f"\r  [{bar}] {percent:5.1f}%{info}    ")
    sys.stdout.flush()

def base_opts():
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        opts["ffmpeg_location"] = ffmpeg_path
    return opts


def fetch_info(url):
    opts = base_opts()
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def print_info_card(info):
    title = info.get("title") or "Sans titre"
    author = info.get("uploader") or info.get("channel") or "—"
    duration = format_duration(info.get("duration"))
    platform = platform_label(info)

    print(box_top())
    print(box_line(f"Plateforme : {platform}"))
    print(box_line(f"Titre      : {title}"))
    print(box_line(f"Auteur     : {author}"))
    print(box_line(f"Durée      : {duration}"))
    print(box_bottom())


def progress_hook(d):
    if d.get("status") == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes", 0)
        if total:
            percent = downloaded / total * 100
            print_progress_bar(percent, d.get("speed"), d.get("eta"))
    elif d.get("status") == "finished":
        print_progress_bar(100, done=True)
        sys.stdout.write("\n")
        print(dim("  Traitement (fusion / conversion)..."))


def build_ydl_opts(dest, mode):
    ydl_opts = base_opts()
    ydl_opts.update({
        "outtmpl": os.path.join(dest, "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
    })

    if mode == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": (
                "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[height<=2160]+bestaudio/"
                "best[height<=2160]/best"
            ),
            "merge_output_format": "mp4",
        })

    return ydl_opts


def download(url, dest, mode):
    ydl_opts = build_ydl_opts(dest, mode)

    print()
    print(box_top())
    print(box_line("TÉLÉCHARGEMENT EN COURS"))
    print(box_bottom())
    print()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print()
        print(box_top())
        print(box_line("TERMINÉ"))
        print(box_line(f"Fichier dans : {dest}"))
        print(box_bottom())
    except Exception as e:
        print()
        print(box_top())
        print(box_line("ERREUR"))
        print(box_line(str(e)))
        print(box_sep())
        print(box_line("Astuce : si c'est un lien TikTok, mets"))
        print(box_line("yt-dlp à jour : pip install -U yt-dlp"))
        print(box_bottom())




def ask_format():
    print(box_top())
    print(box_line("FORMAT"))
    print(box_sep())
    print(box_line("[1] Vidéo (4K si dispo)"))
    print(box_line("[2] Audio seulement (MP3)"))
    print(box_bottom())
    choice = input("  Choix (1/2, défaut = 1) : ").strip()
    return "audio" if choice == "2" else "video"


def ask_destination():
    default = str(Path.home() / "Downloads")
    dest = input(f"  Dossier de destination [{default}] : ").strip()
    dest = dest or default
    os.makedirs(dest, exist_ok=True)
    return dest


def main():
    setup_console()

    if yt_dlp is None:
        print("Le module yt-dlp n'est pas installé.")
        print("Installe-le avec : pip install yt-dlp")
        input("\nAppuie sur Entrée pour fermer...")
        return

    while True:
        clear_screen()
        print_logo()
        print_header()

        url = input("  › Lien YouTube ou TikTok (ou 'q' pour quitter) : ").strip()
        if url.lower() in ("q", "quit", "exit"):
            break
        if not url:
            continue

        try:
            info = with_spinner("Analyse du lien...", fetch_info, url)
        except Exception as e:
            print()
            print(box_top())
            print(box_line("ERREUR"))
            print(box_line(str(e)))
            print(box_bottom())
            input("\n  Appuie sur Entrée pour continuer...")
            continue

        print()
        print_info_card(info)
        print()

        proceed = input("  Entrée pour télécharger, 'a' pour annuler : ").strip().lower()
        if proceed == "a":
            input("\n  Appuie sur Entrée pour continuer...")
            continue

        print()
        fmt = ask_format()
        print()
        dest = ask_destination()

        download(url, dest, fmt)

        again = input("\n  Télécharger une autre vidéo ? (o/n) : ").strip().lower()
        if again != "o":
            break

    print(f"\n{dim('À bientôt.')}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{dim('Interrompu. À bientôt.')}\n")
