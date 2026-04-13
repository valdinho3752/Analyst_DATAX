import json
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el .env de la raíz
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ================= CONFIGURACIÓN =================
# Referencia al archivo de chunks en la otra carpeta
INPUT_FILE = "../metadata/chunks_demo2.json"
COLLECTION_NAME = "rag_metadata_demo_openia"
QDRANT_URL = "http://localhost:6337"

MODEL_NAME = "text-embedding-3-small"
VECTOR_NAME = "openai-embedding" 
VECTOR_SIZE = 1536 # Tamaño por defecto de text-embedding-3-small

client_openai = OpenAI()
client_qdrant = QdrantClient(url=QDRANT_URL)

def get_embeddings_openai(texts):
    """Obtiene embeddings de OpenAI"""
    response = client_openai.embeddings.create(
        input=texts,
        model=MODEL_NAME
    )
    return [item.embedding for item in response.data]

def main():
    # Construir ruta absoluta al archivo de entrada
    input_path = os.path.abspath(os.path.join(os.path.dirname(__file__), INPUT_FILE))
    
    print(f"📖 Leyendo archivo: {input_path}...")
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    except Exception as e:
        print(f"❌ Error al leer archivo: {e}")
        return

    total_chunks = len(chunks)
    
    # 1. Preparar Colección
    print(f"📡 Conectando a Qdrant en {QDRANT_URL}...")
    client_qdrant.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            VECTOR_NAME: models.VectorParams(
                size=VECTOR_SIZE, 
                distance=models.Distance.COSINE
            )
        }
    )
    print(f"✅ Colección '{COLLECTION_NAME}' reiniciada con tamaño {VECTOR_SIZE}.")

    # 2. Vectorizar y Subir
    textos_todos = [c["texto"] for c in chunks]
    BATCH_SIZE = 100 
    
    print(f"🚀 Procesando {total_chunks} items en lotes de {BATCH_SIZE}...")
    
    for i in range(0, total_chunks, BATCH_SIZE):
        fin = min(i + BATCH_SIZE, total_chunks)
        batch_texts = textos_todos[i:fin]
        batch_chunks = chunks[i:fin]
        
        try:
            # Llamada a OpenAI
            batch_vectores = get_embeddings_openai(batch_texts)
            
            points = []
            for idx, vec in enumerate(batch_vectores):
                # Extraer y preparar payload
                payload_actual = batch_chunks[idx].get("payload", {})
                payload_actual["document"] = batch_chunks[idx]["texto"]

                points.append(models.PointStruct(
                    id=i + idx,
                    vector={VECTOR_NAME: vec},
                    payload=payload_actual 
                ))
            
            # Subir a Qdrant
            operation_info = client_qdrant.upsert(
                collection_name=COLLECTION_NAME, 
                wait=True,
                points=points
            )
            print(f"💾 Bloque {i}-{fin} subido. Status: {operation_info.status}")

        except Exception as e:
            print(f"❌ Error en lote {i}-{fin}: {e}")

    # Verificación final
    info = client_qdrant.get_collection(COLLECTION_NAME)
    print(f"\n✅ Proceso terminado. Puntos totales en Qdrant: {info.points_count}")

if __name__ == "__main__":
    main()
