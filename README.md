# Detekcija saobraćajnih traka (DOSiVuAV)

### Izveštaj / README

#### 1. Priložite izveštaj koji obuhvata sve tačke kriterijuma ocenjivanja i način na koji ste odgovorili na svaku od njih.

### Kalibracija kamere

#### 1. Ukratko opišite kako ste izračunali matricu kamere i koeficijente distorzije. Priložite primer kalibracione slike sa ispravljenom distorzijom.

Kod je funkcija `calibrate` ([pipeline.py:19-41](pipeline.py#L19-L41)). Detektor je poziva jednom, a rezultat se
čuva u `sources/camera_cal/calib.npz`.

1. **Tačke objekta** ([pipeline.py:25-26](pipeline.py#L25-L26)): šahovska tabla ima 9x6 unutrašnjih uglova.
   Njihove koordinate na tabli su `(x, y, 0)` u mreži. Tabla je ravna (z = 0), pa se isti niz koristi za svaku sliku.
2. **Tačke slike** ([pipeline.py:30-35](pipeline.py#L30-L35)): `cv2.findChessboardCorners` traži uglove na sivoj
   slici, a `cv2.cornerSubPix` ih precizira na nivo ispod piksela. Uglovi su pronađeni na **17 od 20** slika. Na
   `calibration1.jpg`, `calibration4.jpg` i `calibration5.jpg` deo table je van kadra, pa se te slike preskaču.
3. **Kalibracija** ([pipeline.py:38](pipeline.py#L38)): `cv2.calibrateCamera` prilagođava pinhole model kamere
   (predavanje 09) svim parovima tačaka. Matrica kamere sadrži žižne daljine `fx, fy` i glavnu tačku `cx, cy`.
   Koeficijenti distorzije opisuju radijalnu (`k1, k2, k3`) i tangencijalnu (`p1, p2`) distorziju sočiva. RMS greška
   reprojekcije je **1,00 px**.

```
Matrica kamere:                        Koeficijenti distorzije (k1, k2, p1, p2, k3):
[[1156.46     0.00   671.32]           [-0.2467, -0.0254, -0.0007, 0.0001, 0.0107]
 [   0.00  1151.27   389.22]
 [   0.00     0.00     1.00]]
```

4. **Korekcija distorzije** ([pipeline.py:53-54](pipeline.py#L53-L54)): `cv2.undistort` se primenjuje samo na
   kadrove kalibrisane kamere (1280x720). Video snimci 960x540 su sa druge kamere, a za nju nema slika šahovske table.

Korekcija primenjena na `calibration1.jpg`. Ova slika nije korišćena za kalibraciju, pa je nezavisna provera: linije
table koje je radijalna distorzija iskrivila sada su prave.

![Šahovska tabla bez distorzije](docs/calibration.jpg)

### Pipeline (pojedinačne slike)

#### 1. Priložite primer slike sa ispravljenom distorzijom.

Ista korekcija je prvi filter za svaki kadar. Na `test1.jpg` razlika se najviše vidi na ivicama slike: hauba na dnu
i belo vozilo desno menjaju oblik i položaj.

![Slika puta bez distorzije](docs/undistort.jpg)

#### 2. Opišite kako (i navedite gde u kodu) ste koristili transformacije boja, gradijente ili druge metode za kreiranje binarne slike dobijene pragovanjem. Priložite primer dobijene binarne slike.

#### 3. Opišite kako (i navedite gde u kodu) ste izvršili perspektivnu transformaciju i priložite primer transformisane slike.

#### 4. Opišite kako (i navedite gde u kodu) ste identifikovali piksele linija trake i fitovali njihove pozicije polinomom.

#### 5. Opišite kako (i navedite gde u kodu) ste izračunali poluprečnik zakrivljenosti trake i poziciju vozila u odnosu na centar.

#### 6. Priložite primer slike sa rezultatom iscrtanim nazad na put, tako da je oblast trake jasno označena.

### Pipeline (video)

#### 1. Priložite link ka svom finalnom izlaznom videu. Vaš pipeline treba da radi prihvatljivo dobro na celom projektnom videu (blago treperenje linija je u redu, ali bez katastrofalnih grešaka koje bi dovele do toga da automobil sleti sa puta!).

### Diskusija

#### 1. Ukratko prodiskutujte probleme / poteškoće sa kojima ste se suočili tokom implementacije ovog projekta. Gde će vaš pipeline verovatno otkazati? Šta biste mogli da uradite da ga učinite robusnijim?
