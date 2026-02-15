import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.agent import dogao_agent
import uvicorn

app = FastAPI(title="Agente SDR Maringá FC - API")

class ChatRequest(BaseModel):
    message: str
    whatsapp_id: str

@app.get("/")
async def health_check():
    return {"status": "online", "agente": "Dogão SDR"}

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        # Inicializa o estado com a mensagem do usuário
        # O LangGraph cuidará do roteamento entre retriever, chat e tracker
        inputs = {
            "messages": [("user", req.message)],
            "whatsapp_id": req.whatsapp_id
        }
        
        # Execução assíncrona do Grafo
        result = await dogao_agent.ainvoke(inputs)
        
        # Extrai a última mensagem da lista (a resposta da IA)
        final_message = result["messages"][-1].content
        
        return {
            "response": final_message,
            "nome_identificado": result.get("nome_torcedor"),
            "plano": result.get("plano_interesse")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Porta 80 é o padrão para o Azure App Service
    port = int(os.environ.get("PORT", 80))
    uvicorn.run(app, host="0.0.0.0", port=port)