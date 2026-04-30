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

from agent_executor import SqlExecutorAgentExecutor

# Carga variables de entorno
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host sobre el cual hacer bind.')
@click.option('--port', 'port', default=10004, help='Puerto en el cual correr el servidor.')
def main(host, port):
    """Inicia el servidor del SQL Executor Agent."""
    try:
        # Definir Skills
        execution_skill = AgentSkill(
            id='execution_skill',
            name='SQL Execution Skill',
            description='Ejecuta consultas SQL en Postgres y devuelve resultados en DataFrames',
            tags=['SQL', 'Execution', 'Postgres'],
        )

        # Agent Card
        public_agent_card = AgentCard(
            name='SQL Executor Agent',
            description='Agente especializado en la ejecución técnica de SQL y manejo de datos con Pandas',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            default_input_modes=['text'],
            default_output_modes=['text'],
            capabilities=AgentCapabilities(streaming=True, push_notifications=True),
            skills=[execution_skill],
            supports_authenticated_extended_card=False,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=SqlExecutorAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=public_agent_card,
            http_handler=request_handler,
        )

        logger.info(f"Iniciando servidor de agente ejecutor en http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except Exception as e:
        logger.error(f'Ocurrió un error inesperado al arrancar el servidor: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
