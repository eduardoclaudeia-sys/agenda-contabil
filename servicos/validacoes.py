import re
from datetime import datetime


def somente_digitos(v):
    return re.sub(r'\D','',str(v or ''))


def validar_cnpj(cnpj):
    n=somente_digitos(cnpj)
    if len(n)!=14 or n==n[0]*14: return False
    def digito(base,pesos):
        s=sum(int(a)*b for a,b in zip(base,pesos)); r=s%11
        return '0' if r<2 else str(11-r)
    d1=digito(n[:12],[5,4,3,2,9,8,7,6,5,4,3,2])
    d2=digito(n[:12]+d1,[6,5,4,3,2,9,8,7,6,5,4,3,2])
    return n[-2:]==d1+d2


def validar_competencia(comp):
    try:
        s=str(comp).strip()
        if '/' in s: datetime.strptime(s,'%m/%Y')
        else: datetime.strptime(s,'%Y-%m')
        return True
    except Exception:
        return False
