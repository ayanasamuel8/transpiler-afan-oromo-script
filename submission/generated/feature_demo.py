def sadarkaa_kenni(marka):
    if marka > 80:
        return 'A'
    elif marka > 60:
        return 'B'
    else:
        return 'C'

class Barataa:

    def __init__(self, maqaa, marka):
        self.maqaa = maqaa
        self.marka = marka

    def agarsiisi_gatii(self):
        print(self.maqaa + ' => ' + sadarkaa_kenni(self.marka))
barataa = Barataa('Bontu', 75)
barataa.agarsiisi_gatii()
