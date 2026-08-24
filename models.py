from __future__ import annotations

from datetime import datetime
from extensions import db


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), nullable=False, unique=True, index=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class UsuarioPapel(db.Model):
    __tablename__ = "usuarios_papeis"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True)
    papel = db.Column(db.String(30), nullable=False, default="admin")
    usuario = db.relationship("Usuario", backref=db.backref("papel_registro", uselist=False, cascade="all, delete-orphan"))


class Empresa(db.Model):
    __tablename__ = "empresas"
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(220), nullable=False, index=True)
    nome_fantasia = db.Column(db.String(220))
    cnpj = db.Column(db.String(14), unique=True, index=True)
    data_abertura = db.Column(db.String(20))
    cnae_principal = db.Column(db.String(30))
    cnaes_secundarios = db.Column(db.Text)
    regime_atual = db.Column(db.String(80), default="Simples Nacional")
    uf = db.Column(db.String(4))
    municipio = db.Column(db.String(120))
    situacao_cadastral = db.Column(db.String(80))
    porte = db.Column(db.String(100))
    natureza_juridica = db.Column(db.String(220))
    logradouro = db.Column(db.String(220))
    numero = db.Column(db.String(30))
    complemento = db.Column(db.String(120))
    cep = db.Column(db.String(20))
    bairro = db.Column(db.String(120))
    data_situacao = db.Column(db.String(20))
    origem_cadastro = db.Column(db.String(80))
    inscricao_estadual = db.Column(db.String(80))
    inscricao_municipal = db.Column(db.String(80))
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Faturamento(db.Model):
    __tablename__ = "faturamentos"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    competencia = db.Column(db.String(7), nullable=False)
    receita_interna = db.Column(db.Float, nullable=False, default=0)
    receita_externa = db.Column(db.Float, nullable=False, default=0)
    observacoes = db.Column(db.Text)
    empresa = db.relationship("Empresa", backref=db.backref("faturamentos", cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("empresa_id", "competencia", name="uq_faturamento_empresa_comp"),)


class Folha(db.Model):
    __tablename__ = "folhas"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    competencia = db.Column(db.String(7), nullable=False)
    salarios = db.Column(db.Float, nullable=False, default=0)
    pro_labore = db.Column(db.Float, nullable=False, default=0)
    encargos = db.Column(db.Float, nullable=False, default=0)
    outros_fs12 = db.Column(db.Float, nullable=False, default=0)
    observacoes = db.Column(db.Text)
    empresa = db.relationship("Empresa", backref=db.backref("folhas", cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("empresa_id", "competencia", name="uq_folha_empresa_comp"),)


class CompetenciaResumo(db.Model):
    """Consolidação V5 por empresa/competência, preservando as tabelas históricas."""
    __tablename__ = "competencias_v5"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    ano_mes = db.Column(db.String(7), nullable=False)
    faturamento_bruto = db.Column(db.Float, nullable=False, default=0)
    folha_pagamento = db.Column(db.Float, nullable=False, default=0)
    rbt12 = db.Column(db.Float)
    fs12 = db.Column(db.Float)
    status = db.Column(db.String(20), nullable=False, default="ABERTA")
    atualizado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    empresa = db.relationship("Empresa")
    __table_args__ = (db.UniqueConstraint("empresa_id", "ano_mes", name="uq_competencia_v5_empresa_mes"),)


class Apuracao(db.Model):
    __tablename__ = "apuracoes"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    competencia = db.Column(db.String(7), nullable=False)
    anexo = db.Column(db.String(30), nullable=False)
    rbt12 = db.Column(db.Float, nullable=False)
    fs12 = db.Column(db.Float, nullable=False, default=0)
    fator_r = db.Column(db.Float)
    receita_mes = db.Column(db.Float, nullable=False)
    das_total = db.Column(db.Float, nullable=False)
    aliquota_efetiva = db.Column(db.Float, nullable=False)
    faixa = db.Column(db.Integer)
    versao_regra = db.Column(db.String(40))
    resultado_json = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    empresa = db.relationship("Empresa", backref=db.backref("apuracoes", cascade="all, delete-orphan"))
    __table_args__ = (db.UniqueConstraint("empresa_id", "competencia", name="uq_apuracao_empresa_comp"),)


class CalculoRegime(db.Model):
    __tablename__ = "calculos_regime"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="SET NULL"), index=True)
    regime = db.Column(db.String(40), nullable=False, index=True)
    competencia = db.Column(db.String(20))
    dados_json = db.Column(db.Text, nullable=False)
    resultado_json = db.Column(db.Text, nullable=False)
    total_estimado = db.Column(db.Float, nullable=False, default=0)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    empresa = db.relationship("Empresa")


class Auditoria(db.Model):
    __tablename__ = "auditoria"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="SET NULL"))
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    acao = db.Column(db.String(100), nullable=False)
    detalhe = db.Column(db.Text)
    empresa = db.relationship("Empresa")


class AuditoriaV5(db.Model):
    __tablename__ = "auditoria_v5"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), index=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="SET NULL"), index=True)
    acao = db.Column(db.String(100), nullable=False, index=True)
    registro_tipo = db.Column(db.String(60))
    registro_id = db.Column(db.Integer)
    detalhe_json = db.Column(db.Text)
    ip_origem = db.Column(db.String(64))
    data_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class FechamentoCompetencia(db.Model):
    __tablename__ = "fechamentos_competencia"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False, index=True)
    competencia = db.Column(db.String(7), nullable=False)
    fechado = db.Column(db.Boolean, nullable=False, default=False)
    fechado_em = db.Column(db.DateTime)
    fechado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"))
    observacao = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint("empresa_id", "competencia", name="uq_fechamento_empresa_comp"),)


class ComparacaoTributaria(db.Model):
    __tablename__ = "comparacoes_tributarias"
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id", ondelete="SET NULL"), index=True)
    competencia = db.Column(db.String(20))
    dados_json = db.Column(db.Text, nullable=False)
    resultado_json = db.Column(db.Text, nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    criado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"))
    empresa = db.relationship("Empresa")


class RegraTributariaRegistro(db.Model):
    __tablename__ = "regras_tributarias_registro"
    id = db.Column(db.Integer, primary_key=True)
    regime = db.Column(db.String(50), nullable=False, index=True)
    versao = db.Column(db.String(30), nullable=False)
    vigencia_inicio = db.Column(db.String(10), nullable=False)
    vigencia_fim = db.Column(db.String(10))
    fonte = db.Column(db.Text)
    checksum = db.Column(db.String(64))
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("regime", "versao", name="uq_regra_regime_versao"),)
