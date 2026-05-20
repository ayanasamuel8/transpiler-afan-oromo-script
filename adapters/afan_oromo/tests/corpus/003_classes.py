class Barataa:

    def __init__(self, maqaa, umri):
        self.maqaa = maqaa
        self.umri = umri

    def of_ibsi(self):
        print(self.maqaa + ": " + str(self.umri))


b = Barataa("Chaltu", 20)
b.of_ibsi()
