import os

os.environ["ADMIN_TOKEN"] = "token-de-teste-123456"
os.environ["CORS_ORIGINS"] = "https://meusite.com"
os.environ["DATABASE_URL"] = "sqlite:///./test_giufit.db"

import pytest
from fastapi.testclient import TestClient

from main import app

AUTH = {"Authorization": "Bearer token-de-teste-123456"}
PRATO = {
    "nome": "Frango com batata doce",
    "descricao": "Fit",
    "opcoes": [{"tamanho": "250g", "preco": 18.5}, {"tamanho": "350g", "preco": 24}],
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    if os.path.exists("test_giufit.db"):
        os.remove("test_giufit.db")


def test_cardapio_publico_funciona(client):
    assert client.get("/pratos").status_code == 200


@pytest.mark.parametrize("metodo,url", [("post", "/pratos"), ("put", "/pratos/1"), ("delete", "/pratos/1")])
def test_escrita_sem_token_e_barrada(client, metodo, url):
    r = getattr(client, metodo)(url, **({"json": PRATO} if metodo != "delete" else {}))
    assert r.status_code == 401


def test_token_errado_e_barrado(client):
    r = client.post("/pratos", json=PRATO, headers={"Authorization": "Bearer errado"})
    assert r.status_code == 401


def test_crud_completo_com_token(client):
    r = client.post("/pratos", json=PRATO, headers=AUTH)
    assert r.status_code == 201
    pid = r.json()["id_prato"]

    lista = client.get("/pratos").json()
    assert any(p["id"] == pid and len(p["opcoes"]) == 2 for p in lista)

    novo = {**PRATO, "nome": "Editado", "opcoes": [{"tamanho": "500g", "preco": 30}]}
    assert client.put(f"/pratos/{pid}", json=novo, headers=AUTH).status_code == 200
    editado = next(p for p in client.get("/pratos").json() if p["id"] == pid)
    assert editado["nome"] == "Editado" and len(editado["opcoes"]) == 1

    assert client.delete(f"/pratos/{pid}", headers=AUTH).status_code == 200
    assert client.delete(f"/pratos/{pid}", headers=AUTH).status_code == 404


def test_inativo_nao_aparece_no_publico_mas_aparece_no_admin(client):
    r = client.post("/pratos", json={**PRATO, "ativo": False}, headers=AUTH)
    pid = r.json()["id_prato"]
    assert all(p["id"] != pid for p in client.get("/pratos").json())
    assert any(p["id"] == pid for p in client.get("/admin/pratos", headers=AUTH).json())
    assert client.get("/admin/pratos").status_code == 401


@pytest.mark.parametrize(
    "corpo",
    [
        {**PRATO, "nome": ""},
        {**PRATO, "nome": "x" * 101},
        {**PRATO, "opcoes": []},
        {**PRATO, "opcoes": [{"tamanho": "250g", "preco": -5}]},
        {**PRATO, "opcoes": [{"tamanho": "250g", "preco": 999999}]},
    ],
)
def test_entrada_invalida_e_rejeitada(client, corpo):
    assert client.post("/pratos", json=corpo, headers=AUTH).status_code == 422


def test_cors_so_para_origem_autorizada(client):
    ok = client.get("/pratos", headers={"Origin": "https://meusite.com"})
    assert ok.headers.get("access-control-allow-origin") == "https://meusite.com"
    ruim = client.get("/pratos", headers={"Origin": "https://malvado.com"})
    assert "access-control-allow-origin" not in ruim.headers


def test_login_admin_e_rate_limit(client):
    assert client.post("/admin/login", headers=AUTH).status_code == 204
    codigos = [client.post("/admin/login", headers={"Authorization": "Bearer x"}).status_code for _ in range(8)]
    assert 429 in codigos  # força bruta é limitada
