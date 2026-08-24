import json
import html
from datetime import datetime

from servicos.explicacao_tributaria import explicar_resultado, TIPOS_RECEITA


def formatar_moeda(v):
    return f'R$ {float(v or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X','.')


def formatar_pct(v, casas=2):
    return f'{float(v or 0):.{casas}f}%'.replace('.', ',')


def _linhas_memoria(resultado):
    m=resultado.get('memoria',{})
    linhas=[
        f"RBT12: {formatar_moeda(m.get('rbt12',0))}",
        f"Anexo aplicado: {m.get('anexo_aplicado','')}",
        f"Faixa: {m.get('faixa','')}",
        f"Alíquota nominal: {float(m.get('aliquota_nominal',0))*100:.2f}%",
        f"Parcela a deduzir: {formatar_moeda(m.get('parcela_deduzir',0))}",
        f"Alíquota efetiva base: {float(m.get('aliquota_efetiva_base',0))*100:.4f}%",
        "Fórmula: ((RBT12 x alíquota nominal) - parcela a deduzir) / RBT12",
    ]
    if m.get('fator_r') is not None:
        linhas.insert(2,f"Fator R: {float(m.get('fator_r')):.2%}")
    return linhas


def gerar_relatorio_html(empresa, competencia, resultado, destino, contexto=None):
    contexto = contexto or {}
    exp = explicar_resultado(resultado)
    esc = lambda x: html.escape(str(x or ''))
    trib_rows=''.join(
        '<tr>'
        f"<td><b>{esc(x['sigla'])}</b><br><small>{esc(x['nome'])}</small></td>"
        f"<td>{formatar_moeda(x['valor_sem_tratamento'])}</td>"
        f"<td>{formatar_moeda(x['reducao'])}</td>"
        f"<td><b>{formatar_moeda(x['valor_cobrado'])}</b></td>"
        f"<td>{esc(x['status'])}<br><small>{esc(x['descricao'])}</small></td>"
        '</tr>' for x in exp['tributos']
    )
    alert_rows=''.join(f'<li><b>{esc(nivel)}</b> - {esc(msg)}</li>' for nivel,msg in resultado.get('alertas',[]))
    seg_rows=''.join(
        f"<tr><td>{esc(s.get('tipo'))}<br><small>{esc(TIPOS_RECEITA.get(s.get('tipo'),''))}</small></td>"
        f"<td>{esc(s.get('anexo'))}</td><td>{formatar_moeda(s.get('valor',0))}</td>"
        f"<td>{formatar_pct(float(s.get('aliquota_efetiva_segmento',0))*100,4)}</td>"
        f"<td>{formatar_moeda(s.get('das_segmento',0))}</td><td>{esc(', '.join(s.get('exclusoes') or []) or 'Nenhuma')}</td></tr>"
        for s in resultado.get('segmentos',[])
    )
    passos=''.join(f'<li>{esc(p)}</li>' for p in exp['passos'])
    cnpj=esc(empresa.get('cnpj',''))
    html_doc=f'''<!doctype html><html><head><meta charset="utf-8"><title>Relatório Tributário JSM</title>
<style>
@page{{size:A4;margin:24mm 18mm}}body{{font-family:Arial,sans-serif;margin:0;color:#17324d;font-size:13px;line-height:1.45}}
.header{{background:#0B4F8A;color:white;padding:22px 26px}}.header h1{{margin:0;font-size:24px}}.header p{{margin:5px 0 0;color:#eaf3fa}}
.section{{margin:22px 26px}}h2{{color:#083B66;border-bottom:2px solid #EAF3FA;padding-bottom:6px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.card{{border:1px solid #d7e1ea;border-radius:7px;padding:12px;background:#f8fbfd}}
.card small{{color:#5b6570}}.card b{{display:block;font-size:18px;color:#0B4F8A;margin-top:4px}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:12px}}th,td{{border:1px solid #d7dee5;padding:8px;vertical-align:top}}th{{background:#EAF3FA;text-align:left;color:#083B66}}
.warn{{background:#fff7dc;border-left:4px solid #f59e0b;padding:12px 16px}}.formula{{background:#f4f6f8;border-left:4px solid #0B4F8A;padding:12px 16px}}
.footer{{margin:24px 26px;color:#697887;font-size:10px;border-top:1px solid #d7dee5;padding-top:10px}}
</style></head><body>
<div class="header"><h1>Relatório de Análise Tributária</h1><p>Motor Tributário JSM - Simples Nacional</p></div>
<div class="section"><h2>1. Identificação da empresa</h2><p><b>{esc(empresa.get('razao_social',''))}</b><br>CNPJ: {cnpj} &nbsp; | &nbsp; Competência: {esc(competencia)}<br>CNAE analisado: {esc(contexto.get('cnae') or empresa.get('cnae_principal',''))} {esc(contexto.get('descricao_cnae',''))}</p></div>
<div class="section"><h2>2. Resumo da apuração</h2><div class="grid">
<div class="card"><small>Anexo / Faixa</small><b>{esc(resultado.get('anexo'))} - {esc(resultado.get('faixa'))}</b></div>
<div class="card"><small>RBT12</small><b>{formatar_moeda(resultado.get('rbt12',0))}</b></div>
<div class="card"><small>FS12</small><b>{formatar_moeda(resultado.get('fs12',0))}</b></div>
<div class="card"><small>Alíquota efetiva base</small><b>{formatar_pct(resultado.get('aliquota_efetiva',0),4)}</b></div>
<div class="card"><small>Carga efetiva final</small><b>{formatar_pct(resultado.get('carga_efetiva_final',0),4)}</b></div>
<div class="card"><small>DAS estimado</small><b>{formatar_moeda(resultado.get('das_mensal',0))}</b></div>
</div></div>
<div class="section"><h2>3. Dados financeiros e segregação</h2><p>Faturamento da competência: <b>{formatar_moeda(resultado.get('receita_mes',0))}</b>. A segregação abaixo é parte essencial da simulação, porque tratamentos como monofásico, ST, exportação ou ISS retido alteram parcelas específicas do DAS.</p>
<table><tr><th>Natureza da receita</th><th>Anexo</th><th>Receita</th><th>Alíquota do segmento</th><th>DAS</th><th>Parcelas retiradas</th></tr>{seg_rows}</table></div>
<div class="section"><h2>4. Como o cálculo foi feito</h2><div class="formula"><ol>{passos}</ol><p><b>Alíquota nominal:</b> {formatar_pct(resultado.get('aliquota_nominal',0),2)} &nbsp; | &nbsp; <b>Parcela a deduzir:</b> {formatar_moeda(resultado.get('parcela_deduzir',0))}</p>
<p><b>DAS sem os tratamentos especiais informados:</b> {formatar_moeda(resultado.get('das_sem_tratamentos', resultado.get('das_mensal',0)))}<br><b>Redução estimada pelos tratamentos informados:</b> {formatar_moeda(resultado.get('economia_tratamentos',0))}</p></div></div>
<div class="section"><h2>5. Composição estimada do DAS e explicação de cada tributo</h2><table><tr><th>Tributo</th><th>Antes dos tratamentos</th><th>Redução</th><th>No DAS</th><th>Por que entrou / saiu</th></tr>{trib_rows}</table></div>
<div class="section"><h2>6. Alertas e pontos de conferência</h2><div class="warn"><ul>{alert_rows or '<li>Nenhum alerta adicional gerado pelo motor.</li>'}</ul></div></div>
<div class="section"><h2>7. Memória técnica</h2><div class="formula">{'<br>'.join(esc(x) for x in _linhas_memoria(resultado))}</div></div>
<div class="footer">Regra parametrizada: {esc(resultado.get('versao_regra',''))} | Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}. {esc(exp['observacao'])}</div>
</body></html>'''
    with open(destino,'w',encoding='utf-8') as f:
        f.write(html_doc)
    return destino


