"""
agents/price_agent.py
---------------------
Agente especializado en la extracción del precio spot del oro (XAU/USD)
desde la API pública JSON de Yahoo Finance (sin clave de API requerida).

Fuente  : https://query1.finance.yahoo.com/v8/finance/chart/GC=F
Ticker  : GC=F (Gold Futures — contrato más cercano, proxy del spot)
Columnas: timestamp, precio, divisa, fuente
"""

import csv
import os
from datetime import datetime, timezone
from typing import Optional

from core.base_agent import BaseAgent

# ─── Constantes ──────────────────────────────────────────────────────────────
YAHOO_API_URL: str = (
    "https://query1.finance.yahoo.com/v8/finance/chart/GC%3DF"
    "?interval=1m&range=1d&includePrePost=false"
)
CSV_PATH: str = "data/precios_oro.csv"
CSV_COLUMNS: list[str] = ["timestamp", "precio", "divisa", "fuente"]


class PriceAgent(BaseAgent):
    """
    Agente de extracción de precios del oro vía Yahoo Finance.

    Hereda la resiliencia de BaseAgent (Backoff Exponencial + Jitter +
    Circuit Breaker) y añade la lógica de parsing del JSON de Yahoo Finance
    y la persistencia en CSV local en modo append.
    """

    def __init__(self) -> None:
        """Inicializa el PriceAgent con nombre identificador y directorio de datos."""
        super().__init__(name="PriceAgent")
        os.makedirs("data", exist_ok=True)
        self._ensure_csv_header()

    # ─── CSV ─────────────────────────────────────────────────────────────────

    def _ensure_csv_header(self) -> None:
        """
        Crea el archivo CSV con cabecera si no existe todavía.
        No sobreescribe datos existentes (modo append-safe).
        """
        if not os.path.exists(CSV_PATH):
            with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()
            self.logger.info("CSV creado: %s", CSV_PATH)

    def _append_to_csv(self, timestamp: str, precio: float, divisa: str, fuente: str) -> None:
        """
        Añade una fila al CSV en modo append. Nunca sobreescribe registros previos.

        Args:
            timestamp (str): Marca temporal en formato ISO 8601 UTC.
            precio    (float): Precio del oro extraído.
            divisa    (str): Código de divisa (ej. 'USD').
            fuente    (str): Identificador de la fuente de datos.
        """
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow(
                {
                    "timestamp": timestamp,
                    "precio": precio,
                    "divisa": divisa,
                    "fuente": fuente,
                }
            )
        self.logger.info("Registro guardado → %s | %s %s | %s", timestamp, precio, divisa, fuente)

    # ─── Parser ──────────────────────────────────────────────────────────────

    def _parse_price(self, data: dict) -> Optional[tuple[float, str]]:
        """
        Extrae el precio más reciente y la divisa del JSON de Yahoo Finance.

        Navega la estructura:
        chart → result[0] → meta → regularMarketPrice / currency

        Args:
            data (dict): JSON decodificado de la respuesta de Yahoo Finance.

        Returns:
            Optional[tuple[float, str]]: (precio, divisa) o None si el parse falla.
        """
        try:
            result = data["chart"]["result"][0]
            meta = result["meta"]
            precio: float = float(meta["regularMarketPrice"])
            divisa: str = meta.get("currency", "USD")
            return precio, divisa
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            self.logger.error("Error al parsear JSON de Yahoo Finance: %s", exc)
            return None

    # ─── Scraper ─────────────────────────────────────────────────────────────

    def scrape(self) -> Optional[tuple[float, str]]:
        """
        Descarga el JSON de Yahoo Finance y extrae el precio spot del oro.

        Usa el método fetch() heredado de BaseAgent para resiliencia completa.

        Returns:
            Optional[tuple[float, str]]: (precio, divisa) o None si falla.
        """
        # Cabecera específica para el endpoint JSON de Yahoo Finance
        response = self.fetch(
            YAHOO_API_URL,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://finance.yahoo.com/",
            },
        )

        if response is None:
            return None

        try:
            data = response.json()
        except ValueError as exc:
            self.logger.error("Respuesta no es JSON válido: %s", exc)
            return None

        return self._parse_price(data)

    # ─── Punto de entrada ─────────────────────────────────────────────────────

    def run(self) -> bool:
        """
        Ejecuta el ciclo completo del agente: extracción → parsing → persistencia.

        Returns:
            bool: True si el precio fue extraído y guardado con éxito, False si no.
        """
        self.logger.info("=== PriceAgent iniciado ===")
        result = self.scrape()

        if result is None:
            self.logger.error("PriceAgent no pudo obtener el precio del oro.")
            return False

        precio, divisa = result
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        self._append_to_csv(
            timestamp=timestamp,
            precio=precio,
            divisa=divisa,
            fuente="Yahoo Finance / GC=F",
        )

        # Resumen visible en terminal (ASCII-safe para compatibilidad con Windows cp1252)
        sep = "-" * 50
        print(f"\n{sep}")
        print(f"  GOLD-SENTINEL -- PriceAgent")
        print(sep)
        print(f"  Timestamp : {timestamp}")
        print(f"  Precio    : {precio:,.2f} {divisa}")
        print(f"  Fuente    : Yahoo Finance (GC=F - Gold Futures)")
        print(f"  CSV       : {CSV_PATH}")
        print(f"{sep}\n")

        self.logger.info("=== PriceAgent completado con éxito ===")
        return True
