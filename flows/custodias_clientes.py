import html

import pandas as pd
import streamlit as st

from services.email_lookup import carregar_emails
from services.email_sender import enviar_emails
from utils.text import remover_acentos


EMAILS_CLIENTES_PATH = "bases/emails_clientes.json"

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
    "DESCRICAO",
]

# As chaves são normalizadas sem acentos para tornar a identificação
# independente da forma como a descrição aparece na planilha.
TEMPLATES_CUSTODIA = {
    "DESTINATARIO DESCONHECIDO": (
        "Prezados,\n\n"
        "O pedido está com ocorrência de destinatário desconhecido. "
        "Solicitamos, por gentileza, a confirmação do nome completo do destinatário, "
        "endereço, ponto de referência e telefone para contato ativo, para que possamos "
        "seguir com uma nova tentativa de entrega.\n\n"
        "Ficamos no aguardo das informações."
    ),
    "ENDERECO INSUFICIENTE": (
        "Prezados,\n\n"
        "O pedido está com ocorrência de endereço insuficiente. "
        "Solicitamos, por gentileza, a confirmação do endereço completo, número, "
        "complemento, ponto de referência e telefone para contato ativo, para que possamos "
        "seguir com uma nova tentativa de entrega.\n\n"
        "Ficamos no aguardo das informações."
    ),
    "ENDERECO NAO LOCALIZADO": (
        "Prezados,\n\n"
        "A entrega não foi realizada devido à ocorrência de endereço não localizado. "
        "Solicitamos, por gentileza, a confirmação do endereço completo, ponto de referência "
        "e telefone de contato ativo do destinatário para que possamos prosseguir com uma "
        "nova tentativa de entrega."
    ),
    "NUMERO NAO LOCALIZADO": (
        "Prezados,\n\n"
        "O pedido está com ocorrência de número não localizado. Para que possamos seguir "
        "com uma nova tentativa de entrega, solicitamos, por gentileza, a confirmação do "
        "endereço completo, ponto de referência e telefone para contato ativo.\n\n"
        "Ficamos no aguardo das informações para prosseguirmos com a tratativa."
    ),
    "MUDOU-SE": (
        "Prezados,\n\n"
        "O pedido está com ocorrência de destinatário mudou-se. Solicitamos, por gentileza, "
        "a confirmação do novo endereço completo, CEP, ponto de referência e telefone para "
        "contato ativo, para que possamos verificar a possibilidade de uma nova tentativa de entrega.\n\n"
        "Ficamos no aguardo das informações."
    ),
    "CEP ERRADO": (
        "Prezados,\n\n"
        "A entrega não foi realizada devido à ocorrência de CEP incorreto. Solicitamos, por "
        "gentileza, a confirmação do CEP correto e do endereço completo para que possamos "
        "prosseguir com a entrega."
    ),
    "ENDERECO EM ZONA RURAL": (
        "Prezados,\n\n"
        "O pedido abaixo necessita de um endereço alternativo localizado em zona urbana "
        "para seguirmos com a entrega.\n\n"
        "Por gentileza, nos enviar:\n\n"
        "• Endereço completo, contendo número, bloco, torre ou quadra, número do apartamento "
        "e ponto de referência;\n"
        "• Telefone de contato ativo."
    ),
}


def _normalizar_texto(valor):
    if pd.isna(valor):
        return ""
    return remover_acentos(str(valor).strip().upper())


def _ler_arquivos(uploaded):
    if not isinstance(uploaded, list):
        uploaded = [uploaded]

    dfs = []
    colunas = None

    for i, file in enumerate(uploaded):
        try:
            file.seek(0)
        except Exception:
            continue

        is_csv = file.name.lower().endswith(".csv")

        try:
            if i == 0:
                if is_csv:
                    df = pd.read_csv(file, header=1)
                else:
                    df = pd.read_excel(file, header=1)

                colunas = df.columns
            else:
                if colunas is None:
                    continue

                if is_csv:
                    df = pd.read_csv(
                        file,
                        skiprows=2,
                        header=None,
                        names=colunas,
                    )
                else:
                    df = pd.read_excel(
                        file,
                        skiprows=2,
                        header=None,
                        names=colunas,
                    )

            df = df.dropna(how="all")
            dfs.append(df)

        except Exception as erro:
            st.error(f"Erro ao processar {file.name}: {erro}")
            return None

    if not dfs:
        return None

    df = pd.concat(dfs, ignore_index=True)
    df.columns = df.columns.astype(str).str.strip().str.upper()
    df.columns = [remover_acentos(col) for col in df.columns]

    return df


def _identificar_cliente(df, emails_clientes):
    if "CLIENTE" not in df.columns:
        return None

    valores_cliente = df["CLIENTE"].fillna("").astype(str)

    # A planilha pode trazer várias grafias do mesmo cliente. O JSON define
    # o texto-chave que identifica o cliente em qualquer célula da coluna.
    for cliente, config in emails_clientes.items():
        identificador = config.get("identificador", cliente)
        identificador_norm = _normalizar_texto(identificador)

        if not identificador_norm:
            continue

        encontrou = valores_cliente.map(
            lambda valor: identificador_norm in _normalizar_texto(valor)
        ).any()

        if encontrou:
            return cliente, config

    return None


