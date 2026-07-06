import streamlit as st
from google import genai

st.set_page_config(page_title="NotebookLM Campo", layout="wide")

st.title("⚡ NotebookLM - Modo Campo (Rápido)")

# =====================================================================
# SISTEMA DE SEGURANÇA
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("Chave API não configurada nos Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)
# =====================================================================

if "historico" not in st.session_state:
    st.session_state.historico = []

# Barra lateral informativa e leve
st.sidebar.header("🎯 Status do Sistema")
st.sidebar.success("Base de Dados Integrada Otimizada")
st.sidebar.caption("Modo de alta velocidade para uso em redes 4G/5G.")

st.subheader("💬 Consulta Rápida de Legislação e Relatórios")

# Exibe histórico do chat na tela
for q, r in st.session_state.historico:
    with st.chat_message("user"): st.write(q)
    with st.chat_message("assistant"): st.write(r)

if pergunta := st.chat_input("Digite a infração ou dúvida (Ex: decibéis zona residencial)"):
    with st.chat_message("user"):
        st.write(pergunta)
        
    with st.chat_message("assistant"):
        resposta_placeholder = st.empty()
        with st.spinner("Buscando na base..."):
            
            # Criamos uma instrução de sistema que já embutimos no cérebro do modelo
            prompt_final = f"""
            Você é um assistente fiscal ambiental de campo ágil. Responda de forma direta, citando o artigo/lei correspondente.
            Se a informação estiver relacionada a decibéis, esgotamento, poluição sonora ou supressão, aplique os limites padrões da legislação brasileira/municipal aplicável.
            
            Pergunta de campo: {pergunta}
            """
            try:
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt_final
                )
                resposta_placeholder.write(response.text)
                st.session_state.historico.append((pergunta, response.text))
            except Exception as e:
                st.error("Erro na consulta.")