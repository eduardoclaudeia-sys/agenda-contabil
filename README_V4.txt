MOTOR TRIBUTÁRIO JSM — V4 WEB
==============================

CORREÇÃO DE CONCEITO
--------------------
A V3 Web colocou a Gestão/Cadastro no centro da experiência e deixou o motor
tributário escondido. A V4 restaura o conceito da aplicação desktop original:

INÍCIO DO MOTOR
  -> SIMPLES NACIONAL
  -> LUCRO PRESUMIDO
  -> LUCRO REAL (BETA GERENCIAL)
  -> GESTÃO TRIBUTÁRIA como módulo de apoio

SIMPLES NACIONAL
----------------
Reutiliza o motor validado da V2.1:
- Anexos I a V
- RBT12
- FS12
- Fator R
- segregações
- monofásico
- ICMS-ST
- monofásico + ST
- ISS retido
- exportação
- locação sem ISS
- composição estimada do DAS
- alertas
- histórico por empresa

LUCRO PRESUMIDO
---------------
Agora possui tela própria.
Foi adicionada uma função de simulação 2026 sem alterar a API antiga testada.
A simulação considera, para uma atividade por cálculo:
- IRPJ
- adicional de IRPJ
- CSLL
- PIS/Cofins cumulativos
- ISS parametrizável
- ICMS parametrizável
- CPP parametrizável
- regra 2026 de acréscimo de 10% nos percentuais de presunção sobre a parcela
  trimestral que excede R$ 1.250.000;
- para CSLL em 2026, o acréscimo é considerado a partir do 2º trimestre.

Empresas com múltiplas atividades devem aplicar a proporcionalização exigida
pela regra e validar o cenário profissionalmente.

LUCRO REAL
----------
A V2.1 ORIGINAL NÃO TINHA MOTOR AUTOMATIZADO DE LUCRO REAL.
O botão existia, mas o módulo estava marcado como "em desenvolvimento".

A V4 cria um PRIMEIRO SIMULADOR GERENCIAL BETA com:
- lucro contábil;
- adições e exclusões informadas;
- compensação de prejuízo fiscal limitada, em regra, a 30% do lucro ajustado;
- IRPJ 15%;
- adicional IRPJ 10% sobre a parcela acima de R$ 20.000 por mês do período;
- CSLL padrão de 9% para PJ em geral;
- PIS 1,65% e Cofins 7,6% no cenário não cumulativo padrão;
- créditos de PIS/Cofins INFORMADOS PELO USUÁRIO;
- ICMS/ISS/CPP como valores parametrizados.

O módulo NÃO decide automaticamente:
- adições/exclusões permitidas;
- créditos de PIS/Cofins;
- regimes monofásicos/especiais;
- incentivos;
- JCP;
- subvenções;
- preços de transferência;
- particularidades de instituições financeiras;
- benefícios estaduais/municipais.

FONTES OFICIAIS CONSULTADAS PARA A V4
-------------------------------------
Receita Federal — IRPJ:
- alíquota de 15%;
- adicional de 10% sobre parcela que exceder R$ 20.000 por mês do período.

Receita Federal — PIS/Cofins não cumulativos:
- regra geral 1,65% e 7,6%, ressalvadas disposições específicas.

PGFN / Receita Federal — prejuízos fiscais:
- regra geral de limitação de compensação a 30% do lucro líquido ajustado.

Receita Federal — Perguntas e Respostas sobre LC 224/2025, atualizada em
30/04/2026:
- lucro presumido: acréscimo de 10% nos percentuais de presunção na parcela
  da receita bruta acima de R$ 5 milhões/ano, proporcionalmente R$ 1,25 milhão
  por trimestre;
- IRPJ desde 1º trimestre/2026;
- CSLL a partir do 2º trimestre/2026.

VALIDAÇÃO
---------
- 34 testes originais da V2.1 devem continuar aprovados.
- A V4 adiciona testes próprios para Lucro Real e Presumido 2026.

PUBLICAÇÃO
----------
Use o MESMO Supabase e o MESMO serviço Render já criado para o Sistema Tributário.
Não crie outro banco.

Para atualizar:
1. substitua os arquivos do repositório GitHub pela V4;
2. faça Commit;
3. o Render fará novo deploy automaticamente.

O db.create_all() criará apenas a nova tabela "calculos_regime".
As tabelas existentes permanecem.

IMPORTANTE
----------
Ferramenta de apoio interno. Não substitui escrituração, ECF, EFD-Contribuições,
PGDAS-D, legislação específica nem validação do profissional responsável.
