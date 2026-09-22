export class ApiError extends Error {
  constructor(kind, message, status = null, payload = null) {
    super(message);
    this.kind = kind;
    this.status = status;
    this.payload = payload;
  }
}

export async function requestJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new ApiError("network", "Não foi possível conectar à aplicação.");
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    if (!response.ok) {
      throw new ApiError("http", "A aplicação retornou uma resposta inválida.", response.status);
    }
    throw new ApiError("invalid-response", "A aplicação retornou uma resposta inválida.", response.status);
  }

  if (!response.ok) {
    throw new ApiError("http", "A solicitação não foi concluída.", response.status, payload);
  }
  return { status: response.status, data: payload };
}
