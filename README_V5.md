# Motor Tributário JSM Web — V5.0

## O que mudou

A V5 consolida as auditorias realizadas sobre a V4 sem reescrever o núcleo validado do Simples Nacional.

- Arquitetura Flask por Blueprints (auth, dashboard, empresas, Simples, Presumido, Real, comparador, histórico e usuários).
- PostgreSQL/Supabase obrigatório em produção; `SECRET_KEY` obrigatória no Render.
- CSRF, hash de senha, rate limiting, sessão com expiração, headers de segurança e papéis admin/operador.
- Cadastro manual com validação real de CNPJ, importação de PDF e consulta externa opcional de CNPJ.
- Simples: regras versionadas, RBT12/FS12/Fator R, múltiplas segregações, monofásico, ST, ISS retido, exportação, sublimite controlado e memória.
- Lucro Presumido: atividades mistas, receitas financeiras/ganhos de capital separados, regra 2026 versionada e PDF.
- Lucro Real: Beta gerencial a partir do lucro contábil, ajustes agregados/detalhados, trava de compensação parametrizada, créditos detalhados e PDF.
- Comparador triplo com indicador de qualidade; nunca emite ordem de enquadramento.
- Fechamento de competência, auditoria por usuário/IP, histórico e exportação CSV.
- Importador seguro de XML NF-e com indícios de ST/monofásico explicitamente não conclusivos.
- Botões de explicação em praticamente todo o fluxo, centralizados em `servicos/explanations.py`.
- Metadados/checksum das regras versionadas registrados no banco.
- Índices aditivos/idempotentes nas consultas principais, sem apagar tabelas existentes.
- Camada `competencias_v5` para consolidação por empresa/mês sem destruir tabelas históricas da V4.

## Atualização no Render/Supabase

Use o MESMO repositório, serviço Render e banco Supabase da V4.

1. Faça backup do banco antes do primeiro deploy da V5.
2. Substitua os arquivos do repositório pelos arquivos deste pacote.
3. Confirme no Render as variáveis `DATABASE_URL`, `SECRET_KEY` e `SETUP_TOKEN`.
4. Faça o deploy. `db.create_all()` cria somente as tabelas novas que faltarem; não apaga as existentes.
5. Teste primeiro com uma empresa/cenário conhecido e compare com a V4/PGDAS/controles do escritório.

## Segurança

Nunca coloque `.env`, senha do Supabase, `DATABASE_URL`, `SECRET_KEY` ou `SETUP_TOKEN` no GitHub.

## Escopo responsável

O sistema é ferramenta de apoio. Não transmite PGDAS-D, ECF, EFD-Contribuições, SPED ou NF-e e não substitui validação profissional.

A importação integral/automática de SPED e PGDAS-D não foi ativada como automatismo fiscal na V5 porque uma implementação parcial poderia gerar falsa segurança. O V5 deixa a arquitetura preparada para conectores futuros, mas mantém cálculo fiscal explícito e auditável.
