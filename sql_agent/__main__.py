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

from agent_executor import SqlAgentExecutor
# from agent_executor import (
    # HelloWorldAgentExecutor,  # type: ignore[import-untyped]
# )


# Carga variables de entorno desde un archivo .env si existe
load_dotenv()

# Configuración básica del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MissingAPIKeyError(Exception):
    """Excepción para cuando faltan claves de API necesarias."""
    pass


@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host sobre el cual hacer bind.')
@click.option('--port', 'port', default=10001, help='Puerto en el cual correr el servidor.')
def main(host, port):
    """Inicia el servidor del Rag Agent."""
    try:
        # Validar variables de entorno (puedes descomentar esto cuando necesites que sí o sí haya una llave cargada)
        # if not os.getenv('OPENAI_API_KEY'):
        #     raise MissingAPIKeyError('La variable de entorno OPENAI_API_KEY no está configurada.')

        # --8<-- [start:AgentSkill]
        structure_skill = AgentSkill(
            id='structure_skill',
            name='Structure Skill',
            description='Analiza la estructura de la base de datos y genera consultas SQL para obtener datos',
            tags=['structure'],
            # examples=['hi', 'hello world'],
        )
        # --8<-- [end:AgentSkill]
        exact_match_skill = AgentSkill(
            id='exact_match_skill',
            name='Exact Match Skill',
            description='Verifica que la tablas, columnas y campos referenciados en la consulta existen dentro de la base de datos',
            tags=['exact_match'],
            # examples=['hi', 'hello world'],
        )
        sql_skill = AgentSkill(
            id='sql_skill',
            name='SQL Skill',
            description='Genera consultas SQL para obtener datos de la base de datos',
            tags=['SQL', 'sql_skill'],
            examples=['check coherence', 'verify query'],
        )

        # --8<-- [start:AgentCard]
        # This will be the public-facing agent card
        public_agent_card = AgentCard(
            name='SQL Agent',
            description='Analiza la estructura de la base de datos y genera consultas SQL para obtener datos',
            url=f'http://localhost:{port}/',
            version='1.0.0',
            default_input_modes=['text'],
            default_output_modes=['text'],
            capabilities=AgentCapabilities(streaming=True, push_notifications=True),
            skills=[structure_skill, exact_match_skill, sql_skill],  # Only the basic skill for the public card
            supports_authenticated_extended_card=False,
        )
        # --8<-- [end:AgentCard]

        # This will be the authenticated extended agent card
        # It includes the additional 'extended_skill'
        # specific_extended_agent_card = public_agent_card.model_copy(
        #     update={
        #         'name': 'Hello World Agent - Extended Edition',  # Different name for clarity
        #         'description': 'The full-featured hello world agent for authenticated users.',
        #         'version': '1.0.1',  # Could even be a different version
        #         # Capabilities and other fields like url, default_input_modes, default_output_modes,
        #         # supports_authenticated_extended_card are inherited from public_agent_card unless specified here.
        #         'skills': [
        #             skill,
        #             extended_skill,
        #         ],  # Both skills for the extended card
        #     }
        # )

        request_handler = DefaultRequestHandler(
            agent_executor=SqlAgentExecutor(),
            task_store=InMemoryTaskStore(),
        )

        server = A2AStarletteApplication(
            agent_card=public_agent_card,
            http_handler=request_handler,
            # extended_agent_card=specific_extended_agent_card,
        )

        logger.info(f"Iniciando servidor de agente en http://{host}:{port}")
        uvicorn.run(server.build(), host=host, port=port)

    except MissingAPIKeyError as e:
        logger.error(f'Error de Inicialización: {e}')
        sys.exit(1)
    except Exception as e:
        logger.error(f'Ocurrió un error inesperado al arrancar el servidor: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
