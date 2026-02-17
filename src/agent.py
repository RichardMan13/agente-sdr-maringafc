import os
import operator
from typing import Annotated, List, TypedDict, Union, Optional
from dotenv import load_dotenv

# LangChain / LangGraph imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import create_client
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage, RemoveMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

# --- 1. Configuração de Clientes ---
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

# --- 2. Definição do Estado ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    context: str
    whatsapp_id: str
    intent_is_sale: bool
    nome_torcedor: Optional[str]
    plano_interesse: Optional[str]
    # Estado interno para controle de fluxo
    loop_step: Annotated[int, operator.add] 

# --- 3. Ferramentas (Tools) ---
@tool("retrieve_docs")
def retrieve_docs(query: str):
    """
    Busca documentos relevantes sobre o Maringá FC, planos de sócio (Maringá Paixão) e jogos.
    Use esta ferramenta para responder perguntas sobre valores, benefícios, datas de jogos e informações institucionais.
    """
    try:
        # Gera embedding da query
        query_embedding = embeddings.embed_query(query)
        
        # Chama RPC no Supabase
        rpc_res = supabase.rpc("match_documents", {
            "query_embedding": query_embedding,
            "match_threshold": 0.5,
            "match_count": 3
        }).execute()
        
        if not rpc_res.data:
            return "Nenhuma informação relevante encontrada no banco de dados."
            
        # Concatena os resultados
        context = "\n\n".join([item['conteudo'] for item in rpc_res.data])
        return context
    except Exception as e:
        return f"Erro ao acessar banco de dados: {str(e)}"

# --- Nova Ferramenta de Busca na Loja ---
@tool("search_store")
def search_store(query: str):
    """
    Busca produtos, preços e disponibilidade diretamente na loja oficial do Maringá FC.
    Use esta ferramenta SEMPRE que o usuário perguntar sobre camisas, acessórios ou produtos físicos.
    URL Base: https://store.maringafc.com/
    """
    search = TavilySearchResults(
        max_results=3,
        search_depth="advanced",
        include_domains=["store.maringafc.com"] # Restringe a busca apenas à loja oficial
    )
    return search.invoke(query)

# Lista de ferramentas disponíveis para o agente
tools = [retrieve_docs, search_store]
tool_node = ToolNode(tools)

# --- 4. Funções de Apoio (Nodes) ---

def parse_messages(messages):
    """Formata mensagens para string (uso em prompts)."""
    return "\n".join([f"{m.type}: {m.content}" for m in messages])

# --- NÓ: Summarizer ---
def summarize_conversation(state: AgentState):
    """Resume a conversa se ficar muito longa."""
    stored_messages = state['messages']
    
    # Exemplo: mantermos apenas ~6 mensagens recentes sem resumir
    if len(stored_messages) <= 6:
        return {}
    
    # Resume tudo exceto as últimas 4
    to_summarize = stored_messages[:-4]
    if not to_summarize:
        return {}
        
    summary_message = parse_messages(to_summarize)
    prompt = f"Resuma a conversa entre Torcedor e Dogão (SDR Maringá FC). Mantenha nome e plano de interesse.\n\n{summary_message}"
    
    response = llm.invoke(prompt)
    summary = response.content
    
    delete_messages = [RemoveMessage(id=m.id) for m in to_summarize]
    summary_msg = SystemMessage(content=f"RESUMO ANTERIOR: {summary}")
    
    return {"messages": delete_messages + [summary_msg]}

# --- NÓ: Agent (Router) ---
def agent_node(state: AgentState):
    """
    Analisa a última mensagem e decide se chama a ferramenta de busca ou responde direto.
    """
    messages = state['messages']
    
    system_prompt = SystemMessage(content="""Você é o "Dogão", o SDR (Pré-vendas) oficial do Maringá FC.
    Sua missão é engajar a torcida e **CONVERTER VENDAS**.
    
    HIERARQUIA DE OBJETIVOS (SDR):
    1. 🏆 VENDER SÓCIO TORCEDOR: Prioridade máxima. Sempre tente conectar o assunto ao plano 'Maringá Paixão'.
    2. 🎫/👕 VENDER INGRESSOS E PRODUTOS: Receita imediata.
    3. 📝 QUALIFICAR LEAD: Extrair Nome e Interesse para o time de vendas.
    
    DIRETRIZES DE FERRAMENTAS:
    - Sócio/Ingressos/Clube: USE 'retrieve_docs'.
    - Camisas/Produtos/Loja: USE 'search_store' para dar preços e opções da loja oficial.
    - Conversa fiada: Responda diretamente.

    COMPORTAMENTO:
    - Seja vibrante, use gírias da torcida (ex: "Pra cima!", "Dogão").
    - NÃO seja passivo. Tire a dúvida e IMEDIATAMENTE faça uma pergunta de fechamento ou convite (ex: "Bora garantir o Sócio hoje?").
    """)
    
    # Filtra system messages antigos para evitar duplicação no contexto da LLM, mantendo o resumo se houver
    filtered_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    # Procura se tem algum resumo (SystemMessage criada pelo summarizer) e mantém
    resumos = [m for m in messages if isinstance(m, SystemMessage) and "RESUMO" in str(m.content)]
    
    final_msgs = [system_prompt] + resumos + filtered_msgs
    
    # Bind tools
    model = llm.bind_tools(tools)
    response = model.invoke(final_msgs)
    
    return {"messages": [response]}

# --- NÓ: Grade Documents ---
class GradeResult(BaseModel):
    relevant: bool = Field(description="True se os documentos contêm a resposta, False caso contrário")

def grade_documents(state: AgentState):
    """
    Avalia se os documentos trazidos pela ferramenta são suficientes.
    """
    messages = state['messages']
    last_tool_msg = messages[-1]
    
    # Defesa: se não for ToolMessage, segue o fluxo
    if not isinstance(last_tool_msg, ToolMessage):
        return {"context": "", "loop_step": 0}

    docs_content = last_tool_msg.content
    
    # Se a busca não retornou nada útil
    if "Nenhuma informação" in docs_content:
        return {"context": docs_content, "loop_step": 1} # Incrementa loop para controle

    # Avaliação com LLM
    # Pegamos a última pergunta do usuário
    human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
    last_question = human_msgs[-1].content if human_msgs else ""
    
    prompt = f"""Pergunta: {last_question}
    Documentos Recuperados: {docs_content}
    
    Os documentos contêm a informação para responder a pergunta? Responda Sim ou Não."""
    
    structured = llm.with_structured_output(GradeResult)
    result = structured.invoke(prompt)
    
    # Se relevante, zera o loop. Se não, incrementa.
    step_inc = 0 if result.relevant else 1
    
    #hack: salvamos 'context' explicitamente para o generate_answer usar
    return {"context": docs_content, "loop_step": step_inc}

# --- NÓ: Rewrite Question ---
def rewrite_question(state: AgentState):
    """
    Reescreve a query para tentar melhorar a busca.
    """
    messages = state['messages']
    human_msgs = [m for m in messages if isinstance(m, HumanMessage)]
    original_query = human_msgs[-1].content if human_msgs else ""
    
    prompt = (
        "Analise a pergunta inicial e tente compreender a intenção semântica subjacente.\n"
        "Aqui está a pergunta inicial:"
        "\n ------- \n"
        f"{original_query}"
        "\n ------- \n"
        "Formule uma pergunta de busca otimizada para o banco de dados vetorial (RAG).\n"
        "Retorne APENAS a nova frase de busca, sem explicações adicionais."
    )
    
    response = llm.invoke(prompt)
    new_query = response.content
    
    print(f"🔄 Reescrevendo: '{original_query}' -> '{new_query}'")
    
    # Instruímos o agente a buscar a nova query
    # Usamos uma HumanMessage injetada 'fingindo' que o usuário pediu essa busca específica
    msg = HumanMessage(content=f"Por favor, pesquise especificamente por: {new_query}")
    
    return {"messages": [msg]}

