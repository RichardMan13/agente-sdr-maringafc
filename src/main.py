from fastapi import FastAPI
from pydantic import BaseModel
from src.agent import dogao_agent  # Importa o grafo compilado

app = FastAPI(title="API SDR Maringá FC")

class ChatRequest(BaseModel):
    message: str
    whatsapp_id: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    # Inicializa o estado para o LangGraph
    inputs = {
        "messages": [("user", req.message)],
        "whatsapp_id": req.whatsapp_id
    }
    
    # Executa o grafo
    result = await dogao_agent.ainvoke(inputs)
    
    # Retorna a última mensagem do chat (a resposta do Dogão)
    return {"response": result["messages"][-1].content}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)