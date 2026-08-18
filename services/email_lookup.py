import json


def carregar_emails(caminho):

    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)