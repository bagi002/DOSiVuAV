# Detekcija saobraćajnih traka (DOSiVuAV)

### Izveštaj / README

#### 1. Priložite izveštaj koji obuhvata sve tačke kriterijuma ocenjivanja i način na koji ste odgovorili na svaku od njih.

Upravo ga čitate! Svaka tačka kriterijuma je opisana u nastavku, zajedno sa lokacijom koda koji je implementira i
primerom rezultata. Sve slike su u [docs/](docs/).

- [src/pipeline.py](src/pipeline.py) je pipeline: svaki kadar prolazi kroz isti niz filtera, a klasa `LaneDetector`
  ih poziva redom.
- [main.py](main.py) prima sliku, folder sa slikama ili video i čuva rezultat.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py sources/test_images/test1.jpg           # -> output_images/test1.jpg
python main.py sources/test_images/                    # sve slike u folderu
python main.py sources/test_videos/project_video03.mp4 # -> output_videos/project_video03.mp4
```

Jedna razlika u odnosu na redosled iz šablona: perspektivna transformacija se radi **pre** pragovanja. Razlog je
objašnjen u tački 2 pipeline-a za pojedinačne slike.

### Kalibracija kamere

#### 1. Ukratko opišite kako ste izračunali matricu kamere i koeficijente distorzije. Priložite primer kalibracione slike sa ispravljenom distorzijom.

Kod je funkcija `calibrate` ([src/pipeline.py:36-58](src/pipeline.py#L36-L58)). Detektor je poziva jednom, a rezultat se
čuva u `sources/camera_cal/calib.npz`.

1. **Tačke objekta** ([src/pipeline.py:42-43](src/pipeline.py#L42-L43)): šahovska tabla ima 9x6 unutrašnjih uglova.
   Njihove koordinate na tabli su `(x, y, 0)` u mreži. Tabla je ravna (z = 0), pa se isti niz koristi za svaku sliku.
2. **Tačke slike** ([src/pipeline.py:47-52](src/pipeline.py#L47-L52)): `cv2.findChessboardCorners` traži uglove na sivoj
   slici, a `cv2.cornerSubPix` ih precizira na nivo ispod piksela. Uglovi su pronađeni na **17 od 20** slika. Na
   `calibration1.jpg`, `calibration4.jpg` i `calibration5.jpg` deo table je van kadra, pa se te slike preskaču.
3. **Kalibracija** ([src/pipeline.py:55](src/pipeline.py#L55)): `cv2.calibrateCamera` prilagođava pinhole model kamere
   (predavanje 09) svim parovima tačaka. Matrica kamere sadrži žižne daljine `fx, fy` i glavnu tačku `cx, cy`.
   Koeficijenti distorzije opisuju radijalnu (`k1, k2, k3`) i tangencijalnu (`p1, p2`) distorziju sočiva. RMS greška
   reprojekcije je **1,00 px**.

```
Matrica kamere:                        Koeficijenti distorzije (k1, k2, p1, p2, k3):
[[1156.46     0.00   671.32]           [-0.2467, -0.0254, -0.0007, 0.0001, 0.0107]
 [   0.00  1151.27   389.22]
 [   0.00     0.00     1.00]]
