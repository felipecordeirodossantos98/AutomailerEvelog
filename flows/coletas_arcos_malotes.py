import streamlit as st
import pandas as pd

from services.email_config import configurar_email
from services.email_sender import enviar_emails
from utils.text import remover_acentos
from utils.email_form import render_email_config


def separar_emails(valor):
    """
    Converte o conteúdo da coluna EMAIL em uma lista.

    Aceita e-mails separados por:
    - vírgula
    - ponto e vírgula
    - quebra de linha
    """

    if pd.isna(valor):
        return []

    valor = str(valor).strip()

    if not valor:
        return []

    valor = (
        valor
        .replace(";", ",")
        .replace("\n", ",")
    )

    return [
        email.strip()
        for email in valor.split(",")
        if email.strip()
    ]


def formatar_valor(valor):
    """
    Evita valores como nan e remove .0 de números
    lidos como float pelo pandas.
    """

    if pd.isna(valor):
        return ""

    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))

    return str(valor).strip()


def run(uploaded, email_user, senha):

    if not isinstance(uploaded, list):
        uploaded = [uploaded]

    dfs = []

    for file in uploaded:

        if not file.name.lower().endswith((".xlsx", ".xls", ".csv")):
            continue

        try:
            file.seek(0)
        except Exception:
            continue

        try:
            if file.name.lower().endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

        except Exception as erro:
            st.warning(
                f"Não foi possível processar o arquivo "
                f"{file.name}: {erro}"
            )
            continue

        df = df.dropna(how="all")

        if not df.empty:
            dfs.append(df)

    if not dfs:
        st.error("Nenhum arquivo válido foi processado.")
        return

    df = pd.concat(
        dfs,
        ignore_index=True
    )

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df.columns = [
        remover_acentos(coluna)
        for coluna in df.columns
    ]

    colunas_obrigatorias = [
        "SIGLA",
        "ORDEM",
        "UNIDADE",
        "EMAIL",
    ]

    colunas_faltantes = [
        coluna
        for coluna in colunas_obrigatorias
        if coluna not in df.columns
    ]

    if colunas_faltantes:
        st.error(
            "A planilha não possui todas as colunas necessárias."
        )

        st.write(
            "Colunas não encontradas:",
            ", ".join(colunas_faltantes)
        )

        st.stop()

    # Remove linhas sem ordem.
    df = df[df["ORDEM"].notna()].copy()

    if df.empty:
        st.warning("Nenhuma ordem válida encontrada.")
        return

    # Formatação dos campos utilizados.
    df["ORDEM"] = df["ORDEM"].apply(formatar_valor)
    df["SIGLA"] = df["SIGLA"].apply(formatar_valor)
    df["UNIDADE"] = df["UNIDADE"].apply(formatar_valor)
    df["EMAIL"] = df["EMAIL"].apply(formatar_valor)

    st.divider()

    config = render_email_config(
        show_assunto=False,
        show_corpo=False
    )

    cc_input = config.get("cc_input")

    if st.button("🚀 Enviar e-mails"):

        config = configurar_email(cc_input)

        cc_list = config["cc"] or []

        if isinstance(cc_list, str):
            cc_list = [
                email.strip()
                for email in cc_list.split(",")
                if email.strip()
            ]

        lista_envios = []
        registros_sem_email = []

        for _, pedido in df.iterrows():

            ordem = formatar_valor(
                pedido["ORDEM"]
            )

            sigla = formatar_valor(
                pedido["SIGLA"]
            )

            unidade = formatar_valor(
                pedido["UNIDADE"]
            )

            emails_to = separar_emails(
                pedido["EMAIL"]
            )

            if not emails_to:

                registros_sem_email.append({
                    "SIGLA": sigla,
                    "ORDEM": ordem,
                    "UNIDADE": unidade,
                    "EMAIL": formatar_valor(
                        pedido["EMAIL"]
                    ),
                })

                continue

            assunto = (
                "PRÉ-ALERTA - COLETA MALOTE CLIENTE MCDONALD'S "
                f"OC - {ordem} {sigla}"
            )

            corpo_html = """
                <div style="
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                ">

                    <p style="
                        color: red;
                        font-weight: bold;
                        font-size: 16px;
                    ">
                        URGENTE!
                    </p>

                    <p style="
                        background-color: #2ecc71;
                        color: white;
                        font-weight: bold;
                        font-size: 18px;
                        padding: 4px;
                    ">
                        COLETA DE MALOTE – DOCUMENTOS
                    </p>

                    <p>
                        Prezados, boa tarde!
                    </p>

                    <p style="
                        background-color: #17c9c3;
                        color: white;
                        font-weight: bold;
                        padding: 4px;
                    ">
                        Por gentileza, providenciar coleta com urgência.
                        Coleta alinhada com o restaurante, o mesmo está
                        no aguardo!!!
                    </p>

                    <p style="
                        background-color: #d633ff;
                        color: white;
                        font-weight: bold;
                        padding: 4px;
                    ">
                        C/C EMISSÃO 0153080 - MALOTES
                    </p>

                    <p style="
                        background-color: #f1c40f;
                        font-weight: bold;
                        padding: 3px;
                    ">
                        Essa coleta deve ser feita no mesmo dia
                        (dependendo do horário), ou no dia seguinte.
                    </p>

                    <p>
                        Não realizar a coleta em finais de semanas;
                    </p>

                    <ul>
                        <li>
                            Emita pela tarja e nos informe o nº do CTE
                            para que possamos vincular a ordem e creditar
                            o valor da coleta de

                            <span style="
                                background-color: #2ecc71;
                                font-weight: bold;
                            ">
                                R$13,20
                            </span>.
                        </li>

                        <li>
                            Mencione o lacre no campo pedido.
                        </li>

                        <li>
                            Esse item é de suma importância.
                        </li>
                    </ul>

                    <p style="
                        color: red;
                        font-weight: bold;
                    ">
                        ATENÇÃO!
                    </p>

                    <p style="
                        background-color: #f1c40f;
                        font-weight: bold;
                        padding: 4px;
                    ">
                        CASO O RESTAURANTE NÃO ENVIE O MALOTE,
                        PEGUE A RESSALVA NA ORDEM
                        (Nome legível, data e hora)
                        e nos encaminhe via e-mail para que possamos
                        gerar a improdutiva.
                    </p>

                    <p>
                        Caso tenha alguma ordem de coleta pendente
                        de acerto, favor encaminhar em resposta a
                        este e-mail com CTE reversa / OC para que
                        seja feito o acerto.
                    </p>

                    <p>
                        Obrigado, qualquer dúvida estou à disposição. 😊
                    </p>

                    <br><br>

                    <p>
                        <i>Mensagem automática.</i>
                    </p>

                </div>
            """

            lista_envios.append({
                "unidade": unidade,
                "pedido": ordem,
                "to": emails_to,
                "cc": cc_list,
                "subject": assunto,
                "html": corpo_html,
                "qtd_pedidos": 1,
            })

        if registros_sem_email:

            st.warning(
                f"{len(registros_sem_email)} ordem(ns) estão sem "
                "e-mail e serão ignoradas."
            )

            st.dataframe(
                pd.DataFrame(registros_sem_email),
                use_container_width=True,
                hide_index=True
            )

        if not lista_envios:
            st.warning("Nenhum e-mail foi gerado.")
            st.stop()

        try:
            enviar_emails(
                lista_envios,
                email_user,
                senha
            )

        except ValueError as erro:
            st.error(str(erro))
            st.stop()