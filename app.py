import streamlit as st
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import time

# Configuração da página deve ser a PRIMEIRA chamada Streamlit
st.set_page_config(
    page_title="NotebookLM Campo",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================
# 1. CONFIGURAÇÃO E CONSTANTES
# ============================================
DOCS_DIR = Path("./documentos")
CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(exist_ok=True)
CHUNK_SIZE = 5000  # Caracteres por chunk para processamento

# ============================================
# 2. FUNÇÃO DE PRÉ-PROCESSAMENTO (RODA UMA VEZ)
# ============================================
def processar_pdfs_para_texto():
    """
    Lê todos os PDFs da pasta /documentos e gera um arquivo JSON leve.
    Só executa se o arquivo cache não existir ou se houver mudanças nos PDFs.
    """
    cache_file = CACHE_DIR / "documentos_processados.json"
    
    # Verifica se já existe cache
    if cache_file.exists():
        # Verifica se algum PDF foi modificado
        cache_mtime = cache_file.stat().st_mtime
        pdfs_modificados = False
        
        for pdf_file in DOCS_DIR.glob("*.pdf"):
            if pdf_file.stat().st_mtime > cache_mtime:
                pdfs_modificados = True
                break
        
        if not pdfs_modificados:
            # Carrega cache existente
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    # PROCESSAMENTO DOS PDFS (executado apenas quando necessário)
    st.info("🔄 Processando documentos pela primeira vez... Isso pode levar alguns segundos.")
    
    try:
        from pypdf import PdfReader
    except ImportError:
        st.error("Biblioteca pypdf não instalada. Execute: pip install pypdf")
        return None
    
    documentos_texto = []
    
    for pdf_path in DOCS_DIR.glob("*.pdf"):
        try:
            reader = PdfReader(pdf_path)
            texto_completo = ""
            
            for page in reader.pages:
                texto_completo += page.extract_text() + "\n"
            
            # Resumo do documento para contexto
            nome_arquivo = pdf_path.stem
            documentos_texto.append({
                "nome": nome_arquivo,
                "texto": texto_completo,
                "tamanho": len(texto_completo),
                "data_processamento": datetime.now().isoformat()
            })
            
        except Exception as e:
            st.warning(f"Erro ao ler {pdf_path.name}: {str(e)}")
    
    # Salva cache
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(documentos_texto, f, ensure_ascii=False, indent=2)
    
    return documentos_texto

# ============================================
# 3. CARREGAMENTO DOS DOCUMENTOS (LEVE)
# ============================================
@st.cache_resource(ttl=3600)  # Cache por 1 hora
def carregar_documentos():
    """Carrega os documentos processados do cache"""
    documentos = processar_pdfs_para_texto()
    if documentos is None:
        return []
    
    # Extrai apenas os textos para o contexto
    textos = []
    for doc in documentos:
        textos.append(f"--- {doc['nome']} ---\n{doc['texto'][:CHUNK_SIZE]}")
    
    return "\n\n".join(textos)

# ============================================
# 4. FUNÇÃO DE CHAMADA DA API GEMINI
# ============================================
def chamar_gemini(pergunta, contexto, usar_web=False):
    """
    Chama a API do Gemini com tratamento de erros robusto
    """
    try:
        from google import genai
        
        # Configuração da API
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            # Fallback para variável de ambiente
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            return "❌ Chave de API não configurada. Verifique as configurações."
        
        client = genai.Client(api_key=api_key)
        
        # Construção do prompt com economia de tokens
        prompt = f"""Você é um assistente de fiscalização ambiental. Responda de forma direta, prática e curta.

Contexto das legislações/relatórios:
{contexto}

Pergunta do fiscal: {pergunta}

Instruções:
- Seja objetivo e vá direto ao ponto
- Use linguagem clara para leitura em campo
- Se não souber, diga que não tem informação
- Máximo de 200 palavras
"""
        
        # Configuração da chamada
        tools = None
        if usar_web:
            tools = [{"google_search": {}}]
        
        # Faz a chamada com timeout
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            tools=tools,
            config={
                "temperature": 0.3,
                "max_output_tokens": 500,
            }
        )
        
        return response.text
        
    except Exception as e:
        # Tratamento de erros específicos
        error_msg = str(e).lower()
        
        if "quota" in error_msg or "resource exhausted" in error_msg:
            return "⚠️ Limite de requisições da API atingido. Tente novamente mais tarde."
        elif "timeout" in error_msg or "connection" in error_msg:
            return "📡 Instabilidade na rede de campo. Tente novamente."
        elif "api_key" in error_msg or "authentication" in error_msg:
            return "🔑 Erro de autenticação. Verifique sua chave API."
        else:
            return f"⚠️ Erro ao processar sua pergunta: {str(e)[:100]}"

# ============================================
# 5. INTERFACE PRINCIPAL
# ============================================
def main():
    # Inicializa estado da sessão
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []
        st.session_state.usar_web = False
    
    # Sidebar minimalista (apenas para info)
    with st.sidebar:
        st.markdown("### 🌿 Configurações")
        st.session_state.usar_web = st.checkbox(
            "🔍 Busca na Web", 
            value=st.session_state.usar_web,
            help="Ativa busca no Google para informações atualizadas"
        )
        
        st.markdown("---")
        st.markdown("**Status do Sistema**")
        st.caption(f"📄 {len(st.session_state.mensagens)} mensagens")
    
    # Carrega documentos (invisível para o usuário)
    try:
        contexto = carregar_documentos()
    except Exception as e:
        contexto = "Erro ao carregar documentos base."
        st.error("⚠️ Erro ao carregar base de documentos")
    
    # Interface principal - estilo chat
    st.title("🌿 NotebookLM Campo")
    st.caption("Assistente de fiscalização ambiental - resposta instantânea")
    
    # Container de chat (estilo WhatsApp)
    chat_container = st.container()
    
    # Exibe histórico de mensagens
    with chat_container:
        for msg in st.session_state.mensagens:
            if msg["role"] == "user":
                st.chat_message("user").markdown(f"**Você:** {msg['content']}")
            else:
                st.chat_message("assistant").markdown(f"**IA:** {msg['content']}")
    
    # Input do usuário
    pergunta = st.chat_input("Digite sua pergunta sobre legislação ambiental...")
    
    if pergunta:
        # Adiciona pergunta ao histórico
        st.session_state.mensagens.append({"role": "user", "content": pergunta})
        
        # Mostra pergunta imediatamente
        with chat_container:
            st.chat_message("user").markdown(f"**Você:** {pergunta}")
        
        # Placeholder para resposta
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("**IA:** *Processando...*")
            
            # Chama a API
            resposta = chamar_gemini(pergunta, contexto, st.session_state.usar_web)
            
            # Atualiza com a resposta
            placeholder.markdown(f"**IA:** {resposta}")
            
            # Salva no histórico
            st.session_state.mensagens.append({"role": "assistant", "content": resposta})
        
        # Força rerun para atualizar a interface
        st.rerun()

# ============================================
# 6. EXECUÇÃO
# ============================================
if __name__ == "__main__":
    main()