import streamlit as st
from google import genai
from google.genai import types
import pypdf

# Configuração visual da página
st.set_page_config(page_title="Meu NotebookLM", page_icon="📚", layout="wide")
st.title("📚 Meu Próprio NotebookLM")
st.caption("Faça upload de documentos e converse com eles usando o Gemini.")

# =====================================================================
# SUA CHAVE DE API FIXA AQUI
api_key = = st.secrets.get("GEMINI_API_KEY", "")
# =====================================================================

# Inicializa o cliente do Gemini com a sua chave fixa
client = genai.Client(api_key=api_key)

# Cria a memória do chat (para ele lembrar o que você já conversou)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "contexto_documento" not in st.session_state:
    st.session_state.contexto_documento = ""

# Barra lateral para fazer Upload
st.sidebar.header("Fontes de Dados")
uploaded_file = st.sidebar.file_uploader("Escolha um arquivo PDF", type=["pdf"])

# Se você colocar um PDF, o programa lê o texto dele
if uploaded_file is not None and st.session_state.contexto_documento == "":
    with st.spinner("Lendo e processando o documento..."):
        leitor_pdf = pypdf.PdfReader(uploaded_file)
        texto_completo = ""
        for pagina in leitor_pdf.pages:
            texto_completo += pagina.extract_text() + "\n"
        
        st.session_state.contexto_documento = texto_completo
        st.sidebar.success("Documento carregado com sucesso!")

# Botão para limpar o documento e começar de novo
if st.session_state.contexto_documento:
    if st.sidebar.button("Limpar Documento"):
        st.session_state.contexto_documento = ""
        st.session_state.messages = []
        st.rerun()

# Mostra o histórico de mensagens na tela
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Caixa de texto para você fazer perguntas
if prompt := st.chat_input("O que você quer saber sobre o documento?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Gera a resposta usando a IA do Gemini
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        # Criamos a regra: O Gemini DEVE responder usando o seu documento
        if st.session_state.contexto_documento:
            prompt_sistema = (
                "Você é um assistente estilo NotebookLM. Seu objetivo é ajudar o usuário a entender as fontes fornecidas.\n"
                "Responda à pergunta do usuário utilizando estritamente as informações do documento abaixo.\n"
                f"--- INÍCIO DO DOCUMENTO ---\n{st.session_state.contexto_documento}\n--- FIM DO DOCUMENTO ---"
            )
        else:
            prompt_sistema = "Aviso: Nenhum documento foi carregado pelo usuário ainda. Peça para ele carregar um PDF."

        try:
            config = types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                temperature=0.3,
            )
            
            # Chamada corrigida com o modelo atual gemini-2.5-flash
            resposta = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=config
            )
            
            texto_resposta = resposta.text
            message_placeholder.markdown(texto_resposta)
            st.session_state.messages.append({"role": "assistant", "content": texto_resposta})
            
        except Exception as e:
            st.error(f"Erro na API do Gemini: {e}")