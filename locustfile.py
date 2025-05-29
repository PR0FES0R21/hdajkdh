from locust import HttpUser, task, between

def generate_wallet_address():
    return "0xCBc809C4a3243c5F0283754D8e5772FdA632aA96"

class CigarUser(HttpUser):
    wait_time = between(0, 0)  # semua user submit di saat yang sama

    @task
    def register_wallet(self):
        wallet = generate_wallet_address()
        self.client.post("/register", json={"wallet_address": wallet})