def gerar_relatorio_pdf(empresa, competencia, resultado, destino, contexto=None):
    contexto = contexto or {}
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            KeepTogether, PageBreak
        )
    except ImportError as e:
        raise RuntimeError('Para exportar PDF, instale reportlab: pip install reportlab') from e

    exp = explicar_resultado(resultado)
    AZUL = colors.HexColor('#0B4F8A'); AZUL_E = colors.HexColor('#083B66')
    AZUL_C = colors.HexColor('#EAF3FA'); CINZA = colors.HexColor('#F4F6F8')
    TEXTO = colors.HexColor('#263746'); BORDA = colors.HexColor('#D7DEE5')
    AMARELO = colors.HexColor('#FFF7DC')

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle('JSMTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=21, leading=25, textColor=colors.white, spaceAfter=0)
    subtitulo = ParagraphStyle('JSMSub', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.5, leading=13, textColor=colors.HexColor('#EAF3FA'))
    h2 = ParagraphStyle('JSMH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=AZUL_E, spaceBefore=8, spaceAfter=7)
    body = ParagraphStyle('JSMBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.2, leading=13, textColor=TEXTO)
    small = ParagraphStyle('JSMSmall', parent=body, fontSize=7.7, leading=10, textColor=colors.HexColor('#5B6570'))
    cell = ParagraphStyle('JSMCell', parent=body, fontSize=7.8, leading=10)
    cell_b = ParagraphStyle('JSMCellB', parent=cell, fontName='Helvetica-Bold', textColor=AZUL_E)
    cell_head = ParagraphStyle('JSMCellHead', parent=cell, fontName='Helvetica-Bold', textColor=colors.white)
    kpi_label = ParagraphStyle('KLabel', parent=small, alignment=TA_LEFT)
    kpi_value = ParagraphStyle('KValue', parent=body, fontName='Helvetica-Bold', fontSize=11.5, leading=14, textColor=AZUL)

    def ptxt(text, style=body):
        # ReportLab Paragraph supports a small HTML subset; escape user fields.
        return Paragraph(html.escape(str(text or '')).replace('\n','<br/>'), style)

    def cabecalho_rodape(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDA); canvas.setLineWidth(.5)
        canvas.line(18*mm, 13*mm, 192*mm, 13*mm)
        canvas.setFont('Helvetica', 7.5); canvas.setFillColor(colors.HexColor('#697887'))
        canvas.drawString(18*mm, 8.5*mm, 'Motor Tributário JSM - Relatório de Análise')
        canvas.drawRightString(192*mm, 8.5*mm, f'Página {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(destino, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=18*mm, title='Relatório de Análise Tributária - JSM')
    story=[]

    header = Table([[Paragraph('RELATÓRIO DE ANÁLISE TRIBUTÁRIA', titulo)], [Paragraph('Motor Tributário JSM - Simples Nacional', subtitulo)]], colWidths=[174*mm])
    header.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),AZUL),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,0),12),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    story += [header, Spacer(1, 7*mm)]

    story.append(Paragraph('1. Identificação da empresa', h2))
    ident = [
        [Paragraph('<b>Razão Social</b>', cell_b), ptxt(empresa.get('razao_social',''), cell), Paragraph('<b>CNPJ</b>', cell_b), ptxt(empresa.get('cnpj',''), cell)],
        [Paragraph('<b>Competência</b>', cell_b), ptxt(competencia, cell), Paragraph('<b>CNAE analisado</b>', cell_b), ptxt(contexto.get('cnae') or empresa.get('cnae_principal',''), cell)],
        [Paragraph('<b>Atividade</b>', cell_b), ptxt(contexto.get('descricao_cnae') or '', cell), Paragraph('<b>Regra</b>', cell_b), ptxt(resultado.get('versao_regra',''), cell)],
    ]
    t=Table(ident,colWidths=[29*mm,61*mm,27*mm,57*mm])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,BORDA),('BACKGROUND',(0,0),(0,-1),AZUL_C),('BACKGROUND',(2,0),(2,-1),AZUL_C),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),5)])); story += [t, Spacer(1,5*mm)]

    story.append(Paragraph('2. Resumo da apuração', h2))
    fator = '-' if resultado.get('fator_r') is None else f"{resultado.get('fator_r'):.2%}"
    kpis = [
        ('Anexo / Faixa', f"{resultado.get('anexo','')} / {resultado.get('faixa','')}"),
        ('RBT12', formatar_moeda(resultado.get('rbt12',0))),
        ('FS12', formatar_moeda(resultado.get('fs12',0))),
        ('Fator R', fator),
        ('Carga efetiva final', formatar_pct(resultado.get('carga_efetiva_final',0),4)),
        ('DAS estimado', formatar_moeda(resultado.get('das_mensal',0))),
    ]
    data=[]
    for r in range(2):
        row=[]
        for c in range(3):
            lab,val=kpis[r*3+c]
            row.append(Paragraph(f"<font size='7.5' color='#5B6570'>{html.escape(lab)}</font><br/><font size='11.5' color='#0B4F8A'><b>{html.escape(str(val))}</b></font>", body))
        data.append(row)
    t=Table(data,colWidths=[58*mm]*3,rowHeights=[22*mm,22*mm])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.45,BORDA),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F8FBFD')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),6)])); story += [t,Spacer(1,5*mm)]

    story.append(Paragraph('3. Dados financeiros e segregação das receitas', h2))
    story.append(Paragraph(f"Faturamento informado para a competência: <b>{formatar_moeda(resultado.get('receita_mes',0))}</b>. O sistema calculou cada natureza de receita separadamente antes de somar o DAS.", body))
    segrows=[[Paragraph('Natureza',cell_b),Paragraph('Anexo',cell_b),Paragraph('Receita',cell_b),Paragraph('Alíquota segmento',cell_b),Paragraph('DAS',cell_b),Paragraph('Exclusões aplicadas',cell_b)]]
    for s in resultado.get('segmentos',[]):
        segrows.append([
            Paragraph(f"<b>{html.escape(str(s.get('tipo','')))}</b><br/><font size='7'>{html.escape(TIPOS_RECEITA.get(s.get('tipo'),''))}</font>",cell),
            ptxt(s.get('anexo',''),cell), ptxt(formatar_moeda(s.get('valor',0)),cell),
            ptxt(formatar_pct(float(s.get('aliquota_efetiva_segmento',0))*100,4),cell),
            ptxt(formatar_moeda(s.get('das_segmento',0)),cell), ptxt(', '.join(s.get('exclusoes') or []) or 'Nenhuma',cell)
        ])
    t=Table(segrows,colWidths=[42*mm,21*mm,27*mm,29*mm,26*mm,29*mm],repeatRows=1)
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,BORDA),('BACKGROUND',(0,0),(-1,0),AZUL_C),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),4)])); story += [t,Spacer(1,4*mm)]

    story.append(Paragraph('4. Explicação completa do cálculo', h2))
    passos=[]
    for p in exp['passos']:
        passos.append([Paragraph('•',body),ptxt(p,body)])
    t=Table(passos,colWidths=[5*mm,165*mm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),CINZA),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),4),('BOX',(0,0),(-1,-1),.4,BORDA)])); story += [t,Spacer(1,3*mm)]
    calc_data=[
        [Paragraph('<b>Alíquota nominal da faixa</b>',cell),ptxt(formatar_pct(resultado.get('aliquota_nominal',0),2),cell),Paragraph('<b>Parcela a deduzir</b>',cell),ptxt(formatar_moeda(resultado.get('parcela_deduzir',0)),cell)],
        [Paragraph('<b>Alíquota efetiva base</b>',cell),ptxt(formatar_pct(resultado.get('aliquota_efetiva',0),4),cell),Paragraph('<b>Carga final após segregações</b>',cell),ptxt(formatar_pct(resultado.get('carga_efetiva_final',0),4),cell)],
        [Paragraph('<b>DAS sem tratamentos especiais</b>',cell),ptxt(formatar_moeda(resultado.get('das_sem_tratamentos',resultado.get('das_mensal',0))),cell),Paragraph('<b>Redução pelos tratamentos</b>',cell),ptxt(formatar_moeda(resultado.get('economia_tratamentos',0)),cell)],
    ]
    t=Table(calc_data,colWidths=[45*mm,40*mm,52*mm,37*mm]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,BORDA),('BACKGROUND',(0,0),(0,-1),AZUL_C),('BACKGROUND',(2,0),(2,-1),AZUL_C),('PADDING',(0,0),(-1,-1),5)])); story += [t,Spacer(1,4*mm)]

    story.append(Paragraph('5. Composição estimada do DAS e por que cada imposto foi cobrado', h2))
    tribrows=[[Paragraph('Tributo',cell_head),Paragraph('Antes',cell_head),Paragraph('Redução',cell_head),Paragraph('No DAS',cell_head),Paragraph('Explicação',cell_head)]]
    for x in exp['tributos']:
        tribrows.append([
            Paragraph(f"<b>{html.escape(x['sigla'])}</b><br/><font size='7'>{html.escape(x['nome'])}</font>",cell),
            ptxt(formatar_moeda(x['valor_sem_tratamento']),cell), ptxt(formatar_moeda(x['reducao']),cell),
            ptxt(formatar_moeda(x['valor_cobrado']),cell), ptxt(x['status']+' '+x['descricao'],cell)
        ])
    t=Table(tribrows,colWidths=[29*mm,24*mm,23*mm,24*mm,74*mm],repeatRows=1)
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,BORDA),('BACKGROUND',(0,0),(-1,0),AZUL),('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),4)])); story += [t,Spacer(1,4*mm)]

    story.append(Paragraph('6. Alertas e pontos de conferência', h2))
    alertas=resultado.get('alertas',[])
    if alertas:
        ar=[]
        for nivel,msg in alertas:
            ar.append([Paragraph(f'<b>{html.escape(str(nivel))}</b>',cell),ptxt(msg,cell)])
        t=Table(ar,colWidths=[25*mm,145*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),AMARELO),('BOX',(0,0),(-1,-1),.45,colors.HexColor('#F0D98A')),('INNERGRID',(0,0),(-1,-1),.3,colors.HexColor('#F0D98A')),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),5)])); story += [t]
    else:
        story.append(Paragraph('Nenhum alerta adicional foi gerado pelo motor para esta simulação.',body))

    story += [Spacer(1,4*mm), Paragraph('7. Memória técnica e observações', h2)]
    mem = [[ptxt(x,cell)] for x in _linhas_memoria(resultado)]
    t=Table(mem,colWidths=[170*mm]); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),CINZA),('BOX',(0,0),(-1,-1),.4,BORDA),('PADDING',(0,0),(-1,-1),4)])); story += [t,Spacer(1,3*mm)]
    story.append(Paragraph(html.escape(exp['observacao']), small))
    story.append(Paragraph(f"Documento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}. Este relatório é uma ferramenta de análise e conferência; não substitui a declaração e transmissão oficial no PGDAS-D.", small))

    doc.build(story,onFirstPage=cabecalho_rodape,onLaterPages=cabecalho_rodape)
    return destino


