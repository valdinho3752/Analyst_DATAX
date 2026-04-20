from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils import new_agent_text_message, get_message_text

from agents import Runner
from agents.mcp import MCPServerManager
from agent import GraphAgent

class GraphAgentExecutor(AgentExecutor):
    def __init__(self):
        self.graph_agent_wrapper = GraphAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        user_input = get_message_text(context.message) if context.message else ""
        print(f"\n[GRAPH AGENT] Recibido input:\n{user_input}\n", flush=True)

        async with MCPServerManager(self.graph_agent_wrapper.mcp_servers) as server:
            result = await Runner.run(self.graph_agent_wrapper.agent, user_input)
            
        output_data = result.final_output.model_dump_json(indent=2)
        print(f"\n[GRAPH AGENT] Enviando output:\n{output_data}\n", flush=True)
            
        await event_queue.enqueue_event(new_agent_text_message(output_data))

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception('cancel not supported')
