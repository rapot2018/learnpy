class Car:

    def __init__(self, brand):
        self.brand = brand

    def drive(self):
        print(self.brand + " driving")

c = Car("Honda")
c.drive()

for i in range(5):
    print(i)