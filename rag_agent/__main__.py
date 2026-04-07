import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import RagAgentExecutor
# from agent_executor import (
    # HelloWorldAgentExecutor,  # type: ignore[import-untyped]
# )


if __name__ == '__main__':
    # --8<-- [start:AgentSkill]
    datascout_skill = AgentSkill(
        id='rag_agent_skill',
        name='datascout',
        description='Verifica que la consulta hecha por el usuario existe dentro de la base de datos',
        tags=['Rag', 'datascout'],
        # examples=['hi', 'hello world'],
    )
    # --8<-- [end:AgentSkill]

    coherence_skill = AgentSkill(
        id='coherence_skill',
        name='Coherence Checker',
        description='Verifica que la consulta hecha por el usuario es coherente',
        tags=['Rag', 'coherence'],
        examples=['check coherence', 'verify query'],
    )

    # --8<-- [start:AgentCard]
    # This will be the public-facing agent card
    public_agent_card = AgentCard(
        name='Rag Agent',
        description='Verifica que la consulta hecha por el usuario es coherente y existe dentro de la base de datos',
        url='http://localhost:10000/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[datascout_skill, coherence_skill],  # Only the basic skill for the public card
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
        agent_executor=RagAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
        # extended_agent_card=specific_extended_agent_card,
    )

    uvicorn.run(server.build(), host='0.0.0.0', port=10000)
