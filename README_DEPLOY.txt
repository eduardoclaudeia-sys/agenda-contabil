MOTOR TRIBUTÁRIO JSM WEB V5.0 — ATUALIZAÇÃO

Use o mesmo GitHub, Render e Supabase da versão atual.

1) Faça backup do banco.
2) Envie o CONTEÚDO desta pasta para a raiz do repositório privado, substituindo a versão anterior.
3) Render:
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
4) Environment obrigatória em produção:
   DATABASE_URL = URI Session Pooler do Supabase
   SECRET_KEY = segredo forte e exclusivo
   SETUP_TOKEN = necessário somente se ainda não existe usuário inicial
5) Deploy.
6) Abra /health e confirme status ok / versão 5.0.
7) Faça teste de regressão com caso conhecido antes de usar em produção fiscal.

NÃO ENVIE CREDENCIAIS AO GITHUB.
