import os
import sqlite3
import shutil
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, 'dados_db')
DB_PATH = os.path.join(DB_DIR, 'motor_tributario.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')


def _connect():
    os.makedirs(DB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


@contextmanager
def conexao():
    con = _connect()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def inicializar_banco():
    with conexao() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razao_social TEXT NOT NULL,
            nome_fantasia TEXT,
            cnpj TEXT UNIQUE,
            data_abertura TEXT,
            inicio_atividade TEXT,
            cnae_principal TEXT,
            cnaes_secundarios TEXT,
            regime_atual TEXT DEFAULT 'Simples Nacional',
            uf TEXT,
            municipio TEXT,
            inscricao_estadual TEXT,
            inscricao_municipal TEXT,
            situacao_cadastral TEXT,
            porte TEXT,
            natureza_juridica TEXT,
            logradouro TEXT,
            numero TEXT,
            complemento TEXT,
            cep TEXT,
            bairro TEXT,
            data_situacao TEXT,
            origem_cadastro TEXT,
            observacoes TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS faturamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            competencia TEXT NOT NULL,
            receita_interna REAL NOT NULL DEFAULT 0,
            receita_externa REAL NOT NULL DEFAULT 0,
            observacoes TEXT,
            UNIQUE(empresa_id, competencia),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS folhas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            competencia TEXT NOT NULL,
            salarios REAL NOT NULL DEFAULT 0,
            pro_labore REAL NOT NULL DEFAULT 0,
            encargos REAL NOT NULL DEFAULT 0,
            outros_fs12 REAL NOT NULL DEFAULT 0,
            observacoes TEXT,
            UNIQUE(empresa_id, competencia),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS apuracoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            competencia TEXT NOT NULL,
            anexo TEXT NOT NULL,
            rbt12 REAL NOT NULL,
            fs12 REAL NOT NULL DEFAULT 0,
            fator_r REAL,
            receita_mes REAL NOT NULL,
            das_total REAL NOT NULL,
            aliquota_efetiva REAL NOT NULL,
            faixa INTEGER,
            memoria_json TEXT,
            versao_regra TEXT,
            criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(empresa_id, competencia),
            FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS segregacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apuracao_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            valor REAL NOT NULL,
            anexo TEXT,
            cnae TEXT,
            observacoes TEXT,
            FOREIGN KEY (apuracao_id) REFERENCES apuracoes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER,
            data_hora TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            acao TEXT NOT NULL,
            detalhe TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE SET NULL
        );
        ''')
        # Migrações leves para bases criadas por versões anteriores.
        cols = {r[1] for r in con.execute('PRAGMA table_info(segregacoes)').fetchall()}
        if 'cnae' not in cols:
            con.execute('ALTER TABLE segregacoes ADD COLUMN cnae TEXT')

        cols_emp = {r[1] for r in con.execute('PRAGMA table_info(empresas)').fetchall()}
        novos_campos = {
            'porte': 'TEXT',
            'natureza_juridica': 'TEXT',
            'logradouro': 'TEXT',
            'numero': 'TEXT',
            'complemento': 'TEXT',
            'cep': 'TEXT',
            'bairro': 'TEXT',
            'data_situacao': 'TEXT',
            'origem_cadastro': 'TEXT',
        }
        for campo, tipo in novos_campos.items():
            if campo not in cols_emp:
                con.execute(f'ALTER TABLE empresas ADD COLUMN {campo} {tipo}')


def registrar_auditoria(empresa_id, acao, detalhe=''):
    with conexao() as con:
        con.execute(
            'INSERT INTO auditoria (empresa_id, acao, detalhe) VALUES (?, ?, ?)',
            (empresa_id, acao, detalhe)
        )


def listar_empresas(filtro=''):
    with conexao() as con:
        if filtro:
            cur = con.execute(
                '''SELECT * FROM empresas WHERE razao_social LIKE ? OR nome_fantasia LIKE ? OR cnpj LIKE ?
                   ORDER BY razao_social''',
                (f'%{filtro}%', f'%{filtro}%', f'%{filtro}%')
            )
        else:
            cur = con.execute('SELECT * FROM empresas ORDER BY razao_social')
        return [dict(r) for r in cur.fetchall()]


def obter_empresa(empresa_id):
    with conexao() as con:
        row = con.execute('SELECT * FROM empresas WHERE id=?', (empresa_id,)).fetchone()
        return dict(row) if row else None


def _somente_numeros(valor):
    return ''.join(c for c in str(valor or '') if c.isdigit())


def buscar_empresa_por_cnpj(cnpj):
    numeros = _somente_numeros(cnpj)
    if not numeros:
        return None
    with conexao() as con:
        row = con.execute(
            """SELECT * FROM empresas
               WHERE REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(cnpj,''),'.',''),'/',''),'-',''),' ','') = ?
               LIMIT 1""",
            (numeros,)
        ).fetchone()
        return dict(row) if row else None


def salvar_empresa(dados, empresa_id=None):
    campos = [
        'razao_social','nome_fantasia','cnpj','data_abertura','inicio_atividade',
        'cnae_principal','cnaes_secundarios','regime_atual','uf','municipio',
        'inscricao_estadual','inscricao_municipal','situacao_cadastral','porte',
        'natureza_juridica','logradouro','numero','complemento','cep','bairro',
        'data_situacao','origem_cadastro','observacoes'
    ]
    dados = dict(dados or {})
    if dados.get('cnpj'):
        dados['cnpj'] = _somente_numeros(dados['cnpj'])
    valores = [dados.get(c) for c in campos]
    with conexao() as con:
        if empresa_id:
            sets = ', '.join(f'{c}=?' for c in campos)
            con.execute(
                f'UPDATE empresas SET {sets}, atualizado_em=CURRENT_TIMESTAMP WHERE id=?',
                valores + [empresa_id]
            )
            eid = empresa_id
        else:
            existente = buscar_empresa_por_cnpj(dados.get('cnpj')) if dados.get('cnpj') else None
            if existente:
                return salvar_empresa(dados, existente['id'])
            placeholders = ','.join('?' for _ in campos)
            con.execute(
                f"INSERT INTO empresas ({','.join(campos)}) VALUES ({placeholders})",
                valores
            )
            eid = con.execute('SELECT last_insert_rowid()').fetchone()[0]
    registrar_auditoria(eid, 'empresa_salva', dados.get('razao_social',''))
    return eid


def salvar_empresa_por_pdf(dados_pdf):
    """Cadastra ou atualiza automaticamente uma empresa a partir do PDF do CNPJ.

    O CNPJ é a chave de reconciliação. Campos cadastrais extraídos substituem os
    valores antigos somente quando vierem preenchidos; campos internos do escritório
    (inscrições, observações etc.) são preservados.
    """
    dados_pdf = dict(dados_pdf or {})
    cnpj = dados_pdf.get('cnpj')
    if not cnpj:
        raise ValueError('Não é possível cadastrar empresa sem CNPJ válido.')
    atual = buscar_empresa_por_cnpj(cnpj) or {}

    secund = dados_pdf.get('cnaes_secundarios') or ''
    if isinstance(secund, (list, tuple)):
        secund = '; '.join(str(x) for x in secund if str(x).strip())

    mapa = {
        'razao_social': dados_pdf.get('razao_social'),
        'nome_fantasia': dados_pdf.get('nome_fantasia'),
        'cnpj': cnpj,
        'data_abertura': dados_pdf.get('data_abertura'),
        'inicio_atividade': dados_pdf.get('data_abertura'),
        'cnae_principal': dados_pdf.get('cnae_principal'),
        'cnaes_secundarios': secund,
        'regime_atual': atual.get('regime_atual') or 'Simples Nacional',
        'uf': dados_pdf.get('uf'),
        'municipio': dados_pdf.get('municipio'),
        'situacao_cadastral': dados_pdf.get('situacao'),
        'porte': dados_pdf.get('porte'),
        'natureza_juridica': dados_pdf.get('natureza_juridica'),
        'logradouro': dados_pdf.get('logradouro'),
        'numero': dados_pdf.get('numero'),
        'complemento': dados_pdf.get('complemento'),
        'cep': dados_pdf.get('cep'),
        'bairro': dados_pdf.get('bairro'),
        'data_situacao': dados_pdf.get('data_situacao'),
        'origem_cadastro': 'PDF CNPJ',
    }
    # Preservar dados internos que o comprovante de CNPJ não traz.
    for campo in ('inscricao_estadual','inscricao_municipal','observacoes'):
        mapa[campo] = atual.get(campo)
    # Não apagar um dado já corrigido manualmente quando a extração vier vazia.
    for campo, valor in list(mapa.items()):
        if (valor is None or str(valor).strip() == '') and atual.get(campo) not in (None, ''):
            mapa[campo] = atual.get(campo)

    eid = salvar_empresa(mapa, atual.get('id'))
    registrar_auditoria(eid, 'cadastro_pdf', 'Cadastro/atualização automática a partir do comprovante de CNPJ.')
    return eid


def excluir_empresa(empresa_id):
    emp = obter_empresa(empresa_id)
    with conexao() as con:
        con.execute('DELETE FROM empresas WHERE id=?', (empresa_id,))
    registrar_auditoria(None, 'empresa_excluida', (emp or {}).get('razao_social',''))


def salvar_faturamento(empresa_id, competencia, receita_interna, receita_externa=0, observacoes=''):
    if receita_interna < 0 or receita_externa < 0:
        raise ValueError('Receitas não podem ser negativas.')
    with conexao() as con:
        con.execute('''
            INSERT INTO faturamentos (empresa_id, competencia, receita_interna, receita_externa, observacoes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(empresa_id, competencia) DO UPDATE SET
              receita_interna=excluded.receita_interna,
              receita_externa=excluded.receita_externa,
              observacoes=excluded.observacoes
        ''', (empresa_id, competencia, receita_interna, receita_externa, observacoes))
    registrar_auditoria(empresa_id, 'faturamento_salvo', f'{competencia}: {receita_interna + receita_externa:.2f}')


def salvar_folha(empresa_id, competencia, salarios=0, pro_labore=0, encargos=0, outros_fs12=0, observacoes=''):
    vals = [salarios, pro_labore, encargos, outros_fs12]
    if any(v < 0 for v in vals):
        raise ValueError('Valores da folha não podem ser negativos.')
    with conexao() as con:
        con.execute('''
            INSERT INTO folhas (empresa_id, competencia, salarios, pro_labore, encargos, outros_fs12, observacoes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(empresa_id, competencia) DO UPDATE SET
              salarios=excluded.salarios,
              pro_labore=excluded.pro_labore,
              encargos=excluded.encargos,
              outros_fs12=excluded.outros_fs12,
              observacoes=excluded.observacoes
        ''', (empresa_id, competencia, salarios, pro_labore, encargos, outros_fs12, observacoes))
    registrar_auditoria(empresa_id, 'folha_salva', f'{competencia}: {sum(vals):.2f}')


def historico_faturamento(empresa_id):
    with conexao() as con:
        rows = con.execute('SELECT * FROM faturamentos WHERE empresa_id=? ORDER BY competencia', (empresa_id,)).fetchall()
        return [dict(r) for r in rows]


def historico_folha(empresa_id):
    with conexao() as con:
        rows = con.execute('SELECT * FROM folhas WHERE empresa_id=? ORDER BY competencia', (empresa_id,)).fetchall()
        return [dict(r) for r in rows]


def historico_apuracoes(empresa_id):
    with conexao() as con:
        rows = con.execute('SELECT * FROM apuracoes WHERE empresa_id=? ORDER BY competencia DESC', (empresa_id,)).fetchall()
        return [dict(r) for r in rows]


def salvar_apuracao(empresa_id, competencia, resultado, segregacoes=None):
    import json
    memoria = resultado.get('memoria', {})
    with conexao() as con:
        con.execute('''
            INSERT INTO apuracoes
            (empresa_id, competencia, anexo, rbt12, fs12, fator_r, receita_mes, das_total,
             aliquota_efetiva, faixa, memoria_json, versao_regra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(empresa_id, competencia) DO UPDATE SET
              anexo=excluded.anexo, rbt12=excluded.rbt12, fs12=excluded.fs12,
              fator_r=excluded.fator_r, receita_mes=excluded.receita_mes,
              das_total=excluded.das_total, aliquota_efetiva=excluded.aliquota_efetiva,
              faixa=excluded.faixa, memoria_json=excluded.memoria_json,
              versao_regra=excluded.versao_regra, criado_em=CURRENT_TIMESTAMP
        ''', (
            empresa_id, competencia, resultado['anexo'], resultado['rbt12'], resultado.get('fs12',0),
            resultado.get('fator_r'), resultado['receita_mes'], resultado['das_mensal'],
            resultado['aliquota_efetiva'], resultado['faixa'], json.dumps(memoria, ensure_ascii=False),
            resultado.get('versao_regra','2026.08')
        ))
        aid = con.execute('SELECT id FROM apuracoes WHERE empresa_id=? AND competencia=?', (empresa_id, competencia)).fetchone()[0]
        con.execute('DELETE FROM segregacoes WHERE apuracao_id=?', (aid,))
        for seg in (segregacoes or []):
            con.execute('INSERT INTO segregacoes (apuracao_id, tipo, valor, anexo, cnae, observacoes) VALUES (?,?,?,?,?,?)',
                        (aid, seg.get('tipo'), seg.get('valor',0), seg.get('anexo'), seg.get('cnae'), seg.get('observacoes','')))
    registrar_auditoria(empresa_id, 'apuracao_salva', f'{competencia}: DAS {resultado["das_mensal"]:.2f}')
    return aid


def criar_backup(destino=None):
    inicializar_banco()
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if destino is None:
        carimbo = datetime.now().strftime('%Y%m%d_%H%M%S')
        destino = os.path.join(BACKUP_DIR, f'motor_tributario_{carimbo}.db')
    shutil.copy2(DB_PATH, destino)
    return destino


def restaurar_backup(origem):
    if not os.path.exists(origem):
        raise FileNotFoundError(origem)
    os.makedirs(DB_DIR, exist_ok=True)
    shutil.copy2(origem, DB_PATH)
    inicializar_banco()
    return DB_PATH


inicializar_banco()


def listar_auditoria(empresa_id=None, limite=300):
    with conexao() as con:
        if empresa_id:
            rows=con.execute('SELECT * FROM auditoria WHERE empresa_id=? ORDER BY id DESC LIMIT ?', (empresa_id,limite)).fetchall()
        else:
            rows=con.execute('SELECT * FROM auditoria ORDER BY id DESC LIMIT ?', (limite,)).fetchall()
        return [dict(r) for r in rows]

def obter_apuracao(apuracao_id):
    with conexao() as con:
        r=con.execute('SELECT * FROM apuracoes WHERE id=?',(apuracao_id,)).fetchone()
        if not r:return None
        out=dict(r); out['segregacoes']=[dict(x) for x in con.execute('SELECT * FROM segregacoes WHERE apuracao_id=?',(apuracao_id,)).fetchall()]
        return out
