import os
import tempfile
import unittest
from unittest import mock

from dados_db import database as db


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patcher=mock.patch.object(db,'DB_PATH',os.path.join(self.tmp.name,'teste.db'))
        self.patcher.start(); db.inicializar_banco()

    def tearDown(self):
        self.patcher.stop(); self.tmp.cleanup()

    def test_crud_e_historico(self):
        eid=db.salvar_empresa({'razao_social':'Empresa Teste','cnpj':'00.000.000/0001-00','regime_atual':'Simples Nacional'})
        self.assertEqual(db.obter_empresa(eid)['razao_social'],'Empresa Teste')
        db.salvar_faturamento(eid,'2026-01',10000,1000)
        db.salvar_folha(eid,'2026-01',2000,500,300,100)
        self.assertEqual(len(db.historico_faturamento(eid)),1)
        self.assertEqual(len(db.historico_folha(eid)),1)

    def test_upsert_competencia(self):
        eid=db.salvar_empresa({'razao_social':'Empresa 2','cnpj':'00.000.000/0002-00'})
        db.salvar_faturamento(eid,'2026-01',10000,0)
        db.salvar_faturamento(eid,'2026-01',20000,0)
        self.assertEqual(db.historico_faturamento(eid)[0]['receita_interna'],20000)

    def test_negativo_bloqueia(self):
        eid=db.salvar_empresa({'razao_social':'Empresa 3','cnpj':'00.000.000/0003-00'})
        with self.assertRaises(ValueError): db.salvar_faturamento(eid,'2026-01',-1,0)

    def test_salvar_apuracao(self):
        eid=db.salvar_empresa({'razao_social':'Empresa 4','cnpj':'00.000.000/0004-00'})
        result={'anexo':'Anexo I','rbt12':120000,'fs12':0,'fator_r':None,'receita_mes':10000,'das_mensal':400,'aliquota_efetiva':4,'faixa':1,'memoria':{},'versao_regra':'2026.08'}
        db.salvar_apuracao(eid,'2026-01',result,[{'tipo':'normal','valor':10000,'anexo':'Anexo I'}])
        self.assertEqual(len(db.historico_apuracoes(eid)),1)


if __name__=='__main__': unittest.main()

class TestCadastroPDF(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patcher=mock.patch.object(db,'DB_PATH',os.path.join(self.tmp.name,'pdf.db'))
        self.patcher.start(); db.inicializar_banco()

    def tearDown(self):
        self.patcher.stop(); self.tmp.cleanup()

    def test_cadastro_pdf_e_atualizacao_por_cnpj(self):
        dados={'razao_social':'Empresa PDF Ltda','cnpj':'11.222.333/0001-81','cnae_principal':'47.11-3-02','cnaes_secundarios':['47.12-1-00'],'porte':'ME','municipio':'Macaé','uf':'RJ','situacao':'ATIVA'}
        eid=db.salvar_empresa_por_pdf(dados)
        self.assertEqual(db.obter_empresa(eid)['origem_cadastro'],'PDF CNPJ')
        dados['nome_fantasia']='EMPRESA PDF'; eid2=db.salvar_empresa_por_pdf(dados)
        self.assertEqual(eid,eid2)
        self.assertEqual(len(db.listar_empresas()),1)
        self.assertEqual(db.obter_empresa(eid)['nome_fantasia'],'EMPRESA PDF')