# --- NÓ: Generate Answer (RAG) ---
def generate_answer(state: AgentState):
    """
    Gera a resposta final usando o contexto validado.
    """
    context = state['context']
    messages = state['messages']
    
    current_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Você é o Dogão, mascote e SDR do Maringá FC.
        Baseado EXCLUSIVAMENTE no contexto abaixo, responda ao torcedor.
        
        CONTEXTO:
        {context}
        
        Se o contexto não tiver a resposta, diga que vai verificar com a diretoria (mas seja simpático).
        """),
        MessagesPlaceholder(variable_name="messages"),
    ])
    
    chain = prompt | llm
    # Passamos as mensagens para manter o fluxo da conversa
    response = chain.invoke({"messages": current_messages, "context": context})
    
    return {"messages": [response]}

# --- NÓ: Lead Tracker (Final) ---
class LeadInfo(BaseModel):
    venda: bool = Field(description="Interesse comercial detectado")
    nome: Optional[str]
    plano: Optional[str]

def classify_and_track(state: AgentState):
    """Extrai intenções e salva dados do lead."""
    messages = state['messages']
    if len(messages) < 2:
        return {"intent_is_sale": False}
        
    history = parse_messages(messages[-6:]) # Analisa últimas mensagens
    
    prompt = f"""Extraia informações do lead da conversa.
    Se o usuário informar nome ou plano, capture.
    
    Histórico:
    {history}
    """
    
    try:
        structured = llm.with_structured_output(LeadInfo)
        res = structured.invoke(prompt)
        
        updates = {}
        if res.nome and res.nome not in ["Torcedor", "Não informado"]:
            updates["nome_torcedor"] = res.nome
        if res.plano and res.plano not in ["A definir", "Não informado"]:
            updates["plano_interesse"] = res.plano
            
        # Persistência
        nome = updates.get("nome_torcedor") or state.get("nome_torcedor") or "Torcedor"
        plano = updates.get("plano_interesse") or state.get("plano_interesse") or "A definir"
        intent = res.venda
        
        if intent or updates:
            print(f"🎯 Atualizando Lead: {nome} | {plano}")
            supabase.table("leads_sdr").upsert({
                "whatsapp_id": state['whatsapp_id'],
                "nome_torcedor": nome,
                "plano_interesse": plano,
                "convertido": False
            }, on_conflict="whatsapp_id").execute()
            
        return {**updates, "intent_is_sale": intent}
        
    except Exception as e:
        print(f"Erro tracking: {e}")
        return {"intent_is_sale": False}

# --- 5. Montagem do Grafo ---
workflow = StateGraph(AgentState)

# Adiciona nós
workflow.add_node("summarizer", summarize_conversation)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tool_node)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("rewrite", rewrite_question)
workflow.add_node("generate", generate_answer)
workflow.add_node("tracker", classify_and_track)

# Define Entry Point
workflow.set_entry_point("summarizer")

# Arestas
workflow.add_edge("summarizer", "agent")

# Decisão do Agent: Tool ou Resposta Direta?
def route_agent(state):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "tracker"

workflow.add_conditional_edges("agent", route_agent, {
    "tools": "tools",
    "tracker": "tracker"
})

workflow.add_edge("tools", "grade_documents")

# Decisão da Grade: Generate ou Rewrite?
def route_grade(state):
    loop_step = state.get("loop_step", 0)
    context = state.get("context", "")
    
    # Se já tentamos reescrever (loop > 0) ou se a resposta veio vazia repetidamente, paramos
    # Se loop_step for 1, significa que falhou a primeira e incrementou. Tentamos rewrite.
    # Se loop_step for 2, já reescreveu e buscou de novo. Se ainda ruim, desiste e gera com o que tem.
    if loop_step > 1: 
        return "generate"
        
    if "Nenhuma informação" in context:
        return "rewrite"
        
    # Se step inc foi 0 -> generate. Se foi 1 -> rewrite.
    # Mas como 'grade_documents' retorna step incrementado, checamos:
    # Se era 0 e virou 1 -> rewrite.
    # Se era 1 e virou 2 -> generate (abort)
    
    # Vamos simplificar: se loop_step > 0 E context ruim -> rewrite.
    # Se loop_step == 0 e context ruim -> rewrite (loop vira 1).
    if loop_step > 0: # Significa que NÓS incrementamos agora indicando falha
        return "rewrite"
        
    return "generate"

workflow.add_conditional_edges("grade_documents", route_grade, {
    "rewrite": "rewrite",
    "generate": "generate"
})

workflow.add_edge("rewrite", "agent")
workflow.add_edge("generate", "tracker")
workflow.add_edge("tracker", END)

# Compilação
dogao_agent = workflow.compile()