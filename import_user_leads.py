"""
Script de importação rápida dos leads para o Supabase.
"""

import sys
import os
import uuid
from datetime import datetime

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_supabase
from config import BR_TZ

RAW_PHONES = [
    "5512988265141",
    "5512981695000",
    "5512981568028",
    "5512997931046",
    "5511958074621",
    "541155160747",
    "5512982079442",
    "5512988618747",
    "5512997244413",
    "5512988995799",
    "5512981198843",
    "5512988097151",
    "5512981521844",
    "5512988525160",
    "5512997443041",
    "5512996563191",
    "5512988175104",
    "5512988864730",
    "5512982602284",
    "5512996544365",
    "5512996261979",
    "5512996862576",
    "5512988246989",
    "5512988320143",
    "5512991149650",
    "5512981472664",
    "5512991604606",
    "5512981406079",
    "5512991881349",
    "5512996795657",
    "5512983019293",
    "5512983019293",
    "5512988605128",
    "5512982603580",
    "5512997152581",
    "5512996098357",
    "5512982066413",
    "5512996466480",
    "5512981564059",
    "5512988271075",
    "5512981062854",
    "5512991456214",
    "5512982171982",
    "5512997956814",
    "5512988287970",
    "5512997367273",
    "5512996838196",
    "5512991472041",
    "5512988831223",
    "5512997519018",
    "5512982717895",
    "5512982470667",
    "5512996515437",
    "5512991350443",
    "5512997350599",
    "5512982100326",
    "5512983131967",
    "5512992394362",
    "5512988808834",
    "5512981808685",
    "5512997069766",
    "5512982357257",
    "5512982045385",
    "5512991516860",
    "5512987084800",
    "5512997343740",
    "5512997561215",
    "5512991495547",
    "5512987045934",
    "5511972271864",
    "5512997657620",
    "5512996672605",
    "5511947781683",
    "5512988252746",
    "5512991497022",
    "5512991433130",
    "5512991798743",
    "5512988401508",
    "5512981574986",
    "5512981129889",
    "5512988145556",
    "5512988431907",
    "5512988431907",
    "5512988033272",
    "5512997429098",
    "5512981343402",
    "5512991870771",
    "5512992321001",
]

def run_fast_import():
    sb = get_supabase()
    print(f"Total bruto: {len(RAW_PHONES)} números")

    unique_phones = []
    seen = set()
    for p in RAW_PHONES:
        clean = "".join(c for c in p if c.isdigit())
        if clean not in seen:
            seen.add(clean)
            unique_phones.append(clean)

    print(f"Total de telefones únicos: {len(unique_phones)}")

    # Busca telefones já existentes
    existing_res = sb.table("leads").select("phone").execute()
    existing_phones = set(r["phone"] for r in (existing_res.data or []))
    print(f"Telefones já no banco: {len(existing_phones)}")

    to_insert = []
    now = datetime.now(BR_TZ).isoformat()

    for phone in unique_phones:
        if phone not in existing_phones:
            lead_id = f"lead_{uuid.uuid4().hex[:8]}"
            to_insert.append({
                "id": lead_id,
                "name": "",
                "phone": phone,
                "source": "disparo_direto",
                "tags": ["disparo_em_massa", "reativacao"],
                "added_at": now,
                "added_by": "import_script",
                "status": "active",
                "notes": "Lead para disparo em massa",
                "paused": False,
                "remarketing_day": 0,
            })

    print(f"Novos registros a inserir: {len(to_insert)}")

    if to_insert:
        # Insere em lotes de 25
        batch_size = 25
        for i in range(0, len(to_insert), batch_size):
            batch = to_insert[i:i+batch_size]
            res = sb.table("leads").insert(batch).execute()
            print(f"  Inserido lote {i//batch_size + 1}: {len(res.data or [])} leads")

    # Contagem final
    total_res = sb.table("leads").select("id", count="exact").execute()
    print("\n" + "="*45)
    print(f"✅ IMPORTAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f"   Novos leads inseridos: {len(to_insert)}")
    print(f"   Já existentes mantidos: {len(unique_phones) - len(to_insert)}")
    print(f"   Total de leads no bolsão agora: {total_res.count}")
    print("="*45)

if __name__ == "__main__":
    run_fast_import()
