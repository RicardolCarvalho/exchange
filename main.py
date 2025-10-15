from datetime import datetime
import httpx
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator

app = FastAPI()
security = HTTPBearer()

# Configurações diretas
API_KEY = "6da6d6433dce806f39b5f292"
AUTH_SERVICE_URL = "http://auth:8080"
BASE_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest"

class ExchangeResponse(BaseModel):
    sell: float
    buy: float
    date: str
    id_account: str

    @field_validator("date", mode="before")
    @classmethod
    def format_date(cls, v) -> str:
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return v

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                f"{AUTH_SERVICE_URL}/auth/solve",
                json={"jwt": credentials.credentials},
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("idAccount")
            raise HTTPException(status_code=401, detail=f"Token inválido: {response.status_code}")
        except httpx.HTTPError as e:
            raise HTTPException(status_code=503, detail=f"Serviço de autenticação indisponível: {str(e)}")

@app.get("/exchange/{from_currency}/{to_currency}", response_model=ExchangeResponse)
async def get_exchange_rate(
    from_currency: str,
    to_currency: str,
    id_account: str = Depends(verify_token)
):
    async with httpx.AsyncClient(timeout=6.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/{from_currency.upper()}")
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Erro na API: {exc}")

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Erro ao obter taxa de câmbio")

    data = response.json()
    if data.get("result") != "success":
        raise HTTPException(status_code=400, detail=data.get('error-type', 'Erro desconhecido'))

    rates = data.get("conversion_rates", {})
    if to_currency.upper() not in rates:
        raise HTTPException(status_code=400, detail=f"Moeda {to_currency.upper()} não encontrada")

    rate = float(rates[to_currency.upper()])

    return ExchangeResponse(
        sell=round(rate * 1.01, 4),
        buy=round(rate * 0.99, 4),
        date=datetime.utcnow(),
        id_account=id_account,
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "exchange"}