def gerar_relatorio_regime_pdf(regime, empresa, competencia, resultado, destino):
    """Relatório executivo genérico para Lucro Presumido e Lucro Real."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError as e:
        raise RuntimeError('Para exportar PDF, instale reportlab.') from e

    AZUL = colors.HexColor('#0B4F8A')
    BORDA = colors.HexColor('#D7DEE5')
    CLARO = colors.HexColor('#F5F8FB')
    AMARELO = colors.HexColor('#FFF7DC')
    styles = getSampleStyleSheet()
    title = ParagraphStyle('V5Title', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=19,
                           leading=23, textColor=colors.white, alignment=TA_LEFT)
    h2 = ParagraphStyle('V5H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12,
                        textColor=AZUL, spaceBefore=7, spaceAfter=6)
    body = ParagraphStyle('V5Body', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.8,
                          leading=12, textColor=colors.HexColor('#263746'))
    small = ParagraphStyle('V5Small', parent=body, fontSize=7.2, leading=9, textColor=colors.HexColor('#667788'))

    def esc(v):
        return html.escape(str(v if v is not None else ''))

    def par(v, st=body):
        return Paragraph(esc(v).replace('\n', '<br/>'), st)

    def money_rows(keys):
        rows = [[par('Tributo / item'), par('Valor')]]
        for key in keys:
            if key in resultado:
                rows.append([par(key), par(formatar_moeda(resultado.get(key, 0)))])
        return rows

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDA); canvas.line(18*mm, 13*mm, 192*mm, 13*mm)
        canvas.setFont('Helvetica', 7); canvas.setFillColor(colors.HexColor('#6A7886'))
        canvas.drawString(18*mm, 8.5*mm, 'Motor Tributário JSM — relatório interno de apoio')
        canvas.drawRightString(192*mm, 8.5*mm, f'Página {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(destino, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=16*mm, bottomMargin=18*mm, title=f'Relatório {regime} - JSM')
    story = []
    header = Table([[Paragraph(f'RELATÓRIO — {esc(regime).upper()}', title)],
                    [Paragraph('Motor Tributário JSM — V5.0', small)]], colWidths=[174*mm])
    header.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),AZUL),('LEFTPADDING',(0,0),(-1,-1),12),
                                ('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,0),11),
                                ('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story += [header, Spacer(1, 6*mm)]

    story.append(Paragraph('1. Identificação', h2))
    ident = [
        [par('Empresa'), par(empresa.get('razao_social',''))],
        [par('CNPJ'), par(empresa.get('cnpj',''))],
        [par('Competência / período'), par(competencia)],
        [par('Versão da regra'), par(resultado.get('versao_regra',''))],
    ]
    t=Table(ident,colWidths=[42*mm,132*mm]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,BORDA),
        ('BACKGROUND',(0,0),(0,-1),CLARO),('PADDING',(0,0),(-1,-1),5)])); story += [t, Spacer(1,4*mm)]

    story.append(Paragraph('2. Resumo tributário', h2))
    if regime == 'Lucro Presumido':
        keys = ['IRPJ','Adicional IRPJ','CSLL','PIS/Pasep','COFINS','ISS estimado','ICMS estimado','CPP estimada']
        total = resultado.get('total_trimestre',0); carga = resultado.get('carga_efetiva',0)
        resumo = [
            ['Receita operacional', formatar_moeda(resultado.get('receita_trimestre',0))],
            ['Base IRPJ', formatar_moeda(resultado.get('base_irpj',0))],
            ['Base CSLL', formatar_moeda(resultado.get('base_csll',0))],
            ['Total estimado', formatar_moeda(total)], ['Carga efetiva', formatar_pct(carga)],
        ]
    else:
        keys = ['IRPJ','Adicional IRPJ','CSLL','PIS/Pasep','COFINS','ICMS estimado','ISS estimado','CPP estimada']
        total = resultado.get('total_periodo',0); carga = resultado.get('carga_efetiva',0)
        resumo = [
            ['Receita do período', formatar_moeda(resultado.get('receita_periodo',0))],
            ['Lucro contábil', formatar_moeda(resultado.get('lucro_contabil',0))],
            ['Base IRPJ', formatar_moeda(resultado.get('base_irpj',0))],
            ['Base CSLL', formatar_moeda(resultado.get('base_csll',0))],
            ['Total estimado', formatar_moeda(total)], ['Carga efetiva', formatar_pct(carga)],
        ]
    rt=Table([[par(a),par(b)] for a,b in resumo],colWidths=[55*mm,119*mm]); rt.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),.35,BORDA),('BACKGROUND',(0,0),(0,-1),CLARO),('PADDING',(0,0),(-1,-1),5)])); story += [rt,Spacer(1,4*mm)]

    story.append(Paragraph('3. Composição', h2))
    tr = Table(money_rows(keys), colWidths=[95*mm,79*mm], repeatRows=1)
    tr.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,BORDA),('BACKGROUND',(0,0),(-1,0),AZUL),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('PADDING',(0,0),(-1,-1),5)])); story += [tr,Spacer(1,4*mm)]

    memoria = resultado.get('memoria') or {}
    story.append(Paragraph('4. Memória de cálculo', h2))
    mem_rows=[]
    for k,v in memoria.items():
        if isinstance(v, (dict,list)):
            try: v = json.dumps(v, ensure_ascii=False, indent=2)
            except Exception: v = str(v)
        mem_rows.append([par(k), par(v)])
    if mem_rows:
        tm=Table(mem_rows,colWidths=[52*mm,122*mm]); tm.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.3,BORDA),
            ('BACKGROUND',(0,0),(0,-1),CLARO),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),4)])); story += [tm]
    else:
        story.append(par('Memória detalhada não disponível para este registro.'))

    story.append(Paragraph('5. Alertas e validações', h2))
    alertas = resultado.get('alertas') or []
    if alertas:
        ta=Table([[par('ATENÇÃO'),par(a[1] if isinstance(a,(list,tuple)) and len(a)>1 else a)] for a in alertas],
                 colWidths=[25*mm,149*mm]); ta.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),AMARELO),
            ('GRID',(0,0),(-1,-1),.3,colors.HexColor('#E6D58C')),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),5)])); story += [ta]
    else:
        story.append(par('Nenhum alerta adicional registrado.'))

    story += [Spacer(1,4*mm), Paragraph(
        'Relatório de apoio interno. Não substitui ECF, EFD-Contribuições, PGDAS-D, escrituração contábil/fiscal, '
        'apuração estadual/municipal ou validação do profissional responsável.', small)]
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return destino
