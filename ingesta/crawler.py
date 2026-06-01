import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "LocalRAG-Crawler/1.0"}
TAGS_EXCLUIR = ["nav", "footer", "header", "script", "style", "aside", "form", "noscript"]


# ---------------------------------------------------------------------------
# Fase 1 — Escaneo de URLs
# ---------------------------------------------------------------------------

def _urls_desde_sitemap(url_base: str) -> list[str]:
    url_sitemap = url_base.rstrip("/") + "/sitemap.xml"
    try:
        resp = requests.get(url_sitemap, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    except Exception:
        return []


def _urls_desde_html(url_base: str, profundidad: int, visitadas: set) -> list[str]:
    if profundidad == 0 or url_base in visitadas:
        return []
    visitadas.add(url_base)
    dominio = urlparse(url_base).netloc
    encontradas = [url_base]
    try:
        resp = requests.get(url_base, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return encontradas
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup.find_all("a", href=True):
            href = urljoin(url_base, tag["href"])
            parsed = urlparse(href)
            if parsed.netloc == dominio and parsed.scheme in ("http", "https"):
                href_limpio = parsed._replace(fragment="", query="").geturl()
                if href_limpio not in visitadas:
                    encontradas += _urls_desde_html(href_limpio, profundidad - 1, visitadas)
    except Exception:
        pass
    return encontradas


def escanear(url_base: str, profundidad_max: int = 2) -> list[str]:
    """
    Fase 1: intenta sitemap.xml primero; si no existe, recorre links recursivamente.
    Retorna lista de URLs únicas del mismo dominio.
    """
    urls = _urls_desde_sitemap(url_base)
    if not urls:
        urls = _urls_desde_html(url_base, profundidad_max, set())
    return list(dict.fromkeys(urls))  # deduplicar preservando orden


# ---------------------------------------------------------------------------
# Fase 2 — Descarga y limpieza selectiva
# ---------------------------------------------------------------------------

def _limpiar_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(TAGS_EXCLUIR):
        tag.decompose()
    texto = soup.get_text(separator="\n")
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    return "\n".join(lineas)


def descargar(urls: list[str]) -> list[dict]:
    """
    Fase 2: descarga solo las URLs seleccionadas y extrae texto limpio.
    Retorna lista de { url, texto }.
    """
    resultados = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            texto = _limpiar_html(resp.text)
            if texto:
                resultados.append({"url": url, "texto": texto})
        except Exception:
            continue
    return resultados
