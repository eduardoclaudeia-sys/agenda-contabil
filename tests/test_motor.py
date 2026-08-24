import os
import tempfile
import unittest

from motor import simples_nacional, simples_avancado
from motor.lucro_presumido import calcular_lucro_presumido, comparar_com_simples


class TestSimplesBasico(unittest.TestCase):
    def test_anexo_i_2_faixa(self):
        r=simples_nacional.calcular_simples('Anexo I',300000,30000)
        self.assertEqual(r['faixa'],2)
        self.assertAlmostEqual(r['aliquota_efetiva'],5.32,places=2)
        self.assertAlmostEqual(r['das_mensal'],1596,places=2)

    def test_anexo_ii_correcao_faixa_3(self):
        r=simples_nacional.calcular_simples('Anexo II',500000,50000)
        esperado=((500000*.10)-13860)/500000*100
        self.assertAlmostEqual(r['aliquota_efetiva'],esperado,places=6)

    def test_limites(self):
        self.assertEqual(simples_nacional.calcular_simples('Anexo I',180000,1000)['faixa'],1)
        self.assertEqual(simples_nacional.calcular_simples('Anexo I',180000.01,1000)['faixa'],2)
        self.assertEqual(simples_nacional.calcular_simples('Anexo I',4800000,1000)['faixa'],6)


class TestFatorR(unittest.TestCase):
    def test_fator_r_truncado(self):
        self.assertEqual(simples_avancado.calcular_fator_r(2774,10000),.27)

    def test_fator_r_corte(self):
        self.assertEqual(simples_avancado.resolver_anexo_fator_r('Anexo V',True,.28),'Anexo III')
        self.assertEqual(simples_avancado.resolver_anexo_fator_r('Anexo III',True,.27),'Anexo V')

    def test_regras_zero(self):
        self.assertEqual(simples_avancado.calcular_fator_r(0,0),.01)
        self.assertEqual(simples_avancado.calcular_fator_r(100,0),.28)


class TestHistorico(unittest.TestCase):
    def test_primeiro_mes_rbt12(self):
        self.assertEqual(simples_avancado.calcular_rbt12([], '2026-01','2026-01-10',10000),120000)

    def test_terceiro_mes_rbt12(self):
        h=[{'competencia':'2026-01','receita_interna':9000,'receita_externa':0},
           {'competencia':'2026-02','receita_interna':40000,'receita_externa':0}]
        self.assertEqual(simples_avancado.calcular_rbt12(h,'2026-03','2026-01-10',6000),294000)

    def test_empresa_madura_usa_12_anteriores(self):
        h=[]
        for y,m in [(2025,m) for m in range(1,13)]+[(2026,1)]:
            h.append({'competencia':f'{y}-{m:02d}','receita_interna':10000,'receita_externa':0})
        self.assertEqual(simples_avancado.calcular_rbt12(h,'2026-02','2024-01-01',10000),120000)


class TestSegregacao(unittest.TestCase):
    def test_normal_anexo_i(self):
        r=simples_avancado.calcular_apuracao('Anexo I',300000,100000)
        self.assertAlmostEqual(r['das_mensal'],5320,places=2)
        self.assertAlmostEqual(sum(r['tributos'].values()),5320,places=2)

    def test_monofasico_reduz_pis_cofins(self):
        normal=simples_avancado.calcular_apuracao('Anexo I',300000,100000)
        mono=simples_avancado.calcular_apuracao('Anexo I',300000,100000,[{'tipo':'monofasico','valor':100000}])
        self.assertLess(mono['das_mensal'],normal['das_mensal'])
        self.assertEqual(mono['tributos']['PIS/Pasep'],0)
        self.assertEqual(mono['tributos']['COFINS'],0)

    def test_st_reduz_icms(self):
        r=simples_avancado.calcular_apuracao('Anexo I',300000,100000,[{'tipo':'icms_st','valor':100000}])
        self.assertEqual(r['tributos']['ICMS'],0)

    def test_exportacao_comercio(self):
        r=simples_avancado.calcular_apuracao('Anexo I',300000,100000,[{'tipo':'exportacao','valor':100000}])
        self.assertEqual(r['tributos']['PIS/Pasep'],0)
        self.assertEqual(r['tributos']['COFINS'],0)
        self.assertEqual(r['tributos']['ICMS'],0)

    def test_iss_retido(self):
        r=simples_avancado.calcular_apuracao('Anexo III',300000,100000,[{'tipo':'iss_retido','valor':100000}])
        self.assertEqual(r['tributos']['ISS'],0)

    def test_segregacao_precisa_fechar(self):
        with self.assertRaises(ValueError):
            simples_avancado.calcular_apuracao('Anexo I',300000,100000,[{'tipo':'normal','valor':90000}])

    def test_multiplos_segmentos(self):
        r=simples_avancado.calcular_apuracao('Anexo I',300000,100000,[
            {'tipo':'normal','valor':50000},{'tipo':'monofasico','valor':30000},{'tipo':'icms_st','valor':20000}])
        self.assertGreater(r['das_mensal'],0)
        self.assertEqual(len(r['segmentos']),3)

    def test_anexo_iv_sem_cpp_no_das(self):
        r=simples_avancado.calcular_apuracao('Anexo IV',300000,100000)
        self.assertNotIn('CPP',r['tributos'])

    def test_alerta_sublimite(self):
        r=simples_avancado.calcular_apuracao('Anexo I',3700000,100000)
        self.assertTrue(any('sublimite' in msg.lower() for _,msg in r['alertas']))


class TestLucroPresumido(unittest.TestCase):
    def test_comercio(self):
        r=calcular_lucro_presumido(100000,'comercio')
        self.assertAlmostEqual(r['base_irpj'],24000)
        self.assertAlmostEqual(r['base_csll'],36000)
        self.assertGreater(r['total_trimestre'],0)

    def test_servico_presuncao(self):
        r=calcular_lucro_presumido(100000,'servico')
        self.assertEqual(r['presuncao_irpj'],.32)
        self.assertEqual(r['presuncao_csll'],.32)
        self.assertGreater(r['Adicional IRPJ'],0)

    def test_comparador(self):
        r=comparar_com_simples(10000,receita_mensal=100000,tipo_atividade='comercio')
        self.assertIn(r['cenario_mais_economico'],('Simples Nacional','Lucro Presumido','Equivalente'))


if __name__=='__main__': unittest.main()
