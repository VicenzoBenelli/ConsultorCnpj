# CNPJ.ws — API Pública

> Documento de contexto técnico preparado a partir da documentação pública oficial do CNPJ.ws.
>
> Fonte: https://docs.cnpj.ws/referencia-de-api/api-publica  
> Consultado em: 2026-09-16  
> Objetivo: fornecer contexto compacto e estruturado para agentes de IA, RAG e desenvolvimento de integrações.
>
> Observação: este arquivo é uma síntese técnica reestruturada, não uma cópia literal da página original.

## 1. Visão geral

A **API Pública do CNPJ.ws** permite acessar, de forma pública e limitada, informações empresariais brasileiras mantidas na base do CNPJ.ws.

A seção oficial da API pública está dividida em três assuntos principais:

1. **Consulta de CNPJ**
   - Consulta dados cadastrais e empresariais associados a um CNPJ.
   - Método HTTP: `GET`.
   - Endpoint base:
     `https://publica.cnpj.ws/cnpj/{cnpj}`

2. **Validação de inscrição SUFRAMA**
   - Verifica uma inscrição SUFRAMA associada a um CNPJ.
   - Método HTTP: `POST`.
   - Endpoint:
     `https://publica.cnpj.ws/suframa`

3. **Limitações da API pública**
   - A API aplica limitação por IP.
   - Limite documentado: **3 requisições por minuto por IP**.
   - Excesso de chamadas resulta em HTTP `429 Too Many Requests`.
   - Repetir excessivamente chamadas enquanto o IP já está limitado pode gerar uma penalização temporária adicional.

## 2. Base URL

```text
https://publica.cnpj.ws
```

## 3. Endpoints documentados

| Operação | Método | Endpoint |
|---|---|---|
| Consultar CNPJ | `GET` | `/cnpj/{cnpj}` |
| Validar inscrição SUFRAMA | `POST` | `/suframa` |

## 4. Formato de dados

As respostas documentadas utilizam:

```http
Content-Type: application/json
```

Na validação SUFRAMA, o corpo da requisição também é JSON:

```http
Content-Type: application/json
```

## 5. Normalização do CNPJ

Quando um CNPJ for enviado à API, ele deve ser informado **sem caracteres especiais**.

Formato esperado:

```text
00000000000000
```

Evite enviar:

```text
00.000.000/0000-00
```

Uma integração deve, preferencialmente, normalizar a entrada antes da chamada:

1. remover `.`, `/`, `-`, espaços e quaisquer caracteres não numéricos;
2. validar que restaram 14 dígitos;
3. somente então enviar a requisição.

## 6. Autenticação

A documentação desta seção descreve a API como pública e os exemplos de consulta de CNPJ não apresentam token ou chave de API.

A documentação da validação SUFRAMA lista uma resposta HTTP `401`, portanto a aplicação cliente deve tratar esse status caso seja retornado, mesmo que o endpoint esteja documentado dentro da API pública.

## 7. Rate limiting

Regra documentada:

```text
3 requisições por minuto por IP
```

Características importantes:

- o limite é associado ao **IP solicitante**;
- requisições contam para a limitação mesmo quando a consulta não encontra o CNPJ;
- após exceder o limite, a API retorna `429`;
- é necessário aguardar a liberação indicada pela API antes de continuar;
- insistência excessiva após atingir o limite pode provocar bloqueio temporário adicional do IP.

Para integrações reais, implemente:

- fila ou limitador de requisições;
- retry somente após o período de liberação;
- backoff;
- cache para consultas repetidas;
- deduplicação de chamadas concorrentes para o mesmo CNPJ;
- observabilidade de respostas `429`.

## 8. Tratamento de erros

Formato genérico mostrado pela documentação:

```json
{
  "status": 0,
  "titulo": "string",
  "detalhes": "string",
  "validacao": [
    "string"
  ]
}
```

Nem toda resposta de erro precisa necessariamente conter todos os campos em todas as situações. O consumidor deve ser tolerante a campos ausentes ou adicionais.

## 9. Uso recomendado por um agente de IA

Ao gerar código ou tomar decisões sobre esta API, o agente deve seguir estas regras:

- utilizar somente `https://publica.cnpj.ws` como base da API pública descrita nestes documentos;
- não inventar endpoints;
- enviar CNPJ sem máscara;
- considerar o limite de 3 requisições/minuto/IP antes de propor loops, jobs ou importações em lote;
- nunca realizar retry agressivo após `429`;
- tratar campos JSON como potencialmente nulos quando os exemplos indicarem ausência de informação;
- considerar `atualizado_em` como indicador da atualização do registro no CNPJ.ws, não como garantia de atualização em tempo real;
- para detalhes do contrato da consulta de empresa, consultar o arquivo `02-consultando-cnpj.md`;
- para SUFRAMA, consultar `03-validando-inscricao-suframa.md`;
- para regras de limitação, consultar `04-limitacoes.md`.

## 10. Escopo desta documentação

A documentação da API pública é voltada a acesso **público e limitado** a informações empresariais. Ela não deve ser confundida com os endpoints e recursos da API comercial do CNPJ.ws.
