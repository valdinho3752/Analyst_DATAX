import os
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

COLLECTION_NAME = "rag_metadata_demo_openia"
VECTOR_NAME = "openai-embedding"
MODEL_NAME = "text-embedding-3-small"
QDRANT_URL = "http://localhost:6337"

client_openai = OpenAI()
qdrant_client = QdrantClient(url=QDRANT_URL)

def test_search(query: str, limit: int = 30):
    print(f"--- 🧠 Buscando puntos relevantes para: '{query}' ---")

    query_vector = client_openai.embeddings.create(
        input=[query],
        model=MODEL_NAME
    ).data[0].embedding

    points = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        using=VECTOR_NAME,
        limit=limit,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="tipo",
                    match=models.MatchValue(value="miembro_dimension")
                ),
                models.FieldCondition(
                    key="tabla_origen",
                    match=models.MatchValue(value="S_BOAPS_44_000612")
                )
            ]
        ),
        with_payload=True
    ).points

    print(f"Se encontraron {len(points)} puntos. Detalles:\n")
    for i, point in enumerate(points):
        tipo = point.payload.get("tipo", "N/A")
        origen = point.payload.get("tabla_origen", point.payload.get("nombre_tabla", "N/A"))
        columna = point.payload.get("nombre_columna", "N/A")
        valor = point.payload.get("valor_miembro", "N/A")
        desc = point.payload.get("Descripcion", point.payload.get("Descripcion tabla", "N/A"))[:50]
        
        print(f"{i+1}. Score: {point.score:.4f} | Tipo: {tipo} | Tabla: {origen}")
        if tipo == "miembro_dimension":
            print(f"   Columna: {columna} | Valor: {valor}")
        else:
            print(f"   Columna: {columna} | Desc: {desc}...")

if __name__ == "__main__":
    prompt = "disponible en bancos"
    test_search(prompt, limit=30)
