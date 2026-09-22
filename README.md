# Consultor CNPJ

Aplicação FastAPI para criar consultas de CNPJ, processá-las por um worker
síncrono e disponibilizar resultados e exportação XLSX.

## Deploy no Render

### Arquitetura

O deploy usa três recursos na mesma região do Render:

- Web Service: FastAPI, Jinja2 e arquivos estáticos;
- Background Worker: processamento da fila PostgreSQL e consultas à CNPJ.ws;
- Render PostgreSQL: banco da aplicação, fila, leases e rate limiter global.

Web e Worker usam a mesma Internal Database URL. O acesso externo ao banco é
bloqueado pelo Blueprint; não use a External Database URL para os serviços.

### Runtime e comandos

O runtime é Python 3.12.10, fixado em `.python-version`.

| Serviço | Build | Pre-deploy | Start |
| --- | --- | --- | --- |
| Web | `pip install -r requirements.txt` | `python -m alembic upgrade head` | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Worker | `pip install -r requirements.txt` | — | `python -m app.worker.main` |

Somente o Web executa migrations. O Worker nunca executa Alembic. O build não
executa pytest: testes de integração exigem banco de teste isolado e jamais
devem apontar para o banco de produção.

### Variáveis de ambiente

O Blueprint configura somente as variáveis necessárias em produção:

- `DATABASE_URL`: referência interna dinâmica ao PostgreSQL do Render;
- `APP_ENV=production`;
- `LOG_LEVEL=INFO`.

As demais configurações possuem defaults em `app.core.config.Settings`.
`TEST_DATABASE_URL` é exclusivo de testes e não deve ser configurada no Render.
Não versione `.env`, `.env.test` ou credenciais.

### Health checks

- `/health` é o health check do Render e não depende do banco;
- `/ready` verifica o PostgreSQL e deve ser usado para diagnóstico e smoke.

### Primeiro deploy

Para impedir que o Worker rode antes do schema existir:

1. Crie o PostgreSQL e o Web Service pelo Blueprint, inicialmente sem habilitar
   o Worker.
2. O pre-deploy do Web executa `python -m alembic upgrade head`.
3. Confirme `GET /health` e `GET /ready`.
4. Habilite o Background Worker e confirme o início nos logs.

O `render.yaml` final declara os três recursos. Para o bootstrap seguro,
publique primeiro uma revisão temporária que contenha apenas banco e Web; após
validar readiness, publique a revisão que inclui o Worker.

### Smoke pós-deploy

1. Confirme `GET /health` e `GET /ready` com HTTP 200.
2. Abra `/`.
3. Crie um Job com `12.097.046/0001-50`.
4. Confirme a transição `PENDING` → `RUNNING` → `COMPLETED` e o resultado
   `SUCCESS`.
5. Baixe e abra o XLSX.

### Limitações operacionais

- O Worker é um recurso pago no Render; o perfil estável definido no Blueprint
  usa 0.5 CPU/512 MB para Web e Worker e 0.1 CPU/256 MB para PostgreSQL.
- A aplicação é pública e não possui autenticação: qualquer visitante pode
  criar Jobs.
- Jobs e resultados não possuem política automática de retenção.
- Começar com uma instância Web e uma Worker preserva o rate limiter global e
  evita ampliar custo e concorrência sem validação de produção.