def _obter_emails(config):
    emails = config.get("emails", [])

    if isinstance(emails, str):
        emails = [e.strip() for e in emails.split(",") if e.strip()]
    else:
        emails = [str(e).strip() for e in emails if str(e).strip()]

    return emails


def _formatar_html(texto):
    return html.escape(texto).replace("\n", "<br>")


def run(uploaded, email_user, senha):
    try:
        emails_clientes = carregar_emails(EMAILS_CLIENTES_PATH)
    except Exception as erro:
        st.error(f"Não foi possível carregar {EMAILS_CLIENTES_PATH}: {erro}")
        return

    df = _ler_arquivos(uploaded)

    if df is None:
        st.error("Nenhum arquivo válido foi processado")
        return

    colunas_obrigatorias = {"STATUS", "DESCRICAO", "CLIENTE"}
    faltantes = sorted(colunas_obrigatorias - set(df.columns))

    if faltantes:
        st.error(
            "A planilha não possui as colunas obrigatórias: "
            + ", ".join(faltantes)
        )
        return

    identificacao = _identificar_cliente(df, emails_clientes)

    if not identificacao:
        st.error(
            "Cliente não identificado. Verifique a coluna 'Cliente' e o cadastro "
            "em bases/emails_clientes.json."
        )
        return

    cliente, config_cliente = identificacao
    emails_to = _obter_emails(config_cliente)

    st.success(f"Cliente identificado: **{cliente}**")

    df["STATUS"] = df["STATUS"].fillna("").astype(str).str.strip().str.upper()
    df["DESCRICAO_NORMALIZADA"] = df["DESCRICAO"].map(_normalizar_texto)

    # Este fluxo não possui seleção de status: ele trabalha exclusivamente
    # com pedidos em CUSTODIA.
    df_custodia = df[df["STATUS"] == "CUSTODIA"].copy()

    if df_custodia.empty:
        st.warning("Nenhum pedido com status CUSTODIA foi encontrado na planilha.")
        return

    descricoes_encontradas = sorted(
        df_custodia["DESCRICAO_NORMALIZADA"].dropna().unique()
    )

    descricoes_validas = [
        descricao
        for descricao in descricoes_encontradas
        if descricao in TEMPLATES_CUSTODIA
    ]

    descricoes_ignoradas = [
        descricao
        for descricao in descricoes_encontradas
        if descricao and descricao not in TEMPLATES_CUSTODIA
    ]

    df_custodia = df_custodia[
        df_custodia["DESCRICAO_NORMALIZADA"].isin(TEMPLATES_CUSTODIA)
    ].copy()

    if df_custodia.empty:
        st.warning("Nenhum pedido de CUSTODIA possui uma descrição cadastrada para envio.")
        return

    st.divider()
    st.subheader("Configuração do e-mail")

    cc_input = st.text_input(
        "CC (separados por vírgula)",
        placeholder="email1@evelog.com.br, email2@evelog.com.br",
        key="custodias_clientes_cc_input",
    )

    if st.button("🚀 Enviar e-mails", key="custodias_clientes_enviar"):
        cc_list = [e.strip() for e in cc_input.split(",") if e.strip()]

        if not emails_to:
            st.error(f"Nenhum e-mail cadastrado para o cliente {cliente}.")
            st.stop()

        lista_envios = []

        for _, pedido in df_custodia.iterrows():
            descricao_normalizada = pedido["DESCRICAO_NORMALIZADA"]

            # Usa a descrição da planilha para o assunto, preservando a grafia
            # apresentada pelo usuário quando houver acentos.
            descricao_original = str(pedido["DESCRICAO"]).strip()

            texto_base = TEMPLATES_CUSTODIA[descricao_normalizada]

            # Mantém somente as colunas configuradas para o e-mail.
            colunas_disponiveis = [
                coluna for coluna in COLUNAS_EMAIL
                if coluna in pedido.index
            ]

            # Transforma a linha do pedido em DataFrame para gerar a tabela HTML.
            pedido_email = pedido[colunas_disponiveis].to_frame().T

            tabela_html = pedido_email.to_html(
                index=False,
                border=1
            )

            corpo_html = f"""
                <p>{_formatar_html(texto_base)}</p>

                <br>

                {tabela_html}

                <br><br>

                <p><i>Mensagem automática.</i></p>
            """

            lista_envios.append({
                "unidade": (
                    f"{cliente} - "
                    f"Pedido {pedido.get('PEDIDO', '')} - "
                    f"{descricao_original}"
                ),
                "to": emails_to,
                "cc": cc_list,
                "subject": (
                    f'SOLICITAÇÃO DE CONFIRMAÇÃO DE ENDEREÇO "{descricao_original}"'
                ),
                "html": corpo_html,
                "qtd_pedidos": 1,
                "df": pedido_email,
            })

        if not lista_envios:
            st.warning("Nenhum e-mail foi gerado.")
            st.stop()

        enviar_emails(lista_envios, email_user, senha)
