import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from supabase import create_client
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from urllib.parse import urljoin, urlparse

load_dotenv()

# Configurações
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

def is_valid_url(url, base_domain):
    """Garante que ficaremos apenas dentro do site do Maringá FC."""
    parsed = urlparse(url)
    return parsed.netloc == base_domain and not parsed.fragment

def get_all_links(base_url):
    """Crawler simples para mapear as páginas do site."""
    domain = urlparse(base_url).netloc
    links = {base_url}
    try:
        response = requests.get(base_url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            full_url = urljoin(base_url, a['href'])
            if is_valid_url(full_url, domain):
                links.add(full_url)
    except Exception as e:
        print(f"Erro ao mapear links: {e}")
    return links

def scrape_and_process(url):
    """Extrai e limpa o conteúdo textual de uma página."""
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Remove ruídos comuns de sites e elementos de navegação
        for script_or_style in soup(["script", "style", "nav", "footer", "header", "aside", "form", "button", "iframe"]):
            script_or_style.decompose()
        
        # Remove elementos com classes suspeitas de serem ruído
        for tag in soup.find_all(class_=lambda x: x and any(cls in x.lower() for cls in ['voltar', 'back', 'menu', 'share', 'print', 'hidden'])):
            tag.decompose()

        texto = soup.get_text(separator=' ')
        
        # Limpeza de espaços extras e linhas inúteis
        linhas = (line.strip() for line in texto.splitlines())
        
        # Filtra linhas muito curtas ou irrelevantes que sobraram
        keywords_ignore = {"voltar", "imprimir", "compartilhar", "menu", "topo", "anterior", "próxima"}
        
        def is_useful(line):
            if not line: return False
            if line.lower() in keywords_ignore: return False
            if len(line.split()) < 2 and len(line) < 15: # Linhas muito curtas (ex: datas soltas, labels menu)
                return False
            return True

        chunks_texto = (phrase.strip() for line in linhas for phrase in line.split("  "))
        texto_limpo = '\n'.join(chunk for chunk in chunks_texto if is_useful(chunk))

        # Splitter adaptado
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=100,
            separators=["\n\n", "\n", ".", " "]
        )
        return splitter.split_text(texto_limpo)
    except Exception as e:
        print(f"Erro no scraping da URL {url}: {e}")
        return []

def main():
    base_url = "https://maringafc.com.br/"
    paginas = get_all_links(base_url)
    print(f"🕸️ {len(paginas)} páginas encontradas para processamento.")

    for url in paginas:
        chunks = scrape_and_process(url)
        if not chunks: continue

        records = []
        for chunk in chunks:
            vector = embeddings_model.embed_query(chunk)
            records.append({
                "categoria": "web_scraping",
                "conteudo": chunk,
                "embedding": vector,
                "fonte_url": url
            })

        # Upsert no Supabase
        supabase.table("conhecimento_clube").insert(records).execute()
        print(f"✅ URL Processada: {url} ({len(chunks)} chunks)")

if __name__ == "__main__":
    main()