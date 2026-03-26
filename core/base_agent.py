"""
core/base_agent.py
------------------
Clase base abstracta para todos los agentes del ecosistema GOLD-SENTINEL.
Implementa la lógica de resiliencia (Backoff Exponencial + Jitter + Circuit Breaker)
y la gestión de headers de sigilo, conforme al protocolo INSTRUCTIONS.md.
"""

import time
import random
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import requests
from requests import Response, Session

# ─── Configuración de logging ────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/sentinel.log", encoding="utf-8"),
    ],
)


# ─── Pool de User-Agents modernos ────────────────────────────────────────────
USER_AGENTS: list[str] = [
    # Chrome 124 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Edge 124 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Safari 17 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Firefox 125 Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    # Chrome 124 macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class BaseAgent(ABC):
    """
    Clase base abstracta para los agentes GOLD-SENTINEL.

    Provee:
    - Rotación de User-Agent y headers miméticos por sesión.
    - Método `fetch()` con Backoff Exponencial + Jitter + Circuit Breaker.
    - Método abstracto `run()` que cada agente especializado debe implementar.

    Attributes:
        name (str): Identificador del agente, usado en los logs.
        max_retries (int): Intentos máximos antes de activar el Circuit Breaker.
        base_delay (float): Segundos base para el primer backoff.
        session (requests.Session): Sesión HTTP reutilizable con headers pre-cargados.
        logger (logging.Logger): Logger dedicado al agente.
    """

    MAX_RETRIES: int = 5
    BASE_DELAY: float = 2.0       # segundos de espera base
    JITTER_FACTOR: float = 0.20   # ±20% de ruido aleatorio

    def __init__(self, name: str) -> None:
        """
        Inicializa el agente con nombre, logger y sesión HTTP con headers rotados.

        Args:
            name (str): Nombre identificador del agente (ej. 'PriceAgent').
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self.session: Session = self._build_session()

    # ─── Sesión y headers ────────────────────────────────────────────────────

    def _build_session(self) -> Session:
        """
        Construye una sesión requests con un User-Agent aleatorio y headers
        miméticos para simular navegación humana real.

        Returns:
            requests.Session: Sesión configurada lista para usar.
        """
        session = requests.Session()
        ua = random.choice(USER_AGENTS)
        session.headers.update(
            {
                "User-Agent": ua,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.google.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1",
                "Connection": "keep-alive",
                "DNT": "1",
            }
        )
        self.logger.debug("Sesión iniciada con UA: %s", ua[:60])
        return session

    def _rotate_session(self) -> None:
        """Renueva la sesión con un User-Agent diferente (llamado tras cada retry)."""
        self.session.close()
        self.session = self._build_session()

    # ─── Backoff + Jitter + Circuit Breaker ──────────────────────────────────

    def _compute_wait(self, attempt: int) -> float:
        """
        Calcula el tiempo de espera con backoff exponencial y jitter ±20%.

        Fórmula: base_delay * 2^attempt * (1 ± jitter)

        Args:
            attempt (int): Número de intento actual (0-indexed).

        Returns:
            float: Segundos a esperar antes del siguiente intento.
        """
        exponential = self.BASE_DELAY * (2 ** attempt)
        jitter = exponential * self.JITTER_FACTOR * random.uniform(-1, 1)
        return max(0.5, exponential + jitter)

    def fetch(self, url: str, **kwargs) -> Optional[Response]:
        """
        Realiza una petición GET resiliente con Circuit Breaker integrado.

        Reintenta automáticamente ante errores HTTP 429, 403 y excepciones
        de red, aplicando Backoff Exponencial + Jitter. Aborta tras MAX_RETRIES
        intentos y registra el fallo en el log de errores.

        Args:
            url (str): URL de destino.
            **kwargs: Argumentos adicionales para requests.Session.get().

        Returns:
            Optional[Response]: Objeto Response si la petición tuvo éxito,
                                None si el Circuit Breaker se activó.
        """
        retryable_codes = {429, 403, 503, 504}

        for attempt in range(self.MAX_RETRIES):
            try:
                self.logger.info("GET %s (intento %d/%d)", url, attempt + 1, self.MAX_RETRIES)
                response = self.session.get(url, timeout=15, **kwargs)

                if response.status_code == 200:
                    return response

                if response.status_code in retryable_codes:
                    wait = self._compute_wait(attempt)
                    self.logger.warning(
                        "HTTP %d recibido. Esperando %.2fs antes de reintentar…",
                        response.status_code,
                        wait,
                    )
                    self._rotate_session()
                    time.sleep(wait)
                    continue

                # Código no recuperable (404, 500, etc.) → abortar inmediatamente
                self.logger.error("HTTP %d no recuperable para %s", response.status_code, url)
                return None

            except requests.exceptions.RequestException as exc:
                wait = self._compute_wait(attempt)
                self.logger.warning("Error de red: %s. Esperando %.2fs…", exc, wait)
                time.sleep(wait)

        # Circuit Breaker activado
        self.logger.error(
            "⛔ CIRCUIT BREAKER activado tras %d intentos fallidos. URL: %s",
            self.MAX_RETRIES,
            url,
        )
        self._log_failure(url)
        return None

    def _log_failure(self, url: str) -> None:
        """
        Registra un fallo crítico (Circuit Breaker) en el archivo de errores.

        Args:
            url (str): URL que provocó el agotamiento de reintentos.
        """
        timestamp = datetime.utcnow().isoformat()
        os.makedirs("logs", exist_ok=True)
        with open("logs/errors.log", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | {self.name} | CIRCUIT_BREAKER | {url}\n")

    # ─── Método abstracto ────────────────────────────────────────────────────

    @abstractmethod
    def run(self) -> bool:
        """
        Punto de entrada principal del agente. Debe ser implementado por cada
        agente especializado.

        Returns:
            bool: True si la tarea completó con éxito, False en caso de fallo.
        """
        ...
