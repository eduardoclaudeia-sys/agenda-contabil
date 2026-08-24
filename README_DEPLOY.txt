AGENDA CONTÁBIL ONLINE - V0.2
=============================

ARQUITETURA
-----------
Frontend: HTML + CSS
Backend: Python + Flask
Banco online: PostgreSQL no Supabase
Hospedagem: Render
Login: usuário + senha
Segurança de formulários: CSRF
Senha do usuário: armazenada com hash
Senha de certificado digital: NÃO armazenar. O campo é apenas "Referência de senha".

1) CRIAR O BANCO NO SUPABASE
----------------------------
- Crie uma conta/projeto no Supabase.
- No projeto, clique em "Connect".
- Para um backend persistente hospedado em ambiente IPv4, prefira a
  string do "Session pooler" (porta 5432).
- Copie a connection string completa.
- Troque [YOUR-PASSWORD] pela senha real do banco.
- Guarde essa string: ela será usada como DATABASE_URL no Render.

2) COLOCAR O PROJETO NO GITHUB
------------------------------
- Crie um repositório novo no GitHub.
- Envie TODOS os arquivos desta pasta para a raiz do repositório.
- Não envie arquivos .env nem senhas.

3) PUBLICAR NO RENDER
---------------------
- No Render: New > Web Service.
- Conecte o repositório do GitHub.
- O arquivo render.yaml já contém:
  Build command: pip install -r requirements.txt
  Start command: gunicorn app:app
- Escolha o plano Free.

4) VARIÁVEIS DE AMBIENTE NO RENDER
----------------------------------
Defina:
DATABASE_URL = string de conexão do Supabase (Session pooler)
SETUP_TOKEN  = um código secreto criado por você, por exemplo:
               um código aleatório forte que só você conheça.

SECRET_KEY é configurada automaticamente pelo render.yaml.

5) PRIMEIRO ACESSO
------------------
- Abra a URL fornecida pelo Render.
- Como ainda não existe usuário, o sistema enviará você para /setup.
- Digite:
  Código de primeiro acesso = valor do SETUP_TOKEN
  Nome
  Usuário
  Senha
- Após criar o administrador, /setup deixa de aceitar novos cadastros.

6) IMPORTANTE SOBRE CERTIFICADOS DIGITAIS
-----------------------------------------
NÃO grave a senha real de certificados digitais neste sistema.
O campo "Referência de senha" deve conter apenas algo como:
"senha no cofre físico", "consultar gerência", "padrão interno A".
Nunca a senha secreta em si.

7) TESTE LOCAL OPCIONAL
-----------------------
Se executar sem DATABASE_URL, o sistema cria SQLite local apenas para teste.
Para produção, use obrigatoriamente o PostgreSQL do Supabase.

By Eduardo de Paiva
