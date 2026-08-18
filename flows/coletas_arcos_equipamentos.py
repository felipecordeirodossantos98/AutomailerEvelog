import streamlit as st
import pandas as pd

from services.email_lookup import carregar_emails
from services.email_config import configurar_email
from services.email_sender import enviar_emails
from utils.text import remover_acentos
from utils.email_form import render_email_config
from services.txt_parser import parse_txt
from io import BytesIO

def run(uploaded, email_user, senha):
    emails_unidades = carregar_emails(
        "bases/emails_restaurantes.json"
    )

    dfs = [parse_txt(arq) for arq in uploaded]
    df = pd.concat(dfs, ignore_index=True)

    df.columns = [
        remover_acentos(col)
        for col in df.columns
    ]

    df["DATA"] = pd.to_datetime(df["DATA"], dayfirst=True, errors="coerce")
    df["QTDE"] = pd.to_numeric(df["QTDE"], errors="coerce")

    df["PRECO_UNIT_RS"] = (
        df["PRECO_UNIT_RS"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    df["PRECO_UNIT_RS"] = pd.to_numeric(
        df["PRECO_UNIT_RS"], errors="coerce"
    )

    def to_excel(df):
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Dados")

        output.seek(0)
        return output

    excel_file = to_excel(df)

    st.download_button(
        label="Exportar planilha",
        data=excel_file,
        file_name="dados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()

    config = render_email_config(show_assunto=False, show_corpo=False)

    cc_input = config.get("cc_input")

    if st.button("🚀 Enviar e-mails"):

        config = configurar_email(cc_input)

        lista_envios = []

        for _, pedido in df.iterrows():

            unidade = str(pedido["RESTAURANTE"]).strip().upper()

            emails_to = emails_unidades.get(unidade, [])

            if not emails_to:
                st.warning(f"Sem e-mail para: {unidade}")
                continue

            if isinstance(emails_to, str):
                emails_to = [e.strip() for e in emails_to.split(",") if e.strip()]

            cc_list = list(config["cc"] or [])

            corpo_html = f"""
                <p>Bom dia!</p>
                <br>
                <p><strong>{unidade}</strong>,</p>
                <p>
                Foi transmitido a nós o pedido: 
                <strong>{pedido['PEDIDO']}</strong> referentes a 
                <strong>{pedido['DESCRICAO']}</strong>, 
                solicitado via Central de Pedidos por 
                <strong>{pedido['RESPONSAVEL']}</strong>.
                </p>
                <p>
                Por gentileza, nos encaminhar a NOTA FISCAL 
                para agendamento da coleta.
                </p>
                <br>
                <p>Obrigado, no aguardo de um retorno.</p>
                <br><br>
                <p><i>Mensagem automática.</i></p>
            """

            lista_envios.append({
                "unidade": unidade,
                "pedido": pedido["PEDIDO"],
                "to": emails_to,
                "cc": cc_list,
                "subject": f'SOLICITAÇÃO DE NF {str(pedido["RESTAURANTE"]).strip()} {str(pedido["PEDIDO"]).strip()}',
                "html": corpo_html,
                "qtd_pedidos": 1
            })

        if not lista_envios:
            st.warning("Nenhum e-mail foi gerado")
            st.stop()

        try:
            enviar_emails(lista_envios, email_user, senha)

        except ValueError as e:
            st.error(str(e))
            st.stop()