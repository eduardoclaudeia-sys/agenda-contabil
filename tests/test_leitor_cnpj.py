import unittest
from leitor_cnpj import LeitorCNPJ


class TestLeitorCNPJ(unittest.TestCase):
    def test_extrai_cnaes_em_bloco(self):
        texto='''
NÚMERO DE INSCRIÇÃO
11.222.333/0001-81
NOME EMPRESARIAL
EMPRESA TESTE LTDA
CÓDIGO E DESCRIÇÃO DA ATIVIDADE ECONÔMICA PRINCIPAL
47.11-3-02 - Comércio varejista de mercadorias em geral
CÓDIGO E DESCRIÇÃO DAS ATIVIDADES ECONÔMICAS SECUNDÁRIAS
47.12-1-00 - Comércio varejista de mercadorias em geral
82.19-9-99 - Preparação de documentos
CÓDIGO E DESCRIÇÃO DA NATUREZA JURÍDICA
206-2 - Sociedade Empresária Limitada
MUNICÍPIO
MACAÉ
UF
RJ
SITUAÇÃO CADASTRAL
ATIVA
'''
        d=LeitorCNPJ().extrair_dados(texto)
        self.assertEqual(d['cnae_principal'],'47.11-3-02')
        self.assertEqual(len(d['cnaes_secundarios']),2)
        self.assertEqual(d['cnaes_secundarios'][1],'82.19-9-99')
        self.assertIn('Comércio varejista',d['cnae_principal_descricao'])

if __name__=='__main__': unittest.main()
