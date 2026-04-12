import httpx
import uuid
from typing import Any
from a2a.client import A2AClient, A2ACardResolver
from a2a.types import SendMessageRequest, MessageSendParams, SendMessageResponse

class RemoteAgentConnection:
    """Maneja la conexión hacia un sub-agente remoto usando el protocolo A2A."""
    
    def __init__(self, agent_url: str):
        self.agent_url = agent_url
        self._httpx_client = httpx.AsyncClient(timeout=60)
        self.client = None
        self.card = None

    async def initialize(self):
        """Resuelve la Agent Card e inicializa el cliente."""
        resolver = A2ACardResolver(self._httpx_client, self.agent_url)
        self.card = await resolver.get_agent_card()
        self.client = A2AClient(self._httpx_client, self.card, url=self.agent_url)

    async def send_message(self, text: str) -> Any:
        """Envía un mensaje de texto al agente remoto y devuelve la respuesta."""
        if not self.client:
            await self.initialize()

        message_id = str(uuid.uuid4())
        payload = {
            'message': {
                'role': 'user',
                'parts': [{'type': 'text', 'text': text}],
                'messageId': message_id,
            },
        }

        request = SendMessageRequest(
            id=message_id, 
            params=MessageSendParams.model_validate(payload)
        )
        
        response: SendMessageResponse = await self.client.send_message(request)
        return response.root.result