```

4. **Korekcija distorzije** ([src/pipeline.py:94-95](src/pipeline.py#L94-L95)): `cv2.undistort` se primenjuje samo na
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

Kod je funkcija `binarize` ([src/pipeline.py:71-82](src/pipeline.py#L71-L82)), a njeni parametri su u
[src/pipeline.py:30-33](src/pipeline.py#L30-L33).

**Zašto pogled odozgo ide prvi.** Na pogledu odozgo (tačka 3) linija trake je svuda iste širine, 10-15 cm, što je
17-26 px, jer je jedan piksel poprečno na put 5,8 mm. Veličina filtera zato može da se izabere u centimetrima i radi
isto i kod vozila i 30 m ispred njega. Pored toga, sve iznad puta (nebo, drveće, druga vozila) više nije na slici.

Koraci:

1. **Gausov filter 5x5** uklanja šum (predavanje 02).
2. **BGR → LAB.** L je svetlina. b je plavo-žuta osa, na kojoj se žuta boja ističe i na suncu i u senci (prostori
   boja i filtriranje po boji, predavanja 00 i 06).
3. **Morfološki top-hat** (morfološko filtriranje, predavanje 06): `tophat = I - opening(I)`. Otvaranje (opening)
   horizontalnim kernelom 1x61 (35 cm) uklanja svaku svetlu strukturu užu od 35 cm. Razlika zato zadržava upravo te
   strukture: boju na putu. Široke svetle površine (svetao beton, belo vozilo) i tamne strukture (spojevi od katrana,
   senke, ivica između dve vrste asfalta) ne daju odziv. Odziv se meri u odnosu na lokalnu pozadinu, pa isti prag
   radi i na tamnom asfaltu i na svetlom betonu.
4. **Pragovanje**: piksel pripada liniji ako je top-hat kanala L veći od 30 (bela i žuta boja) **ili** je top-hat
   kanala b veći od 8 (žuta boja, i u senci, gde joj je svetlina mala).

Pragovi su podešeni na `test1-6.jpg`, `straight_lines1-2.jpg` i kadrovima iz svih šest snimaka. Na asfaltu boja
dostiže vrednosti 100-160 u top-hat-u kanala L, dok je na test slikama 95 % svih piksela pogleda odozgo ispod 21. Na
svetlom betonu kontrast je mnogo manji, i tu žutu liniju nalazi uglavnom sloj b.

Redovi ispod prikazuju `test5.jpg` (senke drveća na betonu), `test4.jpg` (prelaz sa betona na asfalt) i kadar iz
`challenge02.mp4` (spojevi od katrana pored linija). Kolone prikazuju pogled odozgo, oba top-hat odziva i konačnu
binarnu sliku:

![Binarna slika](docs/binary.jpg)

#### 3. Opišite kako (i navedite gde u kodu) ste izvršili perspektivnu transformaciju i priložite primer transformisane slike.

Kod je funkcija `perspective` ([src/pipeline.py:61-68](src/pipeline.py#L61-L68)), a opis kamere je u
[src/pipeline.py:18-28](src/pipeline.py#L18-L28). Koristi se u [src/pipeline.py:96-97](src/pipeline.py#L96-L97).

Trapez na putu se preslikava na pravougaonik fiksnog platna 1280x720 koje gleda odozgo (`cv2.getPerspectiveTransform`
i `cv2.warpPerspective`, predavanja 03 i 10). Na pravom putu stranice trapeza su linije trake, a one se seku u
**nedoglednoj tački** (vanishing point). Zato umesto četiri ručno izabrane tačke kameru opisujem njenom nedoglednom
tačkom i x koordinatama na kojima linije trake seku donji red slike. Stranice trapeza idu od tih donjih tačaka do
nedogledne tačke, a gornja ivica je na 13,5 % puta naniže od nedogledne tačke (red 460).

Merenje: na `straight_lines1.jpg` i `straight_lines2.jpg` bez distorzije fitovao sam pravu kroz piksele linija.
Rezultat je `x = -1,44 y + 1245` (leva) i `x = 1,55 y - 9` (desna), koje se seku u nedoglednoj tački **(641, 419)**.
U donjem redu linije su na x = 207 i x = 1107. Iz toga sledi:

| Izvor (slika) | Odredište (platno) |
|---|---|
| (582, 460) | (320, 0) |
| (704, 460) | (960, 0) |
| (1107, 720) | (960, 720) |
| (207, 720) | (320, 720) |

Provera: na `straight_lines1.jpg` obe linije su na platnu vertikalne i paralelne, a na `test2.jpg` se krivina vidi
kao dve paralelne krive.

![Perspektivna transformacija](docs/perspective.jpg)

Kamera 960x540 (`project_video01-02.mp4` i slike `solid*`) ima svoj opis, izmeren na isti način na
`solidWhiteRight.jpg`: nedogledna tačka (478, 307) i donje tačke 150 i 850.

#### 4. Opišite kako (i navedite gde u kodu) ste identifikovali piksele linija trake i fitovali njihove pozicije polinomom.

#### 5. Opišite kako (i navedite gde u kodu) ste izračunali poluprečnik zakrivljenosti trake i poziciju vozila u odnosu na centar.

#### 6. Priložite primer slike sa rezultatom iscrtanim nazad na put, tako da je oblast trake jasno označena.

### Pipeline (video)

#### 1. Priložite link ka svom finalnom izlaznom videu. Vaš pipeline treba da radi prihvatljivo dobro na celom projektnom videu (blago treperenje linija je u redu, ali bez katastrofalnih grešaka koje bi dovele do toga da automobil sleti sa puta!).

### Diskusija

#### 1. Ukratko prodiskutujte probleme / poteškoće sa kojima ste se suočili tokom implementacije ovog projekta. Gde će vaš pipeline verovatno otkazati? Šta biste mogli da uradite da ga učinite robusnijim?
