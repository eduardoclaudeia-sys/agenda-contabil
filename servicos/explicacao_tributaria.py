TRIBUTOS = {
    'IRPJ': (
        'Imposto de Renda da Pessoa Jurídica',
        'Tributo federal calculado dentro da alíquota do Simples Nacional conforme o Anexo e a faixa aplicáveis.'
    ),
    'CSLL': (
        'Contribuição Social sobre o Lucro Líquido',
        'Contribuição federal incluída na repartição da alíquota do Simples Nacional conforme o Anexo e a faixa.'
    ),
    'PIS/Pasep': (
        'Contribuição para o PIS/Pasep',
        'Contribuição federal incidente sobre a receita dentro do Simples. Em receitas corretamente classificadas como monofásicas ou em determinadas exportações, sua parcela pode ser desconsiderada no DAS.'
    ),
    'COFINS': (
        'Contribuição para o Financiamento da Seguridade Social',
        'Contribuição federal incidente sobre a receita dentro do Simples. Em receitas corretamente classificadas como monofásicas ou em determinadas exportações, sua parcela pode ser desconsiderada no DAS.'
    ),
    'CPP': (
        'Contribuição Patronal Previdenciária',
        'Parcela previdenciária incluída no DAS para os Anexos em que a CPP integra o Simples. No Anexo IV, a contribuição patronal previdenciária não integra o DAS e exige tratamento separado.'
    ),
    'ICMS': (
        'Imposto sobre Circulação de Mercadorias e Serviços',
        'Tributo estadual normalmente presente nas atividades dos Anexos I e II. A parcela pode ser desconsiderada no DAS em receitas com ICMS-ST ou em hipóteses de exportação parametrizadas.'
    ),
    'ISS': (
        'Imposto sobre Serviços',
        'Tributo municipal normalmente presente nos Anexos de serviços. A parcela pode ser desconsiderada quando o ISS estiver retido ou em outras hipóteses parametrizadas.'
    ),
    'IPI': (
        'Imposto sobre Produtos Industrializados',
        'Tributo federal aplicável às receitas industriais do Anexo II, conforme a repartição da faixa. Pode receber tratamento específico em exportações.'
    ),
}

TIPOS_RECEITA = {
    'normal': 'Receita sem tratamento especial informado.',
    'mercado_interno': 'Receita de mercado interno sem tratamento especial informado.',
    'monofasico': 'Receita informada como sujeita à tributação monofásica de PIS/Cofins.',
    'icms_st': 'Receita informada como sujeita a ICMS por substituição tributária.',
    'substituicao_tributaria': 'Receita informada como sujeita a ICMS por substituição tributária.',
    'monofasico_icms_st': 'Receita com tratamento combinado de PIS/Cofins monofásico e ICMS-ST.',
    'monofasico_st': 'Receita com tratamento combinado de PIS/Cofins monofásico e ICMS-ST.',
    'iss_retido': 'Receita de serviço com ISS informado como retido.',
    'exportacao': 'Receita de exportação, com exclusões parametrizadas conforme o tipo de atividade.',
    'locacao_sem_iss': 'Receita de locação tratada sem ISS nesta simulação.',
}


def explicar_resultado(resultado):
    """Retorna explicações em linguagem clara para UI e relatório.

    Não substitui a memória numérica do motor; traduz os critérios usados pelo
    cálculo para que o usuário consiga conferir por que cada parcela entrou ou saiu.
    """
    memoria = resultado.get('memoria', {})
    segmentos = resultado.get('segmentos', [])
    tributos = resultado.get('tributos', {})
    baseline = resultado.get('tributos_sem_tratamentos', {})
    reducoes = resultado.get('reducoes_por_tratamento', {})

    def moeda(v):
        return f'R$ {float(v or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X','.')

    passos = []
    passos.append(
        f"O RBT12 usado para localizar a faixa foi de {moeda(memoria.get('rbt12', 0))}. "
        f"Com isso, o cálculo enquadrou a empresa na faixa {memoria.get('faixa', '')} do {memoria.get('anexo_aplicado', '')}."
    )
    passos.append(
        "A alíquota efetiva base foi calculada pela fórmula: "
        "((RBT12 x alíquota nominal) - parcela a deduzir) / RBT12."
    )
    if memoria.get('fator_r') is not None:
        passos.append(
            f"O Fator R considerado foi de {float(memoria['fator_r']):.2%}. "
            f"O Anexo aplicado após essa análise foi {memoria.get('anexo_aplicado', '')}."
        )
    passos.append(
        "O faturamento do mês foi dividido pelas naturezas de receita informadas. "
        "Cada parcela recebeu as exclusões tributárias correspondentes antes da soma do DAS."
    )
    passos.append(
        f"A soma final das parcelas resultou em DAS estimado de {moeda(resultado.get('das_mensal', 0))}, "
        f"equivalente a uma carga efetiva final de {resultado.get('carga_efetiva_final', 0):.4f}% sobre a receita do mês."
    )

    explicacoes_tributos = []
    todas_chaves = list(dict.fromkeys(list(baseline.keys()) + list(tributos.keys())))
    for trib in todas_chaves:
        nome, descricao = TRIBUTOS.get(trib, (trib, 'Parcela prevista na repartição parametrizada do Simples Nacional.'))
        antes = float(baseline.get(trib, 0) or 0)
        depois = float(tributos.get(trib, 0) or 0)
        reducao = float(reducoes.get(trib, 0) or 0)
        if antes <= 0 and depois <= 0:
            status = 'Não integra a repartição usada nesta apuração.'
        elif reducao > 0.005 and depois <= 0.005:
            status = f'A parcela seria {moeda(antes)}, mas foi integralmente retirada pelos tratamentos informados.'
        elif reducao > 0.005:
            status = f'A parcela foi reduzida em {moeda(reducao)}; valor mantido no DAS: {moeda(depois)}.'
        else:
            status = f'Valor mantido no DAS: {moeda(depois)}.'
        explicacoes_tributos.append({
            'sigla': trib, 'nome': nome, 'descricao': descricao,
            'valor_sem_tratamento': antes, 'reducao': reducao,
            'valor_cobrado': depois, 'status': status,
        })

    explicacoes_segmentos = []
    for seg in segmentos:
        tipo = seg.get('tipo', 'normal')
        exclusoes = seg.get('exclusoes', []) or []
        if exclusoes:
            efeito = 'Parcelas desconsideradas neste segmento: ' + ', '.join(exclusoes) + '.'
        else:
            efeito = 'Nenhuma parcela tributária foi retirada por tratamento especial neste segmento.'
        explicacoes_segmentos.append({
            'tipo': tipo,
            'descricao': TIPOS_RECEITA.get(tipo, tipo),
            'valor': seg.get('valor', 0),
            'anexo': seg.get('anexo', ''),
            'das_segmento': seg.get('das_segmento', 0),
            'efeito': efeito,
        })

    return {
        'passos': passos,
        'tributos': explicacoes_tributos,
        'segmentos': explicacoes_segmentos,
        'observacao': (
            'A simulação depende da classificação correta das receitas e do enquadramento da atividade. '
            'O resultado deve ser conferido com os documentos fiscais e com o PGDAS-D antes da transmissão.'
        )
    }
