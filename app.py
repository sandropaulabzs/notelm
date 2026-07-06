import streamlit as st
from google import genai
from google.genai import types
import pypdf
import json
import os

st.set_page_config(page_title="Meu NotebookLM Avançado", layout="wide")

st.title("📂 Meu NotebookLM - Base de Dados Fixa")

# =====================================================================
# SISTEMA DE SEGURANÇA
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("Chave API não configurada nos Secrets do Streamlit.")
    st.stop()

client = genai.Client(api_key=api_key)
# =====================================================================

# Inicializa estados da memória se não existirem
if "banco_de_dados" not in st.session_state:
    st.session_state.banco_de_dados = {}
if "historico" not in st.session_state:
    st.session_state.historico = []

# Função para a IA categorizar o documento
def categorizar_documento(texto_inicial, nome_arquivo):
    prompt = f"""
    Analise o seguinte trecho inicial de um documento e classifique-o estritamente em uma Categoria Principal e um Subassunto.
    Nome do arquivo: {nome_arquivo}
    Trecho: {texto_inicial[:1500]}
    
    Retorne APENAS um JSON no formato abaixo, sem formatação markdown (sem ```json):
    {{
        "categoria": "Legislação Municipal ou Legislação Federal ou Relatório Técnico ou Outros",
        "subassunto": "Ex: Esgotamento Sanitário, Supressão de Vegetação, Poluição Sonora, Licenciamento, Geral"
    }}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return {"categoria": "Outros", "subassunto": "Geral"}

# --- CARREGAMENTO DA BASE DE DADOS FIXA (Pasta 'documentos') ---
PASTA_DOCS = "documentos"
if os.path.exists(PASTA_DOCS):
    arquivos_locais = [f for f in os.listdir(PASTA_DOCS) if f.endswith('.pdf')]
    
    # Filtra apenas os que ainda não foram processados nesta sessão
    novos_locais = [f for f in arquivos_locais if f not in st.session_state.banco_de_dados]
    
    if novos_locais:
        with st.spinner("Carregando sua base de dados permanente do GitHub..."):
            for nome_arq in novos_locais:
                caminho_completo = os.path.join(PASTA_DOCS, nome_arq)
                try:
                    leitor = pypdf.PdfReader(caminho_completo)
                    texto_completo = ""
                    for pagina in leitor.pages:
                        texto_completo += pagina.extract_text() or ""
                    
                    classificacao = categorizar_documento(texto_completo, nome_arq)
                    st.session_state.banco_de_dados[nome_arq] = {
                        "texto": texto_completo,
                        "categoria": classification.get("categoria", "Outros"),
                        "subassunto": classification.get("subassunto", "Geral")
                    }
                except Exception as e:
                    pass

# --- CARREGAMENTO DE ARQUIVOS TEMPORÁRIOS (Upload na hora) ---
arquivos_carregados = st.file_uploader(
    "Adicionar novos PDFs temporários para esta conversa", 
    type=["pdf"], 
    accept_multiple_files=True
)

if arquivos_carregados:
    novos_uploads = [f for f in arquivos_carregados if f.name not in st.session_state.banco_de_dados]
    if novos_uploads:
        with st.spinner("Processando novos arquivos..."):
            for arquivo in novos_uploads:
                try:
                    leitor = pypdf.PdfReader(arquivo)
                    texto_completo = ""
                    for pagina in leitor.pages:
                        texto_completo += pagina.extract_text() or ""
                    
                    classificacao = categorizar_documento(texto_completo, arquivo.name)
                    st.session_state.banco_de_dados[arquivo.name] = {
                        "texto": texto_completo,
                        "categoria": classificacao.get("categoria", "Outros"),
                        "subassunto": classificacao.get("subassunto", "Geral")
                    }
                except:
                    pass

# --- EXIBIR BIBLIOTECA ORGANIZADA ---
if st.session_state.banco_de_dados:
    st.sidebar.header("🗂️ Biblioteca de Fontes")
    categorias = {}
    for nome, dados in st.session_state.banco_de_dados.items():
        cat = dados["categoria"]
        sub = dados["subassunto"]
        if cat not in categorias: categorias[cat] = {}
        if sub not in categorias[cat]: categorias[cat][sub] = []
        categorias[cat][sub].append(nome)
        
    for cat, subassuntos in categorias.items():
        with st.sidebar.expander(f"📁 {cat}", expanded=True):
            for sub, lista_arquivos in subassuntos.items():
                st.markdown(f"**🔹 {sub}**")
                for arq in lista_arquivos:
                    st.caption(f"📄 {arq}")

# --- CENTRAL DE INTELIGÊNCIA (CHAT) ---
st.subheader("💬 Central de Inteligência - Pergunte à sua base")

contexto_consolidado = ""
for nome_arq, dados in st.session_state.banco_de_dados.items():
    texto_limitado = dados['texto'][:40000]
    contexto_consolidado += f"\n--- FONTE: {nome_arq} (Categoria: {dados['categoria']}, Assunto: {dados['subassunto']}) ---\n{texto_limitado}\n"

for q, r in st.session_state.historico:
    with st.chat_message("user"): st.write(q)
    with st.chat_message("assistant"): st.write(r)

if pergunta := st.chat_input("O que você deseja saber cruzando essas fontes?"):
    with st.chat_message("user"):
        st.write(pergunta)
        
    if contexto_consolidado == "":
        st.error("A base de dados está vazia. Adicione PDFs na pasta 'documentos' ou faça o upload.")
    else:
        with st.chat_message("assistant"):
            resposta_placeholder = st.empty()
            with st.spinner("Analisando base de dados permanente..."):
                prompt_final = f"""
                Você é um assistente fiscal e ambiental especialista. Baseando-se ESTRITAMENTE nas fontes consolidadas abaixo, responda à pergunta do usuário.
                Sempre cite explicitamente quais arquivos (fontes) continham a informação utilizada para responder.
                
                Fontes:
                {contexto_consolidado}
                
                Pergunta: {pergunta}
                """
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_final
                    )
                    resposta_placeholder.write(response.text)
                    st.session_state.historico.append((pergunta, response.text))
                except Exception as e:
                    st.error("Erro ao processar resposta com a IA.")
                    st.caption(f"Detalhe: {str(e)}")