from __future__ import annotations

import os
import tempfile
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for, session

from extensions import db
from helpers import admin_required, auditar, competencia_fechada, login_required, num, numeros, sincronizar_competencia
from leitor_cnpj import LeitorCNPJ
from motor.classificador_cnae import classificar_cnae
from models import Apuracao, CalculoRegime, Empresa, FechamentoCompetencia, Folha, Faturamento
from servicos.validacoes import validar_cnpj, validar_competencia
from servicos.cnpj_api import consultar_cnpj_brasilapi
from servicos.xml_nfe import analisar_nfe_bytes

bp = Blueprint("empresas", __name__, url_prefix="/empresas")


def _salvar_campos_empresa(emp: Empresa, form) -> None:
    cnpj = numeros(form.get("cnpj"))
    if cnpj and not validar_cnpj(cnpj):
        raise ValueError("CNPJ inválido.")
    if cnpj:
        existente = Empresa.query.filter(Empresa.cnpj == cnpj, Empresa.id != (emp.id or 0)).first()
        if existente:
            raise ValueError("Já existe uma empresa cadastrada com este CNPJ.")
        emp.cnpj = cnpj
    campos = (
        "razao_social", "nome_fantasia", "data_abertura", "cnae_principal", "regime_atual",
        "uf", "municipio", "situacao_cadastral", "porte", "natureza_juridica",
        "inscricao_estadual", "inscricao_municipal", "observacoes",
    )
    for campo in campos:
        if campo in form:
            setattr(emp, campo, (form.get(campo) or "").strip())
    if not emp.razao_social:
        raise ValueError("Informe a razão social.")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        try:
            emp = Empresa(razao_social=(request.form.get("razao_social") or "").strip())
            _salvar_campos_empresa(emp, request.form)
            emp.origem_cadastro = "Manual"
            db.session.add(emp)
            db.session.flush()
            auditar("criar_empresa", emp.id, "empresa", emp.id, {"cnpj": emp.cnpj})
            db.session.commit()
            flash("Empresa cadastrada.", "ok")
            return redirect(url_for("empresas.detalhe", empresa_id=emp.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "erro")
    busca = (request.args.get("q") or "").strip()
    query = Empresa.query
    if busca:
        like = f"%{busca}%"
        query = query.filter((Empresa.razao_social.ilike(like)) | (Empresa.nome_fantasia.ilike(like)) | (Empresa.cnpj.ilike(like)))
    return render_template("empresas.html", empresas=query.order_by(Empresa.razao_social.asc()).all(), busca=busca)


@bp.route("/<int:empresa_id>", methods=["GET", "POST"])
@login_required
def detalhe(empresa_id: int):
    emp = db.get_or_404(Empresa, empresa_id)
    if request.method == "POST":
        try:
            _salvar_campos_empresa(emp, request.form)
            auditar("editar_empresa", emp.id, "empresa", emp.id)
            db.session.commit()
            flash("Dados da empresa atualizados.", "ok")
            return redirect(url_for("empresas.detalhe", empresa_id=emp.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "erro")
    faturamentos = Faturamento.query.filter_by(empresa_id=emp.id).order_by(Faturamento.competencia.desc()).limit(24).all()
    folhas = Folha.query.filter_by(empresa_id=emp.id).order_by(Folha.competencia.desc()).limit(24).all()
    apuracoes = Apuracao.query.filter_by(empresa_id=emp.id).order_by(Apuracao.competencia.desc()).limit(24).all()
    calculos = CalculoRegime.query.filter_by(empresa_id=emp.id).order_by(CalculoRegime.criado_em.desc()).limit(24).all()
    fechamentos = {x.competencia: x for x in FechamentoCompetencia.query.filter_by(empresa_id=emp.id).all()}
    classificacao = classificar_cnae(emp.cnae_principal) if emp.cnae_principal else None
    return render_template("empresa_detalhe.html", emp=emp, faturamentos=faturamentos, folhas=folhas,
                           apuracoes=apuracoes, calculos=calculos, fechamentos=fechamentos, classificacao=classificacao)



@bp.route("/consultar-cnpj", methods=["POST"])
@login_required
def consultar_cnpj():
    cnpj = numeros(request.form.get("cnpj_consulta"))
    try:
        if not validar_cnpj(cnpj): raise ValueError("CNPJ inválido.")
        dados = consultar_cnpj_brasilapi(cnpj)
        emp = Empresa.query.filter_by(cnpj=cnpj).first()
        if not emp:
            emp = Empresa(razao_social=dados.get("razao_social") or "Empresa sem razão social", cnpj=cnpj); db.session.add(emp)
        for campo, valor in dados.items():
            if hasattr(emp, campo) and valor not in (None, ""): setattr(emp, campo, valor)
        db.session.flush(); auditar("consulta_cnpj_externa", emp.id, "empresa", emp.id, {"fonte":"BrasilAPI"}); db.session.commit()
        flash("Dados consultados. Confira com o comprovante oficial antes de usar fiscalmente.", "ok")
        return redirect(url_for("empresas.detalhe", empresa_id=emp.id))
    except Exception as exc:
        db.session.rollback(); flash(str(exc), "erro"); return redirect(url_for("empresas.index"))

@bp.route("/importar-pdf", methods=["POST"])
@login_required
def importar_pdf():
    arq = request.files.get("arquivo_pdf")
    if not arq or not arq.filename:
        flash("Selecione o PDF do comprovante de CNPJ.", "erro")
        return redirect(url_for("empresas.index"))
    conteudo = arq.read()
    if len(conteudo) > 10 * 1024 * 1024:
        flash("O PDF deve ter no máximo 10 MB.", "erro")
        return redirect(url_for("empresas.index"))
    if not conteudo.startswith(b"%PDF-"):
        flash("O arquivo enviado não possui assinatura válida de PDF.", "erro")
        return redirect(url_for("empresas.index"))

    caminho = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(conteudo)
            caminho = tmp.name
        leitor = LeitorCNPJ()
        dados = leitor.extrair_dados(leitor.ler_pdf(caminho))
        cnpj = numeros(dados.get("cnpj"))
        if not validar_cnpj(cnpj):
            raise ValueError("Não foi possível extrair um CNPJ válido do PDF.")
        emp = Empresa.query.filter_by(cnpj=cnpj).first()
        if not emp:
            emp = Empresa(razao_social=dados.get("razao_social") or "Empresa sem razão social", cnpj=cnpj)
            db.session.add(emp)
        mapping = {
            "razao_social": "razao_social", "nome_fantasia": "nome_fantasia", "data_abertura": "data_abertura",
            "cnae_principal": "cnae_principal", "uf": "uf", "municipio": "municipio", "porte": "porte",
            "natureza_juridica": "natureza_juridica", "logradouro": "logradouro", "numero": "numero",
            "complemento": "complemento", "cep": "cep", "bairro": "bairro", "data_situacao": "data_situacao",
        }
        for origem, destino in mapping.items():
            valor = dados.get(origem)
            if valor:
                setattr(emp, destino, valor)
        emp.situacao_cadastral = dados.get("situacao") or emp.situacao_cadastral
        secundarios = dados.get("cnaes_secundarios") or []
        emp.cnaes_secundarios = "; ".join(secundarios) if isinstance(secundarios, list) else str(secundarios)
        emp.origem_cadastro = "PDF CNPJ"
        db.session.flush()
        auditar("importar_pdf_cnpj", emp.id, "empresa", emp.id)
        db.session.commit()
        flash("Dados cadastrais importados do PDF.", "ok")
        return redirect(url_for("empresas.detalhe", empresa_id=emp.id))
    except Exception as exc:
        db.session.rollback()
        flash(f"Falha na importação: {exc}", "erro")
        return redirect(url_for("empresas.index"))
    finally:
        if caminho and os.path.exists(caminho):
            try:
                os.unlink(caminho)
            except OSError:
                pass


@bp.route("/<int:empresa_id>/faturamento", methods=["POST"])
@login_required
def salvar_faturamento(empresa_id: int):
    emp = db.get_or_404(Empresa, empresa_id)
    comp = (request.form.get("competencia") or "").strip()
    try:
        if not validar_competencia(comp):
            raise ValueError("Competência inválida. Use AAAA-MM.")
        if competencia_fechada(emp.id, comp):
            raise ValueError("Competência fechada. Reabra antes de alterar faturamento.")
        interna, externa = num(request.form.get("receita_interna")), num(request.form.get("receita_externa"))
        if interna < 0 or externa < 0:
            raise ValueError("Faturamento não pode ser negativo.")
        row = Faturamento.query.filter_by(empresa_id=emp.id, competencia=comp).first()
        if not row:
            row = Faturamento(empresa_id=emp.id, competencia=comp)
            db.session.add(row)
        row.receita_interna, row.receita_externa = interna, externa
        row.observacoes = (request.form.get("observacoes") or "").strip()
        auditar("salvar_faturamento", emp.id, "faturamento", detalhe={"competencia": comp, "total": interna + externa})
        sincronizar_competencia(emp.id, comp)
        db.session.commit()
        flash("Faturamento salvo.", "ok")
    except Exception as exc:
        db.session.rollback(); flash(str(exc), "erro")
    return redirect(url_for("empresas.detalhe", empresa_id=emp.id))


@bp.route("/<int:empresa_id>/folha", methods=["POST"])
@login_required
def salvar_folha(empresa_id: int):
    emp = db.get_or_404(Empresa, empresa_id)
    comp = (request.form.get("competencia") or "").strip()
    try:
        if not validar_competencia(comp):
            raise ValueError("Competência inválida. Use AAAA-MM.")
        if competencia_fechada(emp.id, comp):
            raise ValueError("Competência fechada. Reabra antes de alterar folha.")
        vals = [num(request.form.get(k)) for k in ("salarios", "pro_labore", "encargos", "outros_fs12")]
        if any(v < 0 for v in vals):
            raise ValueError("Valores da folha não podem ser negativos.")
        row = Folha.query.filter_by(empresa_id=emp.id, competencia=comp).first()
        if not row:
            row = Folha(empresa_id=emp.id, competencia=comp); db.session.add(row)
        row.salarios, row.pro_labore, row.encargos, row.outros_fs12 = vals
        row.observacoes = (request.form.get("observacoes") or "").strip()
        auditar("salvar_folha", emp.id, "folha", detalhe={"competencia": comp, "total": sum(vals)})
        sincronizar_competencia(emp.id, comp)
        db.session.commit(); flash("Folha salva.", "ok")
    except Exception as exc:
        db.session.rollback(); flash(str(exc), "erro")
    return redirect(url_for("empresas.detalhe", empresa_id=emp.id))


@bp.route("/<int:empresa_id>/fechamento", methods=["POST"])
@login_required
def fechamento(empresa_id: int):
    emp = db.get_or_404(Empresa, empresa_id)
    comp = (request.form.get("competencia") or "").strip()
    acao = request.form.get("acao", "fechar")
    try:
        if not validar_competencia(comp):
            raise ValueError("Competência inválida.")
        row = FechamentoCompetencia.query.filter_by(empresa_id=emp.id, competencia=comp).first()
        if not row:
            row = FechamentoCompetencia(empresa_id=emp.id, competencia=comp); db.session.add(row)
        if acao == "reabrir" and session.get("papel") != "admin":
            raise ValueError("Somente administrador pode reabrir uma competência fechada.")
        row.fechado = acao == "fechar"
        row.fechado_em = datetime.utcnow() if row.fechado else None
        row.fechado_por = session.get("usuario_id")
        row.observacao = (request.form.get("observacao") or "").strip()
        auditar("fechar_competencia" if row.fechado else "reabrir_competencia", emp.id, "competencia", detalhe={"competencia": comp})
        sincronizar_competencia(emp.id, comp)
        db.session.commit(); flash("Competência fechada." if row.fechado else "Competência reaberta.", "ok")
    except Exception as exc:
        db.session.rollback(); flash(str(exc), "erro")
    return redirect(url_for("empresas.detalhe", empresa_id=emp.id))


@bp.route("/<int:empresa_id>/xml", methods=["GET", "POST"])
@login_required
def importar_xml(empresa_id: int):
    emp = db.get_or_404(Empresa, empresa_id)
    resultado = None
    if request.method == "POST":
        arq = request.files.get("arquivo_xml")
        try:
            if not arq or not arq.filename:
                raise ValueError("Selecione um XML de NF-e.")
            conteudo = arq.read()
            if len(conteudo) > 10 * 1024 * 1024:
                raise ValueError("O XML deve ter no máximo 10 MB.")
            resultado = analisar_nfe_bytes(conteudo)
            auditar("analisar_xml_nfe", emp.id, "xml_nfe", detalhe={"numero": resultado.get("numero"), "chave": resultado.get("chave")})
            db.session.commit()
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "erro")
    return render_template("xml_import.html", emp=emp, resultado=resultado)
