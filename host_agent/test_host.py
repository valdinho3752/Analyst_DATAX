import json
import logging
import asyncio
import httpx
from uuid import uuid4
from a2a.client import A2AClient
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import MessageSendParams, SendMessageRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_host():
    # Usamos 127.0.0.1 para evitar problemas de resolución de 'localhost' en Windows
    # agent_url = "http://host_agent_openai:10002/"
    agent_url = "http://localhost:10002/"
    logger.info(f"Connecting to Host Agent at: {agent_url}")
    
    async with httpx.AsyncClient(timeout=120.0) as httpx_client:
        resolver = A2ACardResolver(httpx_client, agent_url)
        card = await resolver.get_agent_card()
        logger.info(f"Agent Card fetched: {card.name}")
        
        client = A2AClient(httpx_client, card, url=agent_url)
        
        query = "Cual es el monto del activo disponible con el que cerro su gestión BISA seguros en los últimos 3 años?"
        logger.info(f"Sending query to Host: {query}")
        
        send_message_payload = {
            'message': {
                'role': 'user',
                'parts': [
                    {'type': 'text', 'text': query}
                ],
                'messageId': uuid4().hex,
            },
        }
        
        request = SendMessageRequest(
            id=str(uuid4()), 
            params=MessageSendParams.model_validate(send_message_payload)
        )
        
        try:
            response = await client.send_message(request)
            print("\n--- Respuesta del Host Agent ---")
            print(response.model_dump_json(indent=2, exclude_none=True))
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")

if __name__ == "__main__":
    asyncio.run(test_host())
