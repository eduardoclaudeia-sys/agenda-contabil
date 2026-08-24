import os
import tempfile
import unittest

from motor import simples_avancado
from servicos.validacoes import validar_cnpj, validar_competencia
from servicos.relatorios import gerar_relatorio_html, gerar_relatorio_pdf


class TestValidacoes(unittest.TestCase):
    def test_cnpj_valido_e_invalido(self):
        self.assertTrue(validar_cnpj('11.222.333/0001-81'))
        self.assertFalse(validar_cnpj('11.222.333/0001-82'))
        self.assertFalse(validar_cnpj('00.000.000/0000-00'))

    def test_competencia(self):
        self.assertTrue(validar_competencia('2026-08'))
        self.assertTrue(validar_competencia('08/2026'))
        self.assertFalse(validar_competencia('2026-13'))


class TestMotorAdicional(unittest.TestCase):
    def test_monofasico_e_st_combinados(self):
        r = simples_avancado.calcular_apuracao(
            'Anexo I', 300000, 100000,
            [{'tipo': 'monofasico_icms_st', 'valor': 100000}]
        )
        self.assertEqual(r['tributos']['PIS/Pasep'], 0)
        self.assertEqual(r['tributos']['COFINS'], 0)
        self.assertEqual(r['tributos']['ICMS'], 0)

    def test_projecao_receita(self):
        h = [
            {'competencia': '2026-01', 'receita_interna': 10000, 'receita_externa': 0},
            {'competencia': '2026-02', 'receita_interna': 20000, 'receita_externa': 0},
            {'competencia': '2026-03', 'receita_interna': 30000, 'receita_externa': 0},
        ]
        p = simples_avancado.projetar_receita(h, meses_futuros=2, janela_media=3)
        self.assertEqual(p['media_mensal'], 20000)
        self.assertEqual(p['projecao'], [20000, 20000])
        self.assertEqual(p['rbt12_projetado'], 100000)


class TestRelatorios(unittest.TestCase):
    def _resultado(self):
        return simples_avancado.calcular_apuracao(
            'Anexo I', 300000, 100000,
            [{'tipo': 'normal', 'valor': 60000}, {'tipo': 'monofasico', 'valor': 40000}]
        )

    def test_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = os.path.join(tmp, 'relatorio.html')
            gerar_relatorio_html({'razao_social': 'Empresa Teste', 'cnpj': '11.222.333/0001-81'}, '2026-08', self._resultado(), arq)
            self.assertTrue(os.path.exists(arq))
            with open(arq, encoding='utf-8') as f:
                conteudo = f.read()
            self.assertIn('Motor Tributário JSM', conteudo)
            self.assertIn('Composição estimada do DAS', conteudo)

    def test_pdf(self):
        try:
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest('ReportLab não instalado')
        with tempfile.TemporaryDirectory() as tmp:
            arq = os.path.join(tmp, 'relatorio.pdf')
            gerar_relatorio_pdf({'razao_social': 'Empresa Teste', 'cnpj': '11.222.333/0001-81'}, '2026-08', self._resultado(), arq)
            self.assertTrue(os.path.exists(arq))
            self.assertGreater(os.path.getsize(arq), 1000)


if __name__ == '__main__':
    unittest.main()

class TestDetalhamentoCalculo(unittest.TestCase):
    def test_reducao_e_carga_final(self):
        r=simples_avancado.calcular_apuracao('Anexo I',300000,100000,[{'tipo':'normal','valor':60000},{'tipo':'monofasico','valor':40000}])
        self.assertGreater(r['das_sem_tratamentos'],r['das_mensal'])
        self.assertGreater(r['economia_tratamentos'],0)
        self.assertAlmostEqual(r['carga_efetiva_final'],r['das_mensal']/100000*100,places=6)
        self.assertGreater(r['reducoes_por_tratamento']['COFINS'],0)
