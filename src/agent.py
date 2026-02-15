import os
import json
from typing import Annotated, TypedDict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Imports atualizados conforme requirements.txt e padrões LangChain 0.3+
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import create_client
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

load_dotenv()

# 1. Configuração de Clientes
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# 2. Configuração do Retriever (RAG)
vector_store = SupabaseVectorStore(
    client=supabase,
    embedding=embeddings,
    table_name="conhecimento_clube",
    query_name="match_documents",
)
retriever = vector_store.as_retriever(search_kwargs={'k': 3})

# 3. Definição do Estado do Grafo
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    context: str
    whatsapp_id: str
    intent_is_sale: bool
    nome_torcedor: Optional[str] # Memória persistente
    plano_interesse: Optional[str] # Memória persistente

# --- FUNÇÕES DE APOIO (AÇÕES DO GRAFO) ---

def retrieve_docs(state: AgentState):
    """Busca documentos diretamente via RPC no Supabase para evitar bug de versão."""
    last_message = state['messages'][-1].content
    
    # Query Rewriting: Reescreve a pergunta usando o histórico recente para dar contexto ao Vector Store
    # Evita buscas vagas como "quanto custa?" -> "quanto custa o plano Maringá Paixão?"
    historico_recente = parse_messages(state['messages'][-4:]) # Pega as últimas 4 mensagens
    prompt_rewrite = f"""Reescreva a última pergunta do usuário para que ela seja independente e completa, baseada no histórico.
    Histórico: {historico_recente}
    Pergunta original: {last_message}
    Responda APENAS a pergunta reescrita."""
    
    try:
        busca_otimizada = llm.invoke(prompt_rewrite).content
        print(f"🔄 Busca Original: '{last_message}' | Busca Otimizada: '{busca_otimizada}'")
    except:
        busca_otimizada = last_message
    
    # 1. Gera o embedding da pergunta otimizada
    query_embedding = embeddings.embed_query(busca_otimizada)
    
    # 2. Chama a função RPC 'match_documents' que criamos no SQL Editor
    # Isso pula o erro do 'SyncRPCFilterRequestBuilder'
    rpc_res = supabase.rpc("match_documents", {
        "query_embedding": query_embedding,
        "match_threshold": 0.5, # Ajuste conforme necessidade
        "match_count": 3
    }).execute()
    
    # 3. Processa os resultados
    if not rpc_res.data:
        return {"context": "Nenhuma informação encontrada no banco."}
        
    context = "\n\n".join([item['conteudo'] for item in rpc_res.data])

    return {"context": context}

def summarize_conversation(state: AgentState):
    """Resume a conversa se houver muitas mensagens para economizar tokens."""
    
    # Mantém as últimas 4 mensagens (aprox) + a System Message inicial (se houver)
    # O resto será resumido. 
    stored_messages = state['messages']
    
    # Se tiver poucas mensagens, não faz nada
    if len(stored_messages) <= 6:
        return {}
    
    # Identifica o que será resumido (tudo exceto as últimas 4)
    # Assume que a primeira mensagem pode ser um SystemMessage fixo ou não.
    # Vamos resumir tudo exceto as 4 últimas para garantir contexto recente.
    to_summarize = stored_messages[:-4]
    
    if not to_summarize:
        return {}
        
    # Gera o resumo usando a LLM
    # Cria um prompt específico para a sumarização
    summary_message = parse_messages(to_summarize)
    prompt = f"Resuma a seguinte conversa entre um Torcedor e o Dogão (SDR do Maringá FC). Mantenha detalhes sobre o Torcedor (nome, plano de interesse, dúvidas). \n\nConversa:\n{summary_message}"
    
    response = llm.invoke(prompt)
    summary = response.content
    
    # Cria a lista de remoção (apaga as mensagens antigas do histórico via ID)
    delete_messages = [RemoveMessage(id=m.id) for m in to_summarize]
    
    # Cria a mensagem de resumo para injetar no histórico como uma SystemMessage
    # Isso garante que o modelo saiba o que aconteceu antes
    summary_msg = SystemMessage(content=f"RESUMO DA CONVERSA ANTERIOR: {summary}")
    
    print(f"📉 Resumindo {len(to_summarize)} mensagens antigas...")
    
    # Retorna as remoções E a nova mensagem de resumo
    return {"messages": delete_messages + [summary_msg]}

def parse_messages(messages):
    """Helper para formatar mensagens para o prompt de resumo"""
    return "\\n".join([f"{m.type}: {m.content}" for m in messages])

class LeadInfo(BaseModel):
    venda: bool = Field(description="Indica se o usuário demonstrou interesse claro em comprar algo ou saber sobre planos")
    nome: Optional[str] = Field(default=None, description="Nome do torcedor, se informado")
    plano: Optional[str] = Field(default=None, description="Plano de interesse, se informado")

def call_model(state: AgentState):
    """Gera a resposta da Persona Dogão."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Você é o "Dogão", o SDR oficial do Maringá FC. 
        Seja extrovertido, apaixonado e persuasivo. Use o CONTEXTO para responder.
        Se houver interesse em planos, capture Nome e WhatsApp.
        
        CONTEXTO:
        {context}"""),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    chain = prompt | llm
    
    # A otimização de mensagens agora é feita pelo nó 'summarizer',
    # então passamos todas as mensagens disponíveis no estado (que já estarão resumidas/cortadas)
    response = chain.invoke({"messages": state['messages'], "context": state['context']})
    return {"messages": [response]}

def classify_and_track(state: AgentState):
    """Analisa intenção e salva lead na tabela leads_sdr se necessário."""
    
    # Verificação de segurança: se houver menos de 2 mensagens, não há o que comparar
    if len(state['messages']) < 2:
        return {"intent_is_sale": False}
    # Validação de intenção usando Structured Output (Pydantic)
    # Analisa TODO o histórico de mensagens para não perder informações (ex: nome dito anteriormente)
    historico_conversa = parse_messages(state['messages'])
    
    prompt_analise = f"""Analise o histórico da conversa abaixo e extraia intenções de venda.
    
    Dados Atuais no Sistema:
    - Nome: {state.get('nome_torcedor') or 'Não informado'}
    - Plano: {state.get('plano_interesse') or 'Não informado'}
    
    Instruções:
    1. Se o "Nome" já estiver preenchido, SÓ extraia um novo nome se o usuário corrigir explicitamente (ex: "Não é João, é Pedro").
    2. Se o "Plano" mudar, atualize para o novo.
    
    Histórico:
    {historico_conversa}
    """

    try:
        # Usa with_structured_output para garantir JSON válido (Extração de JSON Instável)
        structured_llm = llm.with_structured_output(LeadInfo)
        lead_data = structured_llm.invoke(prompt_analise)
        
        # Lógica de Persistência com Resolução de Conflitos
        updates = {}
        
        # Só atualiza o nome se ainda não tiver um, ou se a LLM indicar troca explícita (pode ser refinado no prompt)
        current_nome = state.get('nome_torcedor')
        new_nome = lead_data.nome
        
        if new_nome and new_nome != "Torcedor Interessado":
             # Se já temos um nome e o novo é diferente, só troca se parecer uma correção (Regra simples: sempre confia no último por enquanto, mas loga)
            if current_nome and current_nome != new_nome:
                 print(f"⚠️ Atualizando Nome: {current_nome} -> {new_nome}")
            updates['nome_torcedor'] = new_nome
            
        # Mesmo para plano
        current_plano = state.get('plano_interesse')
        new_plano = lead_data.plano
        if new_plano and new_plano != "A definir":
            updates['plano_interesse'] = new_plano
            
        # Define os valores finais para o UPSERT (prioriza o estado atualizado)
        nome_final = updates.get('nome_torcedor') or current_nome or "Torcedor Interessado"
        plano_final = updates.get('plano_interesse') or current_plano or "A definir"
        
        if lead_data.venda:
            supabase.table("leads_sdr").upsert({
                "whatsapp_id": state['whatsapp_id'],
                "nome_torcedor": nome_final,
                "plano_interesse": plano_final,
                "convertido": False
            }, on_conflict="whatsapp_id").execute()
            print(f"🎯 Lead registrado: {nome_final}")
            
        # Retorna atualizações para o estado (se houver) + intenção
        return {**updates, "intent_is_sale": True}
        
    except Exception as e:
        print(f"⚠️ Erro no tracking: {e}")
        return {"intent_is_sale": False}

# 4. Construção do Fluxo (LangGraph)
workflow = StateGraph(AgentState)

# Lógica condicional para definir se precisa resumir
def should_summarize(state: AgentState):
    """Retorna o próximo nó baseado no tamanho do histórico."""
    messages = state['messages']
    
    # Se tiver mais de 6 mensagens, vai para o summarizer
    if len(messages) > 6:
        return "summarizer"
    
    # Caso contrário, segue o fluxo normal
    return "dogao_chat"

workflow.add_node("retriever", retrieve_docs)
workflow.add_node("summarizer", summarize_conversation)
workflow.add_node("dogao_chat", call_model)
workflow.add_node("lead_tracker", classify_and_track)

workflow.set_entry_point("retriever")

# Arestas condicionais
workflow.add_conditional_edges(
    "retriever",
    should_summarize,
    {
        "summarizer": "summarizer",
        "dogao_chat": "dogao_chat"
    }
)

# Aresta normal para voltar do summarizer para o chat
workflow.add_edge("summarizer", "dogao_chat")
workflow.add_edge("dogao_chat", "lead_tracker")
workflow.add_edge("lead_tracker", END)

# Compila o Agente
dogao_agent = workflow.compile()