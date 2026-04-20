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

from agent_executor import GraphAgentExecutor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MissingAPIKeyError(Exception):
    pass

@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host sobre el cual hacer bind.')
@click.option('--port', 'port', default=10003, help='Puerto en el cual correr el servidor.')
def main(host, port):
    """Inicia el servidor del Graph Agent."""
    try:
        graph_skill = AgentSkill(
            id='graph_validation_skill',
            name='Graph Validation Skill',
            description='Valida la estructura semántica de una tabla consultando un Knowledge Graph',
            tags=['graph', 'neo4j', 'validation'],
        )

        public_agent_card = AgentCard(
            name='Graph Agent',
            description='Especialista en validar tablas con Neo4j para evitar alucinaciones',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            default_input_modes=['text'],
            default_output_modes=['text'],
            capabilities=AgentCapabilities(streaming=True, push_notifications=True),
            skills=[graph_skill],
            supports_authenticated_extended_card=False,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=GraphAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=public_agent_card,
            http_handler=request_handler,
        )

        logger.info(f"Iniciando servidor de agente en http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except Exception as e:
        logger.error(f'Ocurrió un error inesperado al arrancar el servidor: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
