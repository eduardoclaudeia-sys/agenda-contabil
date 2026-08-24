import re
import pymupdf


# ============================================================
# LEITOR DE DOCUMENTOS CNPJ
# ============================================================

class LeitorCNPJ:
    """
    Responsável por ler um PDF de CNPJ e extrair
    os principais dados cadastrais da empresa.
    """

    # ========================================================
    # CONSTRUTOR
    # ========================================================

    def __init__(self):

        self.texto = ""


    # ========================================================
    # LER PDF
    # ========================================================

    def ler_pdf(self, caminho_pdf):

        self.texto = ""

        documento = pymupdf.open(
            caminho_pdf
        )

        try:

            for pagina in documento:

                self.texto += (
                    pagina.get_text()
                    + "\n"
                )

        finally:

            documento.close()

        return self.texto


    # ========================================================
    # NORMALIZAR TEXTO
    # ========================================================

    def normalizar_texto(self, texto):

        if not texto:

            return ""

        texto = texto.replace(
            "\r",
            "\n"
        )

        linhas = []

        for linha in texto.splitlines():

            linha = linha.strip()

            if linha:

                linha = re.sub(
                    r"\s+",
                    " ",
                    linha
                )

                linhas.append(
                    linha
                )

        return "\n".join(
            linhas
        )


    # ========================================================
    # LOCALIZAR VALOR APÓS UM CAMPO
    # ========================================================

    def valor_apos_campo(
        self,
        linhas,
        campo
    ):

        campo_normalizado = campo.upper()

        for indice, linha in enumerate(linhas):

            if linha.upper().strip() == campo_normalizado:

                if indice + 1 < len(linhas):

                    return linhas[
                        indice + 1
                    ].strip()

        return ""


    # ========================================================
    # EXTRAIR CNPJ
    # ========================================================

    def extrair_cnpj(self, texto):

        padroes = [

            r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",

            r"\b\d{14}\b"

        ]

        for padrao in padroes:

            encontrados = re.findall(
                padrao,
                texto
            )

            for candidato in encontrados:

                numeros = self.somente_numeros(
                    candidato
                )

                if self.validar_cnpj(
                    numeros
                ):

                    return numeros

        return ""


    # ========================================================
    # EXTRAIR RAZÃO SOCIAL
    # ========================================================

    def extrair_razao_social(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "NOME EMPRESARIAL"
        )


    # ========================================================
    # EXTRAIR NOME FANTASIA
    # ========================================================

    def extrair_nome_fantasia(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "TÍTULO DO ESTABELECIMENTO (NOME DE FANTASIA)"
        )


    # ========================================================
    # EXTRAIR DATA DE ABERTURA
    # ========================================================

    def extrair_data_abertura(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "DATA DE ABERTURA"
        )


    # ========================================================
    # EXTRAIR PORTE
    # ========================================================

    def extrair_porte(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "PORTE"
        )


    # ========================================================
    # EXTRAIR CNAE PRINCIPAL
    # ========================================================

    def _parse_linha_cnae(self, linha):
        linha = str(linha or '').strip()
        m = re.match(r'^(\d{2}\.\d{2}-\d-\d{2})\s*-\s*(.+)$', linha)
        if not m:
            m = re.match(r'^(\d{7})\s*-?\s*(.*)$', linha)
            if not m:
                return None
            n = m.group(1)
            codigo = f'{n[:2]}.{n[2:4]}-{n[4]}-{n[5:]}'
            descricao = m.group(2).strip()
            return {'codigo': codigo, 'descricao': descricao}
        return {'codigo': m.group(1), 'descricao': m.group(2).strip()}

    def _bloco_apos_campo(self, linhas, campo, limite_campos):
        campo = campo.upper().strip()
        inicio = None
        for i, linha in enumerate(linhas):
            if linha.upper().strip() == campo:
                inicio = i + 1
                break
        if inicio is None:
            return []
        saida = []
        limites = {x.upper().strip() for x in limite_campos}
        for linha in linhas[inicio:]:
            if linha.upper().strip() in limites:
                break
            saida.append(linha)
        return saida

    def extrair_cnae_principal_detalhe(self, linhas):
        campo = (
            "CÓDIGO E DESCRIÇÃO DA "
            "ATIVIDADE ECONÔMICA PRINCIPAL"
        )
        valor = self.valor_apos_campo(linhas, campo)
        return self._parse_linha_cnae(valor) or {'codigo': valor, 'descricao': ''}

    def extrair_cnae_principal(self, linhas):
        return self.extrair_cnae_principal_detalhe(linhas).get('codigo', '')


    # ========================================================
    # EXTRAIR CNAES SECUNDÁRIOS
    # ========================================================

    def extrair_cnaes_secundarios_detalhes(self, linhas):
        campo = (
            "CÓDIGO E DESCRIÇÃO DAS "
            "ATIVIDADES ECONÔMICAS SECUNDÁRIAS"
        )
        bloco = self._bloco_apos_campo(
            linhas, campo,
            [
                "CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA",
                "LOGRADOURO", "CEP", "ENDEREÇO ELETRÔNICO"
            ]
        )
        itens = []
        for linha in bloco:
            item = self._parse_linha_cnae(linha)
            if item:
                itens.append(item)
        return itens

    def extrair_cnaes_secundarios(self, linhas):
        return [x['codigo'] for x in self.extrair_cnaes_secundarios_detalhes(linhas)]


    # ========================================================
    # EXTRAIR NATUREZA JURÍDICA
    # ========================================================

    def extrair_natureza_juridica(
        self,
        linhas
    ):

        campo = (
            "CÓDIGO E DESCRIÇÃO DA "
            "NATUREZA JURÍDICA"
        )

        return self.valor_apos_campo(
            linhas,
            campo
        )


    # ========================================================
    # EXTRAIR LOGRADOURO
    # ========================================================

    def extrair_logradouro(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "LOGRADOURO"
        )


    # ========================================================
    # EXTRAIR NÚMERO
    # ========================================================

    def extrair_numero(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "NÚMERO"
        )


    # ========================================================
    # EXTRAIR COMPLEMENTO
    # ========================================================

    def extrair_complemento(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "COMPLEMENTO"
        )


    # ========================================================
    # EXTRAIR CEP
    # ========================================================

    def extrair_cep(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "CEP"
        )


    # ========================================================
    # EXTRAIR BAIRRO
    # ========================================================

    def extrair_bairro(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "BAIRRO/DISTRITO"
        )


    # ========================================================
    # EXTRAIR MUNICÍPIO
    # ========================================================

    def extrair_municipio(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "MUNICÍPIO"
        )


    # ========================================================
    # EXTRAIR UF
    # ========================================================

    def extrair_uf(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "UF"
        )


    # ========================================================
    # EXTRAIR SITUAÇÃO CADASTRAL
    # ========================================================

    def extrair_situacao(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "SITUAÇÃO CADASTRAL"
        )


    # ========================================================
    # EXTRAIR DATA DA SITUAÇÃO
    # ========================================================

    def extrair_data_situacao(
        self,
        linhas
    ):

        return self.valor_apos_campo(
            linhas,
            "DATA DA SITUAÇÃO CADASTRAL"
        )


    # ========================================================
    # EXTRAIR TODOS OS DADOS
    # ========================================================

    def extrair_dados(
        self,
        texto=None
    ):

        if texto is None:

            texto = self.texto

        texto = self.normalizar_texto(
            texto
        )

        linhas = texto.splitlines()

        dados = {

            "cnpj":
                self.extrair_cnpj(
                    texto
                ),

            "razao_social":
                self.extrair_razao_social(
                    linhas
                ),

            "nome_fantasia":
                self.extrair_nome_fantasia(
                    linhas
                ),

            "data_abertura":
                self.extrair_data_abertura(
                    linhas
                ),

            "porte":
                self.extrair_porte(
                    linhas
                ),

            "cnae_principal":
                self.extrair_cnae_principal(
                    linhas
                ),

            "cnae_principal_descricao":
                self.extrair_cnae_principal_detalhe(
                    linhas
                ).get('descricao', ''),

            "cnaes_secundarios":
                self.extrair_cnaes_secundarios(
                    linhas
                ),

            "cnaes_secundarios_detalhes":
                self.extrair_cnaes_secundarios_detalhes(
                    linhas
                ),

            "natureza_juridica":
                self.extrair_natureza_juridica(
                    linhas
                ),

            "logradouro":
                self.extrair_logradouro(
                    linhas
                ),

            "numero":
                self.extrair_numero(
                    linhas
                ),

            "complemento":
                self.extrair_complemento(
                    linhas
                ),

            "cep":
                self.extrair_cep(
                    linhas
                ),

            "bairro":
                self.extrair_bairro(
                    linhas
                ),

            "municipio":
                self.extrair_municipio(
                    linhas
                ),

            "uf":
                self.extrair_uf(
                    linhas
                ),

            "situacao":
                self.extrair_situacao(
                    linhas
                ),

            "data_situacao":
                self.extrair_data_situacao(
                    linhas
                )

        }

        return dados


    # ========================================================
    # SOMENTE NÚMEROS
    # ========================================================

    def somente_numeros(
        self,
        valor
    ):

        return "".join(
            caractere
            for caractere in valor
            if caractere.isdigit()
        )


    # ========================================================
    # VALIDAR CNPJ
    # ========================================================

    def validar_cnpj(
        self,
        cnpj
    ):

        numeros = self.somente_numeros(
            cnpj
        )

        if len(numeros) != 14:

            return False

        if numeros == numeros[0] * 14:

            return False


        # ====================================================
        # PRIMEIRO DÍGITO
        # ====================================================

        pesos_1 = [
            5, 4, 3, 2,
            9, 8, 7, 6,
            5, 4, 3, 2
        ]

        soma = 0

        for indice in range(12):

            soma += (
                int(numeros[indice])
                * pesos_1[indice]
            )

        resto = soma % 11

        if resto < 2:

            digito_1 = 0

        else:

            digito_1 = 11 - resto

        if digito_1 != int(
            numeros[12]
        ):

            return False


        # ====================================================
        # SEGUNDO DÍGITO
        # ====================================================

        pesos_2 = [
            6, 5, 4, 3, 2,
            9, 8, 7, 6,
            5, 4, 3, 2
        ]

        soma = 0

        for indice in range(13):

            soma += (
                int(numeros[indice])
                * pesos_2[indice]
            )

        resto = soma % 11

        if resto < 2:

            digito_2 = 0

        else:

            digito_2 = 11 - resto

        if digito_2 != int(
            numeros[13]
        ):

            return False

        return True


# ============================================================
# TESTE DIRETO
# ============================================================

if __name__ == "__main__":

    caminho = (
        r"C:\Users\usuario\Downloads"
        r"\CNPJ - S E B TEIXEIRA.pdf"
    )

    leitor = LeitorCNPJ()

    texto = leitor.ler_pdf(
        caminho
    )

    dados = leitor.extrair_dados(
        texto
    )

    print()
    print("=" * 70)
    print("RESULTADO DA EXTRAÇÃO")
    print("=" * 70)
    print()

    for campo, valor in dados.items():

        print(
            f"{campo}: {valor}"
        )