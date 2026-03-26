"""
agents/news_agent.py
--------------------
Agente especializado en la extracción y filtrado de noticias financieras
relacionadas con el mercado del oro vía RSS de Google News.

Fuente     : https://news.google.com/rss/search?q=gold+price+economy
Persistencia: data/noticias_oro.json (append sin duplicados, link como ID único)
Filtros    : Gold, Fed, Inflation, Interest Rates
"""

import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser

from core.base_agent import BaseAgent

# ─── Constantes ──────────────────────────────────────────────────────────────
RSS_URL: str = (
    "https://news.google.com/rss/search"
    "?q=gold+price+fed+inflation+interest+rates"
    "&hl=en-US&gl=US&ceid=US:en"
)
JSON_PATH: str = "data/noticias_oro.json"

KEYWORDS: list[str] = [
    "gold",
    "fed",
    "federal reserve",
    "inflation",
    "interest rate",
    "interest rates",
    "xau",
    "bullion",
]


class NewsAgent(BaseAgent):
    """
    Agente de extracción de noticias financieras del mercado del oro.

    Conecta al feed RSS de Google News, filtra titulares por palabras clave
    relevantes y persiste los resultados en JSON local sin duplicar entradas.

    Hereda la resiliencia de BaseAgent (Backoff Exponencial + Jitter +
    Circuit Breaker).
    """

    def __init__(self) -> None:
        """Inicializa el NewsAgent y garantiza que el archivo JSON exista."""
        super().__init__(name="NewsAgent")
        os.makedirs("data", exist_ok=True)
        self._ensure_json_file()

    # ─── Persistencia JSON ───────────────────────────────────────────────────

    def _ensure_json_file(self) -> None:
        """
        Crea el archivo JSON con una lista vacía si no existe.
        No sobreescribe datos existentes.
        """
        if not os.path.exists(JSON_PATH):
            with open(JSON_PATH, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            self.logger.info("JSON creado: %s", JSON_PATH)

    def _load_existing(self) -> list[dict]:
        """
        Carga las noticias ya almacenadas desde el archivo JSON.

        Returns:
            list[dict]: Lista de noticias existentes (vacía si el archivo está vacío).
        """
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("JSON corrupto o vacío, iniciando lista limpia.")
                return []

    def _save_all(self, noticias: list[dict]) -> None:
        """
        Sobreescribe el archivo JSON con la lista completa actualizada.

        Args:
            noticias (list[dict]): Lista completa de noticias a persistir.
        """
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(noticias, f, ensure_ascii=False, indent=2)

    # ─── Filtro de relevancia ────────────────────────────────────────────────

    def _is_relevant(self, titulo: str) -> bool:
        """
        Determina si un titular contiene al menos una palabra clave relevante.

        La comparación es case-insensitive.

        Args:
            titulo (str): Título de la noticia a evaluar.

        Returns:
            bool: True si el titular contiene alguna palabra clave, False si no.
        """
        titulo_lower = titulo.lower()
        return any(kw in titulo_lower for kw in KEYWORDS)

    # ─── Parser del feed RSS ─────────────────────────────────────────────────

    def _parse_feed(self, raw_content: bytes) -> list[dict]:
        """
        Parsea el contenido RSS con feedparser y extrae los campos requeridos.

        Aplica el filtro de palabras clave antes de retornar las entradas.
        Las fechas se normalizan a ISO 8601 UTC.

        Args:
            raw_content (bytes): Contenido crudo de la respuesta HTTP del feed.

        Returns:
            list[dict]: Lista de noticias relevantes con campos:
                        titulo, fecha_publicacion, link, fuente, extraido_en.
        """
        feed = feedparser.parse(raw_content)

        if feed.bozo and not feed.entries:
            self.logger.error("feedparser no pudo leer el feed RSS: %s", feed.bozo_exception)
            return []

        self.logger.info("Entradas en el feed: %d", len(feed.entries))
        resultados: list[dict] = []

        for entry in feed.entries:
            titulo: str = entry.get("title", "").strip()

            if not titulo or not self._is_relevant(titulo):
                continue

            # Normalización de fecha a ISO 8601
            fecha_iso: str = self._normalize_date(entry)

            resultados.append(
                {
                    "titulo": titulo,
                    "fecha_publicacion": fecha_iso,
                    "link": entry.get("link", ""),
                    "fuente": "Google News RSS",
                    "extraido_en": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )

        return resultados

    def _normalize_date(self, entry: dict) -> str:
        """
        Convierte la fecha de publicación de un entry RSS a formato ISO 8601 UTC.

        Intenta parsear el campo 'published' (RFC 2822). Si falla, usa la
        fecha/hora actual como fallback.

        Args:
            entry (dict): Entrada del feed RSS parseada por feedparser.

        Returns:
            str: Fecha en formato ISO 8601 UTC (ej. '2026-03-25T12:00:00Z').
        """
        published: str = entry.get("published", "")
        try:
            dt = parsedate_to_datetime(published)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ─── Deduplicación ───────────────────────────────────────────────────────

    def _merge_without_duplicates(
        self, existentes: list[dict], nuevas: list[dict]
    ) -> tuple[list[dict], int]:
        """
        Combina noticias existentes con nuevas, descartando duplicados por link.

        Args:
            existentes (list[dict]): Noticias ya almacenadas en el JSON.
            nuevas     (list[dict]): Noticias recién extraídas del feed.

        Returns:
            tuple[list[dict], int]: (lista_combinada, cantidad_de_nuevas_añadidas)
        """
        links_existentes: set[str] = {n["link"] for n in existentes}
        agregadas = 0
        for noticia in nuevas:
            if noticia["link"] not in links_existentes:
                existentes.append(noticia)
                links_existentes.add(noticia["link"])
                agregadas += 1
        return existentes, agregadas

    # ─── Scraper ─────────────────────────────────────────────────────────────

    def scrape(self) -> Optional[list[dict]]:
        """
        Descarga el feed RSS y retorna las noticias relevantes parseadas.

        Usa fetch() de BaseAgent para resiliencia completa.

        Returns:
            Optional[list[dict]]: Lista de noticias filtradas, o None si falla.
        """
        response = self.fetch(RSS_URL)
        if response is None:
            return None
        return self._parse_feed(response.content)

    # ─── Punto de entrada ─────────────────────────────────────────────────────

    def run(self) -> bool:
        """
        Ejecuta el ciclo completo: extracción → filtrado → deduplicación → persistencia.

        Returns:
            bool: True si al menos una noticia fue procesada con éxito, False si no.
        """
        self.logger.info("=== NewsAgent iniciado ===")

        noticias_nuevas = self.scrape()
        if noticias_nuevas is None:
            self.logger.error("NewsAgent no pudo obtener el feed RSS.")
            return False

        existentes = self._load_existing()
        combinadas, agregadas = self._merge_without_duplicates(existentes, noticias_nuevas)
        self._save_all(combinadas)

        # Resumen en terminal
        sep = "-" * 50
        print(f"\n{sep}")
        print("  GOLD-SENTINEL -- NewsAgent")
        print(sep)
        print(f"  Noticias en feed    : {len(noticias_nuevas)}")
        print(f"  Nuevas guardadas    : {agregadas}")
        print(f"  Total en JSON       : {len(combinadas)}")
        print(f"  Archivo             : {JSON_PATH}")
        print(sep)

        if agregadas > 0:
            print("\n  Ultimas noticias guardadas:")
            for n in combinadas[-3:]:
                print(f"  [{n['fecha_publicacion']}] {n['titulo'][:70]}")
        print()

        self.logger.info(
            "NewsAgent completado: %d nuevas noticias guardadas (total: %d).",
            agregadas,
            len(combinadas),
        )
        return True
