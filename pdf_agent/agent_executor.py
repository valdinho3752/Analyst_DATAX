from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_message_text

from agents import Runner
from agent import PdfAgent

class PdfAgentExecutor(AgentExecutor):
    def __init__(self):
        self.pdf_agent_wrapper = PdfAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        user_input = get_message_text(context.message) if context.message else ""
        print(f"\n[PDF AGENT] Recibido input:\n{user_input}\n", flush=True)

        result = await Runner.run(self.pdf_agent_wrapper.agent, user_input)
        
        output_text = str(result.final_output)
        print(f"\n[PDF AGENT] Enviando output:\n{output_text}\n", flush=True)
            
        await event_queue.enqueue_event(new_agent_text_message(output_text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception('Cancel not supported')
