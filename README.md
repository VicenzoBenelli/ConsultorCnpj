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

| Serviço | Build | Start |
| --- | --- | --- |
| Web Free (Fase A) | `pip install -r requirements.txt && python -m alembic upgrade head` | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

O perfil gratuito de demonstração não oferece `preDeployCommand` para o Web;
por isso, o build executa Alembic. O build não executa pytest: testes de
integração exigem banco de teste isolado e jamais devem apontar para o banco de
produção.

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

### Primeiro bootstrap

O `render.yaml` atual é propositalmente o bootstrap em duas etapas, para que o
Worker não inicie antes de o schema existir.

**Fase A — primeiro deploy**

1. O Blueprint cria o Render PostgreSQL e o Render Web Service em `virginia`.
2. O build do Web executa `python -m alembic upgrade head`.
3. Confirme `GET /health` com HTTP 200.
4. Confirme `GET /ready` com HTTP 200.

**Fase B — após sucesso da Fase A**

1. Adicione novamente `cnpj-consulta-worker` ao `render.yaml`.
2. Faça commit e push da alteração.
3. O Render cria o Background Worker.
4. Confirme o início do Worker nos logs.
5. Execute o smoke com um CNPJ.

### Smoke pós-deploy

1. Confirme `GET /health` e `GET /ready` com HTTP 200.
2. Abra `/`.
3. Crie um Job com `12.097.046/0001-50`.
4. Confirme a transição `PENDING` → `RUNNING` → `COMPLETED` e o resultado
   `SUCCESS`.
5. Baixe e abra o XLSX.

### Limitações do perfil gratuito de demonstração

- Web e PostgreSQL usam `plan: free`; o Web entra em spin-down após
  inatividade e pode apresentar cold start no próximo acesso.
- O PostgreSQL Free expira após 30 dias e não é apropriado para uso estável.
- O Background Worker do Render não possui plano Free. Ele permanece ausente
  deste primeiro Blueprint e será configurado somente na próxima etapa.
- A aplicação é pública e não possui autenticação: qualquer visitante pode
  criar Jobs.
- Jobs e resultados não possuem política automática de retenção.
