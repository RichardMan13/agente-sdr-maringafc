import os
import asyncio
import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.agent import dogao_agent

# Carrega variáveis de ambiente
load_dotenv()

def testar_agente():
    print("--- Iniciando Teste Local do Agente Dogão ---")
    
    # Simula uma mensagem de um torcedor com intenção de compra clara
    mensagem_usuario = "Gostei do plano Maringá Paixão. Meu nome é Marcos Teste e meu whatsapp é 44999887766. Quero fechar agora!"
    print(f"\n👤 Usuário: {mensagem_usuario}")
    
    # Estado inicial com ID único para a mensagem (crítico para lógica de remove_message)
    initial_state = {
        "messages": [HumanMessage(content=mensagem_usuario, id=str(uuid.uuid4()))],
        "whatsapp_id": "5544999887766",
        "intent_is_sale": False
    }

    try:
        # Invoca o agente
        print("🤖 Processando... (Aguarde a consulta ao VectorStore e LLM)")
        result = dogao_agent.invoke(initial_state)
        
        # Extrai a resposta do agente
        mensagens = result.get("messages", [])
        if mensagens:
            ultima_mensagem = mensagens[-1]
            print(f"\n🐕 Dogão: {ultima_mensagem.content}")
        else:
            print("\n❌ Nenhuma resposta gerada.")
            
        # Opcional: Mostrar o estado final para debug
        # print(f"\n🔍 Estado Final: {result}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n❌ Erro ao executar o agente: {e}")

if __name__ == "__main__":
    testar_agente()
