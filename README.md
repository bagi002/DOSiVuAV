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

Kod je funkcija `calibrate` ([src/pipeline.py:48-70](src/pipeline.py#L48-L70)). Detektor je poziva jednom, a rezultat se
čuva u `sources/camera_cal/calib.npz`.

1. **Tačke objekta** ([src/pipeline.py:54-55](src/pipeline.py#L54-L55)): šahovska tabla ima 9x6 unutrašnjih uglova.
   Njihove koordinate na tabli su `(x, y, 0)` u mreži. Tabla je ravna (z = 0), pa se isti niz koristi za svaku sliku.
2. **Tačke slike** ([src/pipeline.py:59-64](src/pipeline.py#L59-L64)): `cv2.findChessboardCorners` traži uglove na sivoj
   slici, a `cv2.cornerSubPix` ih precizira na nivo ispod piksela. Uglovi su pronađeni na **17 od 20** slika. Na
   `calibration1.jpg`, `calibration4.jpg` i `calibration5.jpg` deo table je van kadra, pa se te slike preskaču.
3. **Kalibracija** ([src/pipeline.py:67](src/pipeline.py#L67)): `cv2.calibrateCamera` prilagođava pinhole model kamere
   (predavanje 09) svim parovima tačaka. Matrica kamere sadrži žižne daljine `fx, fy` i glavnu tačku `cx, cy`.
   Koeficijenti distorzije opisuju radijalnu (`k1, k2, k3`) i tangencijalnu (`p1, p2`) distorziju sočiva. RMS greška
   reprojekcije je **1,00 px**.

```
Matrica kamere:                        Koeficijenti distorzije (k1, k2, p1, p2, k3):
[[1156.46     0.00   671.32]           [-0.2467, -0.0254, -0.0007, 0.0001, 0.0107]
 [   0.00  1151.27   389.22]
 [   0.00     0.00     1.00]]
```

4. **Korekcija distorzije** ([src/pipeline.py:221-222](src/pipeline.py#L221-L222)): `cv2.undistort` se primenjuje samo na
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

Kod je funkcija `binarize` ([src/pipeline.py:88-99](src/pipeline.py#L88-L99)), a njeni parametri su u
[src/pipeline.py:32-35](src/pipeline.py#L32-L35).

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

Kod je funkcija `perspective` ([src/pipeline.py:78-85](src/pipeline.py#L78-L85)), a opis kamere je u
[src/pipeline.py:18-30](src/pipeline.py#L18-L30). Koristi se u [src/pipeline.py:223-224](src/pipeline.py#L223-L224).

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

Kod je `lane_starts` ([src/pipeline.py:102-116](src/pipeline.py#L102-L116)), `sliding_windows`
([src/pipeline.py:119-141](src/pipeline.py#L119-L141)) i `fit_line`
([src/pipeline.py:144-166](src/pipeline.py#L144-L166)). Pozivaju se u
[src/pipeline.py:226-229](src/pipeline.py#L226-L229), a parametri su u
[src/pipeline.py:37-45](src/pipeline.py#L37-L45).

1. **Histogram** (histogram, predavanje 02; detekcija trake histogramom i kliznim prozorima, predavanje 10): kolone
   donje polovine binarne slike se sabiraju i zaglađuju. Dve linije počinju na paru kolona koji zajedno ima najviše
   piksela linija, ima vozilo između sebe i udaljen je za širinu trake (2,5-4,3 m, prednost imaju parovi blizu 3,7 m).
   Uzimanje najvišeg vrha sa svake strane ne radi kada je desna linija isprekidana, a na betonu pored nje postoji
   pukotina ili mrlja: na `test1.jpg` obe imaju približno isti broj piksela, i tek par na pravoj udaljenosti bira
   pravu liniju.
2. **Klizni prozori**: 9 prozora, visine 80 px i širine ±100 px, prati svaku liniju odozdo naviše. Prozor skuplja
   piksele u sebi, i ako ih ima više od 50, sledeći prozor se centrira na njihov srednji x. U prekidu isprekidane
   linije prozor nastavlja u pravcu poslednjeg koraka ([src/pipeline.py:136-139](src/pipeline.py#L136-L139)), pa ne gubi
   isprekidanu liniju u krivini.
3. **Fit metodom RANSAC** (predavanje 04): model je polinom drugog reda `x = Ay² + By + C`. x je funkcija od y jer
   su linije skoro vertikalne, a kao funkcija od x ne bi imale jednu vrednost. U svakoj od 250 iteracija (broj iz
   predavanja 04) bira se po jedan piksel iz svake trećine linije, sortirane po y, i kroz te tri tačke se provlači
   parabola. Piksel na manje od 30 px od parabole je inlier. Pobeđuje parabola sa najviše inliera, a konačni fit je
   metoda najmanjih kvadrata (`np.polyfit`) samo na njenim inlierima. Svih 250 parabola se računa odjednom pomoću
   numpy-ja, pa to košta otprilike koliko i jedan fit najmanjim kvadratima.
4. **Da li je to uopšte linija?** Linija trake je tanka, pa skoro svi pikseli oko nje leže na njoj: na
   `project_video03.mp4`, `challenge01.mp4` i `challenge02.mp4` najmanje 94 % piksela svake linije su inlieri.
   Sunčeve mrlje i lišće umesto toga popunjavaju ceo prozor. Ako je inliera manje od 60 %, u tom kadru nema linije
   (na `challenge03.mp4` takve odbačene „linije“ imaju medijanu od 44 % inliera). Liniji treba i najmanje 300 piksela.
Klizni prozori (zeleno) na `test3.jpg`, sa pikselima leve linije u crvenoj, desne u plavoj boji i polinomima u žutoj:

![Pikseli linija i fit polinomom](docs/fit.jpg)

Zašto RANSAC, a ne samo najmanji kvadrati: na ovom kadru iz `challenge03.mp4` desni prozor je pokupio deo šuma pored
linije. Najmanji kvadrati savijaju parabolu prema svakom pikselu, dok RANSAC drži krivu na pikselima koji zaista leže
duž jedne parabole:

![Najmanji kvadrati i RANSAC](docs/ransac.jpg)

#### 5. Opišite kako (i navedite gde u kodu) ste izračunali poluprečnik zakrivljenosti trake i poziciju vozila u odnosu na centar.

Kod je `curvature` ([src/pipeline.py:169-177](src/pipeline.py#L169-L177)) i `curvature_and_offset`
([src/pipeline.py:180-185](src/pipeline.py#L180-L185)), razmera je u
[src/pipeline.py:28-29](src/pipeline.py#L28-L29) i `ym_per_px` ([src/pipeline.py:73-75](src/pipeline.py#L73-L75)),
a položaj vozila u [src/pipeline.py:226](src/pipeline.py#L226).

**Pikseli u metre.**

- Poprečno na put: traka je široka 3,7 m (američki standard, 12 stopa) i 640 px na platnu, pa je 1 px = 5,8 mm.
- Duž puta, razmera sledi iz kalibracije (pinhole model, predavanje 09). Tačka na putu u redu slike y je na
  udaljenosti `Z = h·fy / (y - y_vp)`, gde je h visina kamere, a `y_vp = 419` red nedogledne tačke. U donjem redu traka
  je široka 900 px, pa je `900 = 3,7·fx / Z`, odakle je `Z = 4,75 m` i h = 1,24 m. Gornja ivica trapeza je na 13,5 %
  puta naniže od nedogledne tačke, pa je udaljena `4,75 / 0,135 = 35,2 m`. Platno zato prikazuje **30,5 m** puta, i
  1 px = 4,2 cm. Trapez je pravougaonik na putu, pa je platno umanjeni pogled odozgo i ova razmera je ista svuda na
  njemu.
- Nezavisna provera: na platnu se isprekidana linija ponavlja na svakih 338-365 px, što je 14,1-15,2 m. Na
  autoputevima u Kaliforniji crta je duga 12 stopa, a razmak 36 stopa, što je ukupno 14,6 m.

**Poluprečnik krivine.** Polinom se prevodi u metre sa `A_m = A·xm/ym²` i `B_m = B·xm/ym`. Njegova krivina je
`κ = 2·A_m / (1 + (2·A_m·y + B_m)²)^1.5`, računa se u donjem redu, kod vozila, a poluprečnik je `R = 1/|κ|`. Računa
se za središnju liniju trake (srednja vrednost levog i desnog polinoma), što daje jednu vrednost sa manje šuma nego
bilo koja od linija.

**Položaj vozila.** Kamera je na sredini vozila, pa je vozilo na sredini donjeg reda slike. Njegov položaj na platnu
se dobija transformacijom te tačke istom matricom: x = 628, a ne 640, jer trapez nije potpuno simetričan. Pomeraj je
`(car_x - centar trake na dnu) · xm`, pozitivan udesno.

Rezultati na test slikama (izlaz komande `python main.py sources/test_images/`):

| Slika | Poluprečnik krivine | Pomeraj vozila |
|---|---|---|
| test1.jpg | 853 m | 0,26 m levo |
| test2.jpg | 557 m | 0,35 m levo |
| test3.jpg | 1030 m | 0,19 m levo |
| test4.jpg | 939 m | 0,38 m levo |
| test5.jpg | 787 m | 0,06 m levo |
| test6.jpg | 959 m | 0,34 m levo |
| straight_lines1.jpg | 17,5 km (pravo) | 0,07 m levo |
| straight_lines2.jpg | 7,3 km (pravo) | 0,09 m levo |

#### 6. Priložite primer slike sa rezultatom iscrtanim nazad na put, tako da je oblast trake jasno označena.

Kod je `draw_lane` ([src/pipeline.py:188-205](src/pipeline.py#L188-L205)). Na praznom platnu oblast između dva polinoma se
boji zeleno, a obe linije se crtaju duž polinoma kao debele crvene krive. Platno se inverznom matricom `Minv` vraća
na kadar i meša sa njim pomoću `cv2.addWeighted`. Poluprečnik i pomeraj se ispisuju u gornjem levom uglu.

![Rezultati na test slikama](docs/result.jpg)

### Pipeline (video)

#### 1. Priložite link ka svom finalnom izlaznom videu. Vaš pipeline treba da radi prihvatljivo dobro na celom projektnom videu (blago treperenje linija je u redu, ali bez katastrofalnih grešaka koje bi dovele do toga da automobil sleti sa puta!).

### Diskusija

#### 1. Ukratko prodiskutujte probleme / poteškoće sa kojima ste se suočili tokom implementacije ovog projekta. Gde će vaš pipeline verovatno otkazati? Šta biste mogli da uradite da ga učinite robusnijim?
