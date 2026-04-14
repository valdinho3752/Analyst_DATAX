import os
import json
import logging
import asyncio
import httpx
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from a2a.client import A2AClient
from a2a.client.card_resolver import A2ACardResolver
from a2a.types import MessageSendParams, SendMessageRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Analyst DATAX Premium UI")

# Configurar CORS en caso de usar servidores separados (dev mode)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:10002/")

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")

    if not query:
        return JSONResponse({"error": "No query provided"}, status_code=400)

    logger.info(f"Received query from UI: {query}")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as httpx_client:
            resolver = A2ACardResolver(httpx_client, AGENT_URL)
            card = await resolver.get_agent_card()
            
            client = A2AClient(httpx_client, card, url=AGENT_URL)
            
            send_message_payload = {
                'message': {
                    'role': 'user',
                    'parts': [
                        {'type': 'text', 'text': query}
                    ],
                    'messageId': uuid4().hex,
                },
            }
            
            req_params = SendMessageRequest(
                id=str(uuid4()), 
                params=MessageSendParams.model_validate(send_message_payload)
            )
            
            response = await client.send_message(req_params)
            
            # Formatear y retornar la salida estructurada
            return JSONResponse(json.loads(response.model_dump_json(exclude_none=True)))
            
    except Exception as e:
        logger.error(f"Error proxying to Host Agent: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Montar los assets estáticos
base_dir = os.path.dirname(os.path.abspath(__file__))
public_dir = os.path.join(base_dir, "public")
app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    # Correr servidor en puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
