import logging
import sys
import click
import uvicorn
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from agent_executor import PdfAgentExecutor

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host sobre el cual hacer bind.')
@click.option('--port', 'port', default=10005, help='Puerto en el cual correr el servidor.')
def main(host, port):
    try:
        pdf_skill = AgentSkill(
            id='pdf_skill',
            name='PDF Report Generator',
            description='Genera reportes PDF analíticos y formales usando LaTeX.',
            tags=['pdf', 'report', 'latex'],
        )

        agent_card = AgentCard(
            name='PDF Agent',
            description='Agente encargado de diseñar y compilar reportes PDF de alta calidad con LaTeX.',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            default_input_modes=['text'],
            default_output_modes=['text'],
            capabilities=AgentCapabilities(streaming=True, push_notifications=True),
            skills=[pdf_skill],
            supports_authenticated_extended_card=False,
        )

        request_handler = DefaultRequestHandler(
            agent_executor=PdfAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        logger.info(f"Iniciando PDF Agent en http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except Exception as e:
        logger.error(f'Error al arrancar el PDF Agent: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
