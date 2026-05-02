import random
import time

class BankAPI:
    @staticmethod
    def pay_employee(emp_id):
        # 10% chance of a 429 Rate Limit
        if random.random() < 0.10:
            raise Exception("429 Too Many Requests")
        
        # Simulating a very slow response
        time.sleep(random.uniform(5, 12))
        return True