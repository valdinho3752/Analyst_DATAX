from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_message_text

from agents import Runner
from agent import SqlExecutorAgent

class SqlExecutorAgentExecutor(AgentExecutor):
    """Implementación del ejecutor para el Agente de SQL Executor."""

    def __init__(self):
        self.wrapper = SqlExecutorAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # 1. Obtener el texto que el usuario envió (usualmente el SQL generado por el agente anterior)
        user_input = get_message_text(context.message) if context.message else ""
        print(f"\n[SQL EXECUTOR] Ejecutando comando recibido...\n", flush=True)

        # 2. Correr el agente (este agente no usa MCP servers externos, solo herramientas locales)
        result = await Runner.run(self.wrapper.agent, user_input)
            
        # 3. Extraer el resultado final (que es el Markdown del DataFrame)
        output_data = result.final_output
        print(f"\n[SQL EXECUTOR] Enviando resultados de la consulta.\n", flush=True)
            
        # 4. Enviar la respuesta de vuelta a A2A
        await event_queue.enqueue_event(new_agent_text_message(str(output_data)))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')
