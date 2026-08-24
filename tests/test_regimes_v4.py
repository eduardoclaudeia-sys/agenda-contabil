import unittest
from motor.lucro_presumido import calcular_lucro_presumido_2026
from motor.lucro_real import calcular_lucro_real

class TestPresumido2026(unittest.TestCase):
    def test_sem_excedente(self):
        r = calcular_lucro_presumido_2026(900000, 'comercio', trimestre=1)
        self.assertEqual(r['receita_excedente'], 0)
        self.assertAlmostEqual(r['base_irpj'], 72000)

    def test_excedente_irpj(self):
        r = calcular_lucro_presumido_2026(1500000, 'comercio', trimestre=1)
        esperado = 1250000*.08 + 250000*.088
        self.assertAlmostEqual(r['base_irpj'], esperado)

    def test_csll_q1_sem_acrescimo_e_q2_com(self):
        q1 = calcular_lucro_presumido_2026(1500000, 'comercio', trimestre=1)
        q2 = calcular_lucro_presumido_2026(1500000, 'comercio', trimestre=2)
        self.assertLess(q1['base_csll'], q2['base_csll'])

class TestLucroReal(unittest.TestCase):
    def test_irpj_adicional(self):
        r = calcular_lucro_real(500000, 100000, meses_periodo=3)
        self.assertAlmostEqual(r['IRPJ'], 15000)
        self.assertAlmostEqual(r['Adicional IRPJ'], 4000)

    def test_compensacao_30(self):
        r = calcular_lucro_real(500000, 100000, prejuizo_fiscal_disponivel=100000, meses_periodo=3)
        self.assertAlmostEqual(r['compensacao_irpj'], 30000)
        self.assertAlmostEqual(r['base_irpj'], 70000)

    def test_creditos_pis_cofins(self):
        r = calcular_lucro_real(100000, 20000, meses_periodo=1, creditos_pis=500, creditos_cofins=1000)
        self.assertAlmostEqual(r['PIS/Pasep'], 1150)
        self.assertAlmostEqual(r['COFINS'], 6600)

if __name__ == '__main__':
    unittest.main()
