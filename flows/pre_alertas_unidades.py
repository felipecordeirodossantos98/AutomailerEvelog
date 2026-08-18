import streamlit as st
import pandas as pd

from services.email_lookup import carregar_emails
from services.email_config import configurar_email, validar_config_email
from services.email_sender import enviar_emails
from utils.text import remover_acentos
from utils.email_form import render_email_config


def run(uploaded, email_user, senha):
    emails_unidades = carregar_emails(
        "bases/emails_unidades.json"
    )

    if not isinstance(uploaded, list):
        uploaded = [uploaded]

    dfs = []

    for i, file in enumerate(uploaded):
        try:
            file.seek(0)
        except:
            continue

        is_csv = file.name.lower().endswith(".csv")

        if i == 0:
            if is_csv:
                df = pd.read_csv(file, header=1)
            else:
                df = pd.read_excel(file, header=1)

            colunas = df.columns

        else:
            if is_csv:
                df = pd.read_csv(
                    file,
                    skiprows=2,
                    header=None,
                    names=colunas
                )
            else:
                df = pd.read_excel(
                    file,
                    skiprows=2,
                    header=None,
                    names=colunas
                )

        df = df.dropna(how="all")
        dfs.append(df)

    if not dfs:
        st.error("Nenhum arquivo válido foi processado")
        return

    df = pd.concat(dfs, ignore_index=True)

    df.columns = df.columns.astype(str).str.strip().str.upper()

    df.columns = [
        remover_acentos(col)
        for col in df.columns
    ]

    st.divider()

    st.subheader("Filtro de status")

    COL_STATUS = "STATUS"
    COL_DESCRICAO_STATUS = "DESCRICAO"

    df[COL_STATUS] = df[COL_STATUS].astype(str).str.strip().str.upper()
    df[COL_DESCRICAO_STATUS] = df[COL_DESCRICAO_STATUS].astype(str).str.strip()

    status_disponiveis = sorted(
        df[COL_STATUS]
        .dropna()
        .unique()
    )

    col1, _ = st.columns([1, 2])

    with col1:
        status_selecionado = st.selectbox(
            "Selecione o status para envio",
            status_disponiveis
        )

    df_filtrado = df[df[COL_STATUS] == status_selecionado]

    if status_selecionado == "CUSTODIA":

        descricoes = sorted(
            df_filtrado[COL_DESCRICAO_STATUS]
            .dropna()
            .unique()
        )

        col2, _ = st.columns([1, 2])

        with col2:
            descricao_selecionada = st.selectbox(
                "Selecione a descrição da custódia",
                descricoes
            )

        df_filtrado = df_filtrado[
            df_filtrado[COL_DESCRICAO_STATUS] == descricao_selecionada
        ]

    st.divider()

    config = render_email_config()

    cc_input = config.get("cc_input")
    assunto = config.get("assunto")
    texto_base = config.get("texto_base")

    if st.button("🚀 Enviar e-mails"):

        config = configurar_email(cc_input, assunto, texto_base)

        erros = validar_config_email(config, True, True)

        if erros:
            for erro in erros:
                st.warning(erro)
            st.stop()

        lista_envios = []

        grupos = df_filtrado.groupby("DESTINO")

        COLUNAS_EMAIL = [
            "CODIGO",
            "NOTA FISCAL",
            "PEDIDO",
            "CLIENTE",
            "DESTINO",
            "CIDADE",
            "UF",
            "STATUS",
            "DT EVENTO",
            "PREVISAO",
            "DESCRICAO"
        ]

        for unidade, pedidos_unidade in grupos:

            emails_to = emails_unidades.get(unidade, [])

            if isinstance(emails_to, str):
                emails_to = [e.strip() for e in emails_to.split(",") if e.strip()]

            pedidos_unidade = pedidos_unidade[COLUNAS_EMAIL]

            tabela_html = pedidos_unidade.to_html(index=False)

            cc_list = config["cc"] or []

            if isinstance(cc_list, str):
                cc_list = [e.strip() for e in cc_list.split(",") if e.strip()]

            corpo_html = f"""
                <p>{config['corpo']}</p>
                <br>
                {tabela_html}
                <br><br>
                <p><strong><u>SE NÃO ESTIVER NA SUA UNIDADE, FAVOR DESCONSIDERAR.</u></strong></p>
                <p><i>Mensagem automática.</i></p>
                """

            lista_envios.append({
                "unidade": unidade,
                "to": emails_to,
                "cc": cc_list,
                "subject": f"{config['assunto']} – Unidade {unidade}",
                "html": corpo_html,
                "qtd_pedidos": len(pedidos_unidade),
                "df": pedidos_unidade
            })
        
        if not lista_envios:
            st.warning("Nenhum e-mail foi gerado")
            st.stop()

        try:
            enviar_emails(lista_envios, email_user, senha)

        except ValueError as e:
            st.error(str(e))
            st.stop()
