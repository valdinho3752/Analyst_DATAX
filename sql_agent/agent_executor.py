from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_message_text

from agents import Runner
from agents.mcp import MCPServerManager
from agent import SqlAgent

class SqlAgentExecutor(AgentExecutor):
    """Test AgentProxy Implementation."""

    def __init__(self):
        self.sql_agent_wrapper = SqlAgent()

    # --8<-- [end:HelloWorldAgentExecutor_init]
    # --8<-- [start:HelloWorldAgentExecutor_execute]
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # 1. Obtener el texto que el usuario envió desde el contexto de A2A
        user_input = get_message_text(context.message) if context.message else ""
        print(f"\n[SQL AGENT] Recibido input:\n{user_input}\n", flush=True)

        async with MCPServerManager(self.sql_agent_wrapper.mcp_servers) as server:
            result = await Runner.run(self.sql_agent_wrapper.agent, user_input)
            
        # 3. Extraer el resultado (que es de tipo existing_Output)
        # Pydantic te permite convertirlo a JSON fácilmente
        output_data = result.final_output.model_dump_json(indent=2)
        print(f"\n[SQL AGENT] Enviando output:\n{output_data}\n", flush=True)
            
        # 4. Enviar el JSON de respuesta de vuelta a A2A
        await event_queue.enqueue_event(new_agent_text_message(output_data))
    # --8<-- [end:HelloWorldAgentExecutor_execute]

    # --8<-- [start:HelloWorldAgentExecutor_cancel]
    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')

    # --8<-- [end:HelloWorldAgentExecutor_cancel]