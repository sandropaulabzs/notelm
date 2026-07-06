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
CHUNK_SIZE = 3000  # Caracteres por chunk para processamento (reduzido para economia)
MAX_CONTEXT_TOKENS = 4000  # Limite de tokens para enviar ao Gemini

# ============================================
# 2. FUNÇÃO DE PRÉ-PROCESSAMENTO (EXECUTA UMA VEZ)
# ============================================
def processar_pdfs_para_texto():
    """
    Lê todos os PDFs da pasta /documentos e gera um JSON compacto.
    Só executa se o arquivo cache não existir ou se houver mudanças.
    """
    cache_file = CACHE_DIR / "documentos_processados.json"
    
    # Verifica se já existe cache e está atualizado
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Verifica se algum PDF foi modificado
            pdfs_modificados = False
            for pdf_file in DOCS_DIR.glob("*.pdf"):
                if pdf_file.stat().st_mtime > cache_data.get("cache_timestamp", 0):
                    pdfs_modificados = True
                    break
            
            if not pdfs_modificados:
                return cache_data.get("documentos", [])
        except:
            pass  # Se der erro, reprocessa
    
    # PROCESSAMENTO DOS PDFS (executado apenas quando necessário)
    st.toast("🔄 Processando documentos base...", icon="📄")
    
    try:
        from pypdf import PdfReader
    except ImportError:
        st.error("Biblioteca pypdf não instalada. Execute: pip install pypdf")
        return []
    
    documentos_texto = []
    
    for pdf_path in DOCS_DIR.glob("*.pdf"):
        try:
            reader = PdfReader(pdf_path)
            texto_completo = ""
            
            # Extrai apenas o texto principal (ignora cabeçalhos/rodapés)
            for page in reader.pages:
                texto_pagina = page.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina + " "
            
            # Limpeza básica do texto
            texto_completo = " ".join(texto_completo.split())  # Remove espaços extras
            
            # Resumo do documento para contexto
            nome_arquivo = pdf_path.stem
            documentos_texto.append({
                "nome": nome_arquivo,
                "texto": texto_completo[:CHUNK_SIZE],  # Limita tamanho
                "tamanho": len(texto_completo),
                "hash": hashlib.md5(texto_completo.encode()).hexdigest()[:8]
            })
            
        except Exception as e:
            st.warning(f"⚠️ Erro ao ler {pdf_path.name}: {str(e)[:50]}")
    
    # Salva cache com timestamp
    cache_data = {
        "documentos": documentos_texto,
        "cache_timestamp": time.time(),
        "total_documentos": len(documentos_texto)
    }
    
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    return documentos_texto

# ============================================
# 3. CARREGAMENTO DOS DOCUMENTOS (LEVE E RÁPIDO)
# ============================================
@st.cache_resource(ttl=3600)  # Cache por 1 hora no Streamlit Cloud
def carregar_documentos():
    """
    Carrega os documentos processados do cache.
    Retorna uma string de contexto otimizada para tokens.
    """
    documentos = processar_pdfs_para_texto()
    
    if not documentos:
        return "Base de documentos não encontrada."
    
    # Constrói contexto otimizado (apenas os trechos mais relevantes)
    contextos = []
    total_tokens_estimados = 0
    
    for doc in documentos:
        # Pega apenas o início de cada documento (mais relevante)
        texto_doc = doc['texto'][:2000]  # Reduzido para economia
        contexto_doc = f"📄 {doc['nome']}: {texto_doc}"
        contextos.append(contexto_doc)
        total_tokens_estimados += len(contexto_doc) // 3  # Estimativa grosseira
        
        # Se atingir o limite de tokens, para
        if total_tokens_estimados > MAX_CONTEXT_TOKENS:
            break
    
    return "\n\n".join(contextos)

# ============================================
# 4. FUNÇÃO DE BUSCA NO CONTEXTO LOCAL (SEM API)
# ============================================
def buscar_local(pergunta, contexto):
    """
    Busca por palavras-chave no contexto local sem usar a API.
    Útil quando a cota está esgotada.
    """
    palavras = pergunta.lower().split()
    resultados = []
    
    # Procura por documentos que contenham as palavras-chave
    for linha in contexto.split('\n'):
        linha_lower = linha.lower()
        if any(palavra in linha_lower for palavra in palavras):
            if linha.strip():
                resultados.append(linha.strip())
    
    if resultados:
        return "📋 **Encontrado nos documentos:**\n\n" + "\n".join(resultados[:3])
    return "🔍 Não encontrei informações específicas nos documentos. Tente reformular sua pergunta."

