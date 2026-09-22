# Consultor CNPJ

Aplicação FastAPI para criar consultas de CNPJ, processá-las por um worker
síncrono e disponibilizar resultados e exportação XLSX.

## Deploy no Render

### Perfil gratuito

O perfil gratuito usa dois recursos em `virginia`:

- Web Service Free: FastAPI, Jinja2, arquivos estáticos e Embedded Worker;
- Render PostgreSQL Free: banco, fila, leases e rate limiter global.

Com `RUN_EMBEDDED_WORKER=true`, o worker síncrono roda em uma thread do mesmo
processo Web. O Web usa a Internal Database URL, e o acesso externo ao banco é
bloqueado pelo Blueprint.

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
- `RUN_EMBEDDED_WORKER=true` somente no perfil gratuito do Render.

As demais configurações possuem defaults em `app.core.config.Settings`.
`TEST_DATABASE_URL` é exclusivo de testes e não deve ser configurada no Render.
Não versione `.env`, `.env.test` ou credenciais.

### Health checks

- `/health` é o health check do Render e não depende do banco;
- `/ready` verifica o PostgreSQL e deve ser usado para diagnóstico e smoke.

### Worker embedded

O worker inicia somente no lifespan real do FastAPI, nunca durante import,
build ou Alembic. No encerramento, o Web sinaliza a thread e aguarda até 20
segundos de forma cooperativa. O Render permite até 60 segundos de shutdown.

Para desenvolvimento local, mantenha `RUN_EMBEDDED_WORKER=false` e execute o
Web com `--reload` e o worker em terminal separado. Para testar o modo
embedded, use `RUN_EMBEDDED_WORKER=true`, suba somente o Web e não use
`--reload`.

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
- Enquanto o Web está suspenso, o Embedded Worker também está parado. Ao acordar
  após uma nova requisição, a recuperação de leases permite retomar itens que
  ficaram em processamento; a semântica continua at-least-once.
- O PostgreSQL Free expira após 30 dias e não é apropriado para uso estável.
- Lotes grandes não são apropriados para processamento desacompanhado no perfil
  Free; o polling da interface mantém tráfego real somente enquanto a página
  está aberta.
- A aplicação é pública e não possui autenticação: qualquer visitante pode
  criar Jobs.
- Jobs e resultados não possuem política automática de retenção.

### Perfil pago futuro

Para voltar ao modelo contínuo, defina `RUN_EMBEDDED_WORKER=false` no Web e
crie um Background Worker separado com `python -m app.worker.main`. O mesmo
PostgreSQL, fila, leases e rate limiter continuam sendo usados.
