import streamlit as st
import pandas as pd
import sys
import os
import streamlit.components.v1 as components

components.html(
    """
    <script>
        window.parent.addEventListener("beforeunload", function (event) {
            event.preventDefault();
            event.returnValue = "";
        });
    </script>
    """,
    height=0,
)

from flows import (
    pre_alertas_unidades,
    coletas_tramontina,
    coletas_arcos_malotes,
    coletas_arcos_equipamentos
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="AutoMailer Evelog",
    page_icon="images/evelog-favicon.svg",
    layout="wide"
)

st.title("Automailer Evelog")

col_form, _ = st.columns([1, 2])

with col_form:
    email_user = st.text_input(
        "E-mail remetente",
        placeholder="atendimento@evelog.com.br",
        key="email_user"
    )

    senha = st.text_input(
        "Senha",
        type="password",
        key="email_smtp"
    )

    uploaded = st.file_uploader(
        "Importar arquivos",
        type=["xlsx", "xls", "csv", "txt"],
        accept_multiple_files=True
    )

if uploaded:

    tipo_fluxo = None

    for file in uploaded:
        nome = file.name.lower()

        if nome.endswith(".txt"):
            tipo_fluxo = "coletas_arcos_equipamentos"

        elif nome.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file, header=None)

            a1 = str(df.iloc[0, 0]).strip()
            a2 = str(df.iloc[1, 0]).strip()

            file.seek(0)

            if a2 == "Ordem":
                tipo_fluxo = "coletas_tramontina"

            elif a2 in ["Codigo", "Código"]:
                tipo_fluxo = "pre_alertas_unidades"

            elif a1 == "SIGLA":
                tipo_fluxo = "coletas_arcos_malotes"

    if tipo_fluxo == "coletas_arcos_equipamentos":
        coletas_arcos_equipamentos.run(uploaded, email_user, senha)

    elif tipo_fluxo == "coletas_tramontina":
        coletas_tramontina.run(uploaded, email_user, senha)

    elif tipo_fluxo == "pre_alertas_unidades":
        pre_alertas_unidades.run(uploaded, email_user, senha)

    elif tipo_fluxo == "coletas_arcos_malotes":
        coletas_arcos_malotes.run(uploaded, email_user, senha)

    else:
        st.warning("Não foi possível identificar o tipo de fluxo")