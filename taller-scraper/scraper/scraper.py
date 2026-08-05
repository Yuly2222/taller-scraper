"""
scraper.py
----------
Web Scraper que:
  1. Descarga la página objetivo (Hacker News, https://news.ycombinator.com/).
  2. Extrae título, enlace y metadatos (puntos, autor, comentarios) de cada post.
  3. Empaqueta los resultados en JSON y los envía por POST al backend
     (endpoint /api/items) para que este los guarde en Supabase.

Requisitos: ver requirements.txt (requests, beautifulsoup4)

Uso:
    python scraper.py
    python scraper.py --dry-run      # solo imprime, no hace POST
    API_URL=http://localhost:3000 python scraper.py
"""

import os
import sys
import argparse
import logging
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
TARGET_URL = "https://news.ycombinator.com/"
API_URL = os.environ.get("API_URL", "http://localhost:3000")
API_ITEMS_ENDPOINT = f"{API_URL}/api/items"
REQUEST_TIMEOUT = 10  # segundos
HEADERS = {
    # Identificarse correctamente es buena práctica al hacer scraping
    "User-Agent": "Mozilla/5.0 (educational-scraper; +https://example.com/bot-info)"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 1. Extracción (scraping)
# --------------------------------------------------------------------------
def fetch_html(url: str) -> str:
    """Descarga el HTML de la URL dada, con manejo de errores de red."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.exceptions.Timeout:
        logger.error("Timeout al conectar con %s", url)
        raise
    except requests.exceptions.RequestException as exc:
        logger.error("Error de red al obtener %s: %s", url, exc)
        raise


def parse_items(html: str, source: str) -> List[Dict[str, Any]]:
    """
    Recibe el HTML y devuelve una lista de diccionarios con la forma:
    {
        "title": str,
        "url": str,
        "source": str,
        "metadata": { "points": int|None, "comments": int|None, "author": str|None }
    }
    """
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    # Cada historia de HN vive en una fila <tr class="athing">
    story_rows = soup.select("tr.athing")

    for row in story_rows:
        title_tag = row.select_one("span.titleline > a")
        if not title_tag:
            continue  # fila inesperada, la saltamos en vez de romper todo el scraper

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "")

        # Normalizar enlaces relativos (algunos posts de HN son internos, ej: "item?id=123")
        if link.startswith("item?"):
            link = TARGET_URL + link

        # La fila de metadatos (puntos, autor, comentarios) es el <tr> siguiente
        subtext_row = row.find_next_sibling("tr")
        points = comments = author = None

        if subtext_row:
            subtext = subtext_row.select_one("td.subtext")
            if subtext:
                score_tag = subtext.select_one("span.score")
                if score_tag:
                    points = _safe_int(score_tag.get_text(strip=True).split()[0])

                author_tag = subtext.select_one("a.hnuser")
                if author_tag:
                    author = author_tag.get_text(strip=True)

                # El link de comentarios es el último <a> del subtext
                links_in_subtext = subtext.select("a")
                if links_in_subtext:
                    comments_text = links_in_subtext[-1].get_text(strip=True)
                    comments = _safe_int(comments_text.split()[0]) if "comment" in comments_text else 0

        items.append(
            {
                "title": title,
                "url": link,
                "source": source,
                "metadata": {
                    "points": points,
                    "comments": comments,
                    "author": author,
                },
            }
        )

    return items


def _safe_int(value: str) -> int | None:
    """Convierte texto a int de forma segura, devolviendo None si falla."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------
# 2. Envío al backend (integración)
# --------------------------------------------------------------------------
def send_to_api(items: List[Dict[str, Any]], endpoint: str = API_ITEMS_ENDPOINT) -> bool:
    """
    Empaqueta los items en JSON y hace un POST al backend.
    Devuelve True si el backend respondió con éxito, False en caso contrario.
    """
    if not items:
        logger.warning("No hay items para enviar, se omite el POST.")
        return False

    payload = {"items": items}

    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        logger.info(
            "POST exitoso: %s items enviados, %s insertados.",
            len(items),
            result.get("inserted", "N/A"),
        )
        return True
    except requests.exceptions.ConnectionError:
        logger.error(
            "No se pudo conectar con el backend en %s. "
            "¿Está corriendo 'node server.js'?",
            endpoint,
        )
        return False
    except requests.exceptions.HTTPError as exc:
        logger.error("El backend respondió con error: %s - %s", exc, response.text)
        return False
    except requests.exceptions.RequestException as exc:
        logger.error("Error inesperado al hacer POST: %s", exc)
        return False


# --------------------------------------------------------------------------
# 3. Orquestación (main)
# --------------------------------------------------------------------------
def run(dry_run: bool = False) -> int:
    logger.info("Iniciando scraping de %s", TARGET_URL)

    try:
        html = fetch_html(TARGET_URL)
    except requests.exceptions.RequestException:
        logger.error("Abortando: no se pudo descargar la página objetivo.")
        return 1

    items = parse_items(html, source="Hacker News")
    logger.info("Se extrajeron %s items.", len(items))

    if dry_run:
        for item in items[:5]:
            logger.info("DRY-RUN: %s", item)
        logger.info("Dry-run activo: no se envió nada al backend.")
        return 0

    ok = send_to_api(items)
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper de Hacker News -> API backend")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo extrae e imprime resultados, no hace POST al backend.",
    )
    args = parser.parse_args()
    sys.exit(run(dry_run=args.dry_run))
