# CNPJ.ws — Validando Inscrição SUFRAMA na API Pública

> Fonte oficial: https://docs.cnpj.ws/referencia-de-api/api-publica/validando-inscricao-suframa  
> Consultado em: 2026-09-16  
> Objetivo: contexto técnico para desenvolvimento, agentes de IA e RAG.
>
> Observação: síntese técnica reestruturada da documentação oficial.

## 1. Objetivo

Validar uma inscrição no **SUFRAMA** por meio da API pública do CNPJ.ws.

A operação recebe:

- CNPJ da empresa;
- inscrição SUFRAMA.

## 2. Endpoint

### Método

```http
POST
```

### URL

```text
https://publica.cnpj.ws/suframa
```

## 3. Limite

A documentação informa:

```text
até 3 consultas por minuto
```

A limitação geral da API pública é aplicada por IP.

## 4. Normalização do CNPJ

O CNPJ deve ser enviado **sem caracteres especiais**.

Exemplo de formato esperado:

```text
00000000000000
```

## 5. Content-Type

O corpo da requisição utiliza:

```http
Content-Type: application/json
```

## 6. Request body

Campos documentados:

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---:|---|
| `cnpj` | string | sim | CNPJ da empresa |
| `inscricao` | string | sim | Inscrição SUFRAMA |

Schema:

```json
{
  "cnpj": "string",
  "inscricao": "string"
}
```

Recomendação: trate os dois valores como strings para evitar perda de zeros à esquerda.

## 7. Exemplo de requisição

```bash
curl --request POST   --url "https://publica.cnpj.ws/suframa"   --header "Accept: application/json"   --header "Content-Type: application/json"   --data '{
    "cnpj": "00000000000000",
    "inscricao": "000000000"
  }'
```

Os números acima são placeholders de formato, não uma empresa real.

## 8. Respostas HTTP documentadas

| Status | Uso |
|---:|---|
| `200` | Validação retornada com sucesso |
| `401` | Resposta de erro listada pela referência oficial |
| `404` | Registro/combinação consultada não encontrada |

Além desses status específicos da página, clientes da API pública também devem estar preparados para `429` em razão do rate limit geral.

## 9. Resposta `200`

Schema documentado:

```json
{
  "cnpj_raiz": "string",
  "cnpj": "string",
  "inscricao_suframa": "string",
  "ativo": true,
  "atualizado_em": "ISO-8601"
}
```

### Campos

| Campo | Tipo | Significado |
|---|---|---|
| `cnpj_raiz` | string | Raiz do CNPJ |
| `cnpj` | string | CNPJ relacionado à inscrição |
| `inscricao_suframa` | string | Inscrição SUFRAMA validada |
| `ativo` | boolean | Indica se a inscrição retornada está ativa |
| `atualizado_em` | datetime/string | Momento de atualização do registro na base |

### Interpretação de `ativo`

```text
ativo = true
```

indica que a inscrição retornada está ativa segundo os dados disponíveis à API.

Não use apenas HTTP `200` como sinônimo de inscrição ativa. O código HTTP indica que a consulta foi processada; a situação de atividade está no campo `ativo`.

## 10. Respostas de erro

A referência apresenta este formato genérico:

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

Esse formato é mostrado tanto para `401` quanto para `404`.

## 11. Exemplo em JavaScript

```javascript
async function validarSuframa(cnpj, inscricao) {
  const normalizedCnpj = cnpj.replace(/\D/g, "");
  const normalizedInscricao = String(inscricao).replace(/\D/g, "");

  if (normalizedCnpj.length !== 14) {
    throw new Error("CNPJ deve possuir 14 dígitos");
  }

  const response = await fetch("https://publica.cnpj.ws/suframa", {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      cnpj: normalizedCnpj,
      inscricao: normalizedInscricao
    })
  });

  if (response.status === 404) {
    return null;
  }

  if (response.status === 429) {
    throw new Error("Rate limit da API CNPJ.ws excedido");
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detalhes ?? `Erro CNPJ.ws: HTTP ${response.status}`
    );
  }

  return response.json();
}
```

## 12. Exemplo em Python

```python
import re
import requests

BASE_URL = "https://publica.cnpj.ws"

def validar_suframa(cnpj: str, inscricao: str) -> dict | None:
    cnpj_normalizado = re.sub(r"\D", "", cnpj)
    inscricao_normalizada = re.sub(r"\D", "", str(inscricao))

    if len(cnpj_normalizado) != 14:
        raise ValueError("CNPJ deve possuir 14 dígitos")

    response = requests.post(
        f"{BASE_URL}/suframa",
        json={
            "cnpj": cnpj_normalizado,
            "inscricao": inscricao_normalizada,
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )

    if response.status_code == 404:
        return None

    if response.status_code == 429:
        raise RuntimeError("Rate limit da API CNPJ.ws excedido")

    response.raise_for_status()
    return response.json()
```

## 13. Pacote JavaScript citado na documentação

A documentação menciona o pacote:

```text
consultar-cnpj
```

Instalação:

```bash
yarn add consultar-cnpj
```

A referência também demonstra uma chamada de conveniência equivalente a:

```javascript
consultarCNPJ.suframa(cnpj, inscricao)
```

Esse pacote é opcional. O contrato HTTP documentado continua sendo `POST https://publica.cnpj.ws/suframa`.

## 14. Recomendações de integração

- normalize o CNPJ antes da chamada;
- preserve a inscrição SUFRAMA como string;
- trate `ativo` como a fonte de verdade para o estado retornado;
- trate explicitamente `401`, `404` e `429`;
- limite chamadas no próprio cliente;
- evite retries automáticos sem espera após `429`;
- mantenha timeout de rede;
- registre falhas de integração sem expor desnecessariamente dados sensíveis em logs;
- não conclua que `404` significa “inscrição inativa”: ele é diferente de uma resposta `200` com `ativo: false`.

## 15. Regras para agentes de IA

Ao gerar integração para SUFRAMA:

1. usar `POST`;
2. usar `/suframa`;
3. enviar JSON;
4. usar exatamente os campos `cnpj` e `inscricao`;
5. não renomear `inscricao` para `inscricao_suframa` no request;
6. interpretar `inscricao_suframa` como campo de resposta;
7. verificar `ativo`;
8. respeitar o rate limit global da API pública.
