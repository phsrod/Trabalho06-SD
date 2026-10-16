from locust import HttpUser, task, between
import random
import time


BASE_URL = "http://localhost:8080"


class PerfilLeitura(HttpUser):
    host = BASE_URL
    wait_time = between(1, 3)

    @task(45)
    def listar_tutores(self):
        self.client.get("/api/customer/owners")

    @task(35)
    def consultar_tutor(self):
        owner_id = random.randint(1, 12)
        self.client.get(f"/api/customer/owners/{owner_id}")

    @task(15)
    def listar_veterinarios(self):
        self.client.get("/api/vet/vets")

    @task(5)
    def cadastrar_tutor(self):
        dados = {
            "firstName": "Teste",
            "lastName": f"Locust{int(time.time() * 1000)}",
            "address": "Rua de Teste, 123",
            "city": "Picos",
            "telephone": str(random.randint(1000000, 999999999999))
        }

        self.client.post("/api/customer/owners", json=dados)


class PerfilEscrita(HttpUser):
    host = BASE_URL
    wait_time = between(1, 3)

    @task(20)
    def listar_tutores(self):
        self.client.get("/api/customer/owners")

    @task(20)
    def consultar_tutor(self):
        owner_id = random.randint(1, 12)
        self.client.get(f"/api/customer/owners/{owner_id}")

    @task(20)
    def listar_veterinarios(self):
        self.client.get("/api/vet/vets")

    @task(40)
    def cadastrar_tutor(self):
        dados = {
            "firstName": "Teste",
            "lastName": f"Locust{int(time.time() * 1000)}",
            "address": "Rua de Teste, 123",
            "city": "Picos",
            "telephone": str(random.randint(1000000, 999999999999))
        }

        self.client.post("/api/customer/owners", json=dados)