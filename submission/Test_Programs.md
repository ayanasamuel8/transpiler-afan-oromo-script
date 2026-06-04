# Test Programs

This section provides the three required test programs for the course project. Each program includes OromScript source, generated Python, and the real execution result.

## 1. Basic program: variables and math

Source: `submission/examples/basic_program.orm`

```orm
lakkoofsa1 = 8
lakkoofsa2 = 4
idaama = lakkoofsa1 + lakkoofsa2
hirama = lakkoofsa1 / lakkoofsa2

agarsiisi("Idaama =", idaama)
agarsiisi("Hirama =", hirama)
```

Generated Python: `submission/generated/basic_program.py`

```python
lakkoofsa1 = 8
lakkoofsa2 = 4
idaama = lakkoofsa1 + lakkoofsa2
hirama = lakkoofsa1 / lakkoofsa2
print('Idaama =', idaama)
print('Hirama =', hirama)
```

Execution result:

```text
Idaama = 12
Hirama = 2.0
```

## 2. Control flow program

Source: `submission/examples/control_flow_program.orm`

```orm
lakkoo = 1
walitti_qabi = 0

yeroo lakkoo < 6:
    walitti_qabi = walitti_qabi + lakkoo
    lakkoo = lakkoo + 1

yoo walitti_qabi > 10:
    agarsiisi("Walitti qabamni guddaadha")
yoo_miti:
    agarsiisi("Walitti qabamni xiqqaadha")

agarsiisi("Bu'aa =", walitti_qabi)
```

Generated Python: `submission/generated/control_flow_program.py`

```python
lakkoo = 1
walitti_qabi = 0
while lakkoo < 6:
    walitti_qabi = walitti_qabi + lakkoo
    lakkoo = lakkoo + 1
if walitti_qabi > 10:
    print('Walitti qabamni guddaadha')
else:
    print('Walitti qabamni xiqqaadha')
print("Bu'aa =", walitti_qabi)
```

Execution result:

```text
Walitti qabamni guddaadha
Bu'aa = 15
```

## 3. Feature demonstration

Source: `submission/examples/feature_demo.orm`

```orm
hojii sadarkaa_kenni(marka):
    yoo marka > 80:
        deebi "A"
    yookaan marka > 60:
        deebi "B"
    yoo_miti:
        deebi "C"

gosa Barataa:
    hojii __init__(of, maqaa, marka):
        of.maqaa = maqaa
        of.marka = marka

    hojii agarsiisi_gatii(of):
        agarsiisi(of.maqaa + " => " + sadarkaa_kenni(of.marka))

barataa = Barataa("Bontu", 75)
barataa.agarsiisi_gatii()
```

Generated Python: `submission/generated/feature_demo.py`

```python
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
```

Execution result:

```text
Bontu => B
```