# ============================================
# 5. FUNÇÃO DE CHAMADA DA API GEMINI
# ============================================
def chamar_gemini(pergunta, contexto):
    """
    Chama a API do Gemini com tratamento de erros robusto.
    """
    try:
        # Importa o SDK mais recente
        from google import genai
        
        # Configuração da API
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            return "🔑 Chave de API não configurada. Verifique as configurações."
        
        client = genai.Client(api_key=api_key)
        
        # Prompt otimizado para economia de tokens
        prompt = f"""Você é um fiscal ambiental experiente. Responda de forma direta e prática.

Documentos disponíveis:
{contexto}

Pergunta: {pergunta}

Regras:
- Máximo 100 palavras
- Se for multa, cite valor
- Se for artigo, cite número
- Se não souber, diga "Não encontrei essa informação nos documentos"
- Seja objetivo e prático para leitura em campo
"""
        
        # Chamada otimizada
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "temperature": 0.2,  # Mais baixo para respostas precisas
                "max_output_tokens": 300,  # Limita resposta
            }
        )
        
        return response.text
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Tratamento granular de erros
        if "quota" in error_msg or "resource exhausted" in error_msg:
            # Tenta busca local como fallback
            resultado_local = buscar_local(pergunta, contexto)
            if "Encontrado" in resultado_local:
                return resultado_local
            return "⚠️ **Limite de consultas diárias atingido.** Tente novamente amanhã ou use a busca local nos documentos."
        
        elif "timeout" in error_msg or "connection" in error_msg:
            return "📡 **Conexão de campo instável.** Tente novamente em instantes."
        
        elif "api_key" in error_msg or "authentication" in error_msg:
            return "🔑 **Erro de autenticação.** Verifique sua chave API no Streamlit Cloud."
        
        else:
            # Log do erro técnico (apenas para debug)
            st.error(f"Erro técnico: {str(e)[:100]}")
            return "⚠️ **Erro ao processar sua pergunta.** Tente novamente."

# ============================================
# 6. INTERFACE PRINCIPAL
# ============================================
def main():
    # Inicializa estado da sessão
    if "historico" not in st.session_state:
        st.session_state.historico = []
        st.session_state.total_requisicoes = 0
        st.session_state.ultima_resposta = None
    
    # Sidebar compacta
    with st.sidebar:
        st.markdown("### 🌿 NotebookLM Campo")
        st.caption(f"📊 {st.session_state.total_requisicoes} consultas hoje")
        
        # Botão para limpar histórico
        if st.button("🗑️ Limpar Conversa", use_container_width=True):
            st.session_state.historico = []
            st.rerun()
        
        st.markdown("---")
        st.caption("💡 Dica: Use perguntas diretas como 'Qual a multa para...'")
        st.caption("📱 App otimizado para conexões 4G/5G")
    
    # Título principal
    st.title("🌿 NotebookLM Campo")
    st.caption("Assistente de fiscalização ambiental - Respostas rápidas para campo")
    
    # Container do chat
    chat_container = st.container()
    
    # Exibe histórico
    with chat_container:
        if not st.session_state.historico:
            st.info("💬 Pergunte sobre legislação ambiental, multas ou procedimentos de fiscalização.")
        
        for msg in st.session_state.historico:
            if msg["role"] == "user":
                st.chat_message("user").markdown(f"**Você:** {msg['content']}")
            else:
                st.chat_message("assistant").markdown(msg['content'])
    
    # Input do usuário
    pergunta = st.chat_input("Digite sua pergunta sobre fiscalização ambiental...")
    
    if pergunta:
        # Adiciona pergunta ao histórico
        st.session_state.historico.append({"role": "user", "content": pergunta})
        st.session_state.total_requisicoes += 1
        
        # Mostra pergunta
        with chat_container:
            st.chat_message("user").markdown(f"**Você:** {pergunta}")
        
        # Carrega contexto (sempre do cache)
        with st.spinner(""):
            contexto = carregar_documentos()
        
        # Placeholder para resposta
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Processando consulta...*")
            
            # Chama API
            resposta = chamar_gemini(pergunta, contexto)
            
            # Atualiza com resposta
            placeholder.markdown(resposta)
            
            # Salva no histórico
            st.session_state.historico.append({"role": "assistant", "content": resposta})
            st.session_state.ultima_resposta = resposta
        
        # Força atualização
        st.rerun()

# ============================================
# 7. EXECUÇÃO
# ============================================
if __name__ == "__main__":
    main()