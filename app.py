import streamlit as st
from google import genai
from google.genai import types
import pypdf
import json

st.set_page_config(page_title="Meu NotebookLM Avançado", layout="wide")

st.title("📂 Meu NotebookLM - Organizador de Fontes")

# =====================================================================
# SISTEMA DE SEGURANÇA
api_key = st.secrets.get("GEMINI_API_KEY", "")
# =====================================================================

if not api_key:
    st.error("Chave API não configurada nos Secrets do Streamlit.")
    st.stop()

client = genai.Client(api_key=api_key)

# Inicializa estados da memória
if "banco_de_dados" not in st.session_state:
    st.session_state.banco_de_dados = {}
if "historico" not in st.session_state:
    st.session_state.historico = []

# Upload de Múltiplos PDFs
arquivos_carregados = st.file_uploader(
    "Arraste todos os seus PDFs aqui (Leis, Decretos, Relatórios, etc.)", 
    type=["pdf"], 
    accept_multiple_files=True
)

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

# Processar os arquivos carregados
if arquivos_carregados:
    novos_arquivos = [f for f in arquivos_carregados if f.name not in st.session_state.banco_de_dados]
    
    if novos_arquivos:
        with st.spinner("A IA está lendo e organizando seus documentos por assunto..."):
            for arquivo in novos_arquivos:
                leitor = pypdf.PdfReader(arquivo)
                texto_completo = ""
                for pagina in leitor.pages:
                    texto_completo += pagina.extract_text() or ""
                
                # Pede para o Gemini categorizar baseado no começo do texto
                classificacao = categorizar_documento(texto_completo, arquivo.name)
                
                st.session_state.banco_de_dados[arquivo.name] = {
                    "texto": texto_completo,
                    "categoria": classificacao.get("categoria", "Outros"),
                    "subassunto": classificacao.get("subassunto", "Geral")
                }
        st.success("Todos os documentos foram organizados!")

# Exibir a estrutura de pastas organizada na barra lateral (Sidebar)
if st.session_state.banco_de_dados:
    st.sidebar.header("🗂️ Biblioteca Organizada")
    
    # Agrupar por categoria no Python para exibir bonito
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

# Área do Chat e Cruzamento de dados
st.subheader("💬 Central de Inteligência - Pergunte à sua base")

# Junta o texto de todos os PDFs para mandar como contexto pro Gemini
contexto_consolidado = ""
for nome_arq, dados in st.session_state.banco_de_dados.items():
    contexto_consolidado += f"\n--- FONTE: {nome_arq} (Categoria: {dados['categoria']}, Assunto: {dados['subassunto']}) ---\n{dados['texto']}\n"

# Exibe histórico do chat na tela
for q, r in st.session_state.historico:
    with st.chat_message("user"): st.write(q)
    with st.chat_message("assistant"): st.write(r)

if pergunta := st.chat_input("O que você deseja saber cruzando essas fontes?"):
    with st.chat_message("user"):
        st.write(pergunta)
        
    if contexto_consolidado == "":
        st.error("Por favor, faça o upload de pelo menos um PDF primeiro.")
    else:
        with st.chat_message("assistant"):
            resposta_placeholder = st.empty()
            with st.spinner("Analisando todas as legislações e relatórios..."):
                prompt_final = f"""
                Você é um assistente fiscal e ambiental especialista. Baseando-se ESTRITAMENTE nas fontes consolidadas abaixo, responda à pergunta do usuário.
                Sempre cite explicitamente quais arquivos (fontes) continham a informação utilizada para responder.
                
                Fontes:
                {contexto_consolidado}
                
                Pergunta: {pergunta}
                """
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_final
                )
                resposta_placeholder.write(response.text)
                st.session_state.historico.append((pergunta, response.text))