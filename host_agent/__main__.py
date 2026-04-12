import logging
import os
import sys

import click
import uvicorn
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

from agent_executor import HostAgentExecutor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MissingAPIKeyError(Exception):
    """Excepción para cuando faltan claves de API necesarias."""
    pass

@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host sobre el cual hacer bind.')
@click.option('--port', 'port', default=10002, help='Puerto en el cual correr el servidor.')
def main(host, port):
    """Inicia el servidor del Host Agent."""
    try:
        # Validar variables de entorno si es necesario
        # if not os.getenv('OPENAI_API_KEY'):
        #     raise MissingAPIKeyError('La variable de entorno OPENAI_API_KEY no está configurada.')

        orchestration_skill = AgentSkill(
            id='orchestration_skill',
            name='Orchestrator',
            description='Coordina la consulta con los expertos en datos (Data Scout y SQL Analyst).',
            tags=['Orchestrator', 'Manager'],
        )

        agent_card = AgentCard(
            name='Analyst DATAX (Host)',
            description='Analista principal encargado de coordinar la verificación y análisis de datos de seguros.',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            default_input_modes=['text'],
            default_output_modes=['text'],
            capabilities=AgentCapabilities(streaming=True, push_notifications=True),
            skills=[orchestration_skill],
            supports_authenticated_extended_card=False,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=HostAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        logger.info(f"Iniciando Host Agent en http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except Exception as e:
        logger.error(f'Error al arrancar el Host Agent: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
