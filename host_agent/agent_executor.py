from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_message_text
from agents import Runner
from agent import HostAgent

class HostAgentExecutor(AgentExecutor):
    """Implementación del Executor para el Host Agent."""

    def __init__(self):
        self.host_agent_wrapper = HostAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        # 1. Obtener el texto del usuario
        user_input = get_message_text(context.message) if context.message else ""
        print(f"\n[HOST AGENT] Recibido input:\n{user_input}\n", flush=True)

        # 2. Ejecutar el Agente Host (que usará sus herramientas internas si es necesario)
        result = await Runner.run(self.host_agent_wrapper.agent, user_input)
        
        # 3. Extraer y enviar la respuesta final textualmente
        output_text = result.final_output if isinstance(result.final_output, str) else str(result.final_output)
        print(f"\n[HOST AGENT] Enviando output:\n{output_text}\n", flush=True)
            
        await event_queue.enqueue_event(new_agent_text_message(output_text))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('Cancel not supported')
