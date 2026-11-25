#!/usr/bin/env bash
# Despliegue de Print with Brilint en Cloudflare.
# Uso: ./deploy.sh   (requiere `npx wrangler login` hecho)
set -euo pipefail
cd "$(dirname "$0")"
export WRANGLER_SEND_METRICS=false
W="npx --yes wrangler@4"
say() { printf "\n\033[1;32m▸ %s\033[0m\n" "$*"; }
PROJECT="brilint-print"

say "Sesión de Cloudflare"
$W whoami

say "Proyecto de Pages"
$W pages project create "$PROJECT" --production-branch main || echo "  (ya existe)"

say "Base de datos D1"
if ! $W d1 list --json | grep -q "\"$PROJECT\""; then
  $W d1 create "$PROJECT"
fi
DB_ID=$($W d1 list --json | python3 -c "import sys,json;d=json.load(sys.stdin);print(next(x['uuid'] for x in d if x['name']=='$PROJECT'))")
echo "  database_id = $DB_ID"
python3 - "$DB_ID" <<'PY'
import re, sys, pathlib
p = pathlib.Path("wrangler.toml")
s = p.read_text(encoding="utf-8")
s = re.sub(r'database_id\s*=\s*"[^"]*"', f'database_id = "{sys.argv[1]}"', s)
p.write_text(s, encoding="utf-8")
print("  wrangler.toml actualizado")
PY

say "Almacenamiento KV"
if grep -q 'id = "PENDIENTE"' wrangler.toml; then
  OUT=$($W kv namespace create brilint-print-files 2>&1) || true
  KV_ID=$(printf '%s\n' "$OUT" | grep -oE 'id = "[a-f0-9]{32}"' | head -1 | cut -d'"' -f2)
  if [ -z "${KV_ID:-}" ]; then
    echo "  no se pudo leer el id del namespace; revisa 'wrangler kv namespace list'"; exit 1
  fi
  echo "  namespace = $KV_ID"
  python3 - "$KV_ID" <<'PY'
import re, sys, pathlib
p = pathlib.Path("wrangler.toml")
s = p.read_text(encoding="utf-8")
s = s.replace('id = "PENDIENTE"', f'id = "{sys.argv[1]}"', 1)
p.write_text(s, encoding="utf-8")
print("  wrangler.toml actualizado")
PY
else
  echo "  namespace ya configurado en wrangler.toml"
fi

say "Esquema de la cola"
$W d1 execute "$PROJECT" --remote --file schema.sql

say "Token del agente"
if [ ! -s agent/.token ]; then
  python3 -c "import secrets; print(secrets.token_urlsafe(32))" > agent/.token
  echo "  token generado en agent/.token"
fi
$W pages secret put AGENT_TOKEN --project-name "$PROJECT" < agent/.token

say "Publicando"
$W pages deploy site --project-name "$PROJECT" --commit-dirty=true

say "Listo"
echo "  URL:  https://$PROJECT.pages.dev"
echo "  Token para agent/config.json:  $(cat agent/.token)"
