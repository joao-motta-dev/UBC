#!/bin/bash
set -e

echo "Aguardando Postgres e Redis..."

while ! nc -z postgres 5432; do
  sleep 1
done

while ! nc -z redis 6379; do
  sleep 1
done

echo "Serviços prontos. Iniciando comando: $@"
exec "$@"