import unittest
from motor.lucro_presumido import calcular_lucro_presumido_misto_2026
from motor.lucro_real import calcular_lucro_real
from motor.simples_avancado import calcular_apuracao, calcular_rbt12
from servicos.explanations import EXPLICACOES
from servicos.validacoes import validar_cnpj

class TestV5Motores(unittest.TestCase):
    def test_presumido_misto(self):
        r=calcular_lucro_presumido_misto_2026([{'tipo':'comercio','receita':600000},{'tipo':'servico','receita':400000}],trimestre=2)
        self.assertEqual(len(r['atividades']),2); self.assertGreater(r['base_irpj'],0)
    def test_real_compensacao_menor_que_limite(self):
        r=calcular_lucro_real(500000,100000,meses_periodo=3,prejuizo_fiscal_disponivel=10000)
        self.assertAlmostEqual(r['compensacao_irpj'],10000)
    def test_real_credito_maior_que_debito_nao_negativa(self):
        r=calcular_lucro_real(100000,10000,meses_periodo=1,creditos_pis=99999,creditos_cofins=99999)
        self.assertEqual(r['PIS/Pasep'],0); self.assertEqual(r['COFINS'],0)
    def test_simples_exportacao_anexo_ii(self):
        r=calcular_apuracao('Anexo II',500000,10000,[{'tipo':'exportacao','valor':10000,'anexo':'Anexo II'}],competencia='2026-08')
        self.assertIn('IPI',r['segmentos'][0]['exclusoes']); self.assertIn('ICMS',r['segmentos'][0]['exclusoes'])
    def test_rbt12_inicio_6_meses(self):
        hist=[{'competencia':f'2026-0{i}','receita_interna':10000,'receita_externa':0} for i in range(1,6)]
        self.assertAlmostEqual(calcular_rbt12(hist,'2026-06',data_abertura='2026-01-10'),120000)
    def test_explicacoes_cobrem_fluxos(self):
        for k in ['simples','presumido','real','comparador','rbt12','fator_r','segregacao','cnpj','xml','fechamento','memoria']:
            self.assertIn(k,EXPLICACOES)
    def test_cnpj_validator(self):
        self.assertTrue(validar_cnpj('11.222.333/0001-81'))

if __name__=='__main__': unittest.main()
