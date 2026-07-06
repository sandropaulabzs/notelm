import streamlit as st
from google import genai
from google.genai import types
import pypdf
import os

st.set_page_config(page_title="NotebookLM Campo", layout="wide")

st.title("📱 Assistente de Campo - Base Fixa + Web")

# =====================================================================
# CONEXÃO COM A IA
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("Chave API não configurada nos Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)
# =====================================================================

# FUNÇÃO PARA LER OS PDFs DA PASTA UMA ÚNICA VEZ (Cache de Performance)
@st.cache_resource
def carregar_base_permanente():
    texto_completo = ""
    PASTA_DOCS = "documentos"
    if os.path.exists(PASTA_DOCS):
        arquivos = [f for f in os.listdir(PASTA_DOCS) if f.endswith('.pdf')]
        for arq in arquivos:
            try:
                caminho = os.path.join(PASTA_DOCS, arq)
                leitor = pypdf.PdfReader(caminho)
                for pagina in leitor.pages:
                    texto_completo += pagina.extract_text() or ""
            except:
                pass
    # Limita o tamanho do texto para manter o chat instantâneo e leve
    return texto_completo[:150000]

# Carrega os textos para a memória RAM do servidor
contexto_pdfs = carregar_base_permanente()

# Inicializa o histórico de conversa
if "historico" not in st.session_state:
    st.session_state.historico = []

# Barra lateral informativa
st.sidebar.header("🎯 Status do App")
if contexto_pdfs:
    st.sidebar.success("Base de dados 'documentos' carregada na memória!")
else:
    st.sidebar.warning("Nenhum PDF encontrado na pasta 'documentos'.")
st.sidebar.caption("Modo de alta velocidade com consulta à Web ativa.")

st.subheader("💬 Consulta Ágil (PDFs Locais + Google)")

# Exibe o histórico estilo chat
for q, r in st.session_state.historico:
    with st.chat_message("user"): st.write(q)
    with st.chat_message("assistant"): st.write(r)

# Caixa de texto para o Fiscal usar na rua
if pergunta := st.chat_input("Digite sua dúvida ou infração..."):
    with st.chat_message("user"):
        st.write(pergunta)
        
    with st.chat_message("assistant"):
        resposta_placeholder = st.empty()
        
        with st.spinner("Consultando..."):
            # Montamos as instruções de comportamento do chat
            instrucoes = """
            Você é um assistente fiscal ambiental experiente, conversando de forma direta, ágil e fluida.
            Se a resposta para a pergunta do usuário estiver nos documentos locais fornecidos abaixo, priorize-os e cite o arquivo.
            Se não encontrar nos documentos locais ou se o usuário pedir dados atuais, utilize a ferramenta de pesquisa do Google (Google Search) integrada para trazer a legislação correta.
            """
            
            try:
                # Faz a chamada ativando a busca do Google (Google Search Grounding)
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        instrucoes,
                        f"--- DOCUMENTOS LOCAIS DA PASTA ---\n{contexto_pdfs}",
                        f"Pergunta do usuário: {pergunta}"
                    ],
                    config=types.GenerateContentConfig(
                        tools=[{"google_search": {}}] # Ativa o Google no cérebro da IA
                    )
                )
                resposta = response.text
                resposta_placeholder.write(resposta)
                st.session_state.historico.append((pergunta, resposta))
            except Exception as e:
                st.error("Erro ao processar resposta.")
                st.caption(f"Detalhe: {str(e)}")