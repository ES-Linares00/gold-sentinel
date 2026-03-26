"""
main.py
-------
Orquestador principal del ecosistema GOLD-SENTINEL.

Ejecuta los agentes de forma secuencial. Si un agente falla, el orquestador
registra el error y continúa con el siguiente, garantizando que el sistema
no se detenga por el fallo de un componente individual.

Uso:
    python main.py
"""

import logging
import sys
from typing import Callable

from agents.price_agent import PriceAgent
from agents.news_agent import NewsAgent

logger = logging.getLogger("Orchestrator")


def run_agent(agent_factory: Callable) -> None:
    """
    Instancia y ejecuta un agente de forma aislada, capturando cualquier
    excepción no controlada para que no detenga el orquestador.

    Args:
        agent_factory (Callable): Clase del agente a instanciar y ejecutar.
    """
    agent_name = agent_factory.__name__
    try:
        agent = agent_factory()
        success = agent.run()
        if not success:
            logger.warning("[%s] finalizó con estado: FALLO (controlado).", agent_name)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "[%s] excepción no controlada: %s — continuando con el siguiente agente.",
            agent_name,
            exc,
            exc_info=True,
        )


def main() -> None:
    """
    Punto de entrada del orquestador. Define y ejecuta la pipeline de agentes.
    """
    logger.info("===================================")
    logger.info("   GOLD-SENTINEL - Orquestador")
    logger.info("===================================")

    # Pipeline de agentes en orden de ejecución
    pipeline: list[Callable] = [
        PriceAgent,
        NewsAgent,
    ]

    for agent_factory in pipeline:
        run_agent(agent_factory)

    logger.info("Pipeline completada. Todos los agentes procesados.")


if __name__ == "__main__":
    main()
