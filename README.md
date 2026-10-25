### Izveštaj / README

#### 1. Priložite izveštaj koji obuhvata sve tačke kriterijuma ocenjivanja i način na koji ste odgovorili na svaku od njih.

Ovaj README je ujedno i izveštaj. Za svaku tačku kriterijuma u nastavku su opisani postupak, mesto u kodu i primer
rezultata. Sve slike i obrađeni snimci nalaze se u folderu [docs/](docs/).

Projekat čine tri fajla:

- [src/pipeline.py](src/pipeline.py) sadrži ceo pipeline. Svaki kadar prolazi kroz isti niz koraka, a redom ih
  poziva klasa `LaneDetector`.
- [main.py](main.py) prima sliku, folder sa slikama ili video i čuva rezultat.
- [src/make_docs.py](src/make_docs.py) pravi sve slike i snimke koji se koriste u ovom izveštaju.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py sources/test_images/test1.jpg           # -> output_images/test1.jpg
python main.py sources/test_images/                    # sve slike u folderu
python main.py sources/test_videos/project_video03.mp4 # -> output_videos/project_video03.mp4
python src/make_docs.py                                # ponovo pravi slike i snimke u docs/
```

Redosled koraka se u jednom detalju razlikuje od šablona: perspektivnu transformaciju radim **pre** pragovanja.
Zašto je tako, objašnjeno je u tački 2 dela o pojedinačnim slikama.

### Kalibracija kamere

#### 1. Ukratko opišite kako ste izračunali matricu kamere i koeficijente distorzije. Priložite primer kalibracione slike sa ispravljenom distorzijom.

Kalibraciju radi funkcija `calibrate` ([src/pipeline.py:64-86](src/pipeline.py#L64-L86)). Poziva se samo jednom, a
rezultat se čuva u `sources/camera_cal/calib.npz`, pa se pri sledećem pokretanju samo učita.

1. **Tačke objekta** ([src/pipeline.py:70-71](src/pipeline.py#L70-L71)): šahovska tabla ima 9x6 unutrašnjih uglova,
   čije su koordinate na tabli `(x, y, 0)`. Pošto je tabla ravna (z = 0), isti niz tačaka važi za svaku sliku.
2. **Tačke slike** ([src/pipeline.py:75-80](src/pipeline.py#L75-L80)): na sivoj slici uglove pronalazi
   `cv2.findChessboardCorners`, a `cv2.cornerSubPix` ih zatim precizira ispod nivoa piksela. Tabla je pronađena na
   **17 od 20** slika. Na `calibration1.jpg`, `calibration4.jpg` i `calibration5.jpg` deo table je van kadra, pa se te
   slike preskaču.
3. **Kalibracija** ([src/pipeline.py:83](src/pipeline.py#L83)): `cv2.calibrateCamera` na osnovu svih parova tačaka
   računa parametre pinhole modela kamere (predavanje 09). Matrica kamere sadrži žižne daljine `fx, fy` i glavnu tačku
   `cx, cy`, a koeficijenti distorzije opisuju radijalnu (`k1, k2, k3`) i tangencijalnu (`p1, p2`) distorziju sočiva.
   RMS greška reprojekcije je **1,00 px**.

```
Matrica kamere:                        Koeficijenti distorzije (k1, k2, p1, p2, k3):
[[1156.46     0.00   671.32]           [-0.2467, -0.0254, -0.0007, 0.0001, 0.0107]
 [   0.00  1151.27   389.22]
 [   0.00     0.00     1.00]]
```

4. **Korekcija distorzije** ([src/pipeline.py:293-294](src/pipeline.py#L293-L294)): `cv2.undistort` se primenjuje
   samo na kadrove kalibrisane kamere (1280x720). Snimci rezolucije 960x540 potiču sa druge kamere, a za nju nemamo
   slike šahovske table.

Na slici je korekcija primenjena na `calibration1.jpg`. Ta slika nije učestvovala u kalibraciji, pa je dobra
nezavisna provera: linije table koje je radijalna distorzija savila sada su prave.

![Šahovska tabla bez distorzije](docs/calibration.jpg)

### Pipeline (pojedinačne slike)

#### 1. Priložite primer slike sa ispravljenom distorzijom.

Korekcija distorzije je prvi korak za svaki kadar. Na `test1.jpg` razlika se najbolje vidi na ivicama slike: hauba
na dnu i belo vozilo desno menjaju oblik i položaj.

![Slika puta bez distorzije](docs/undistort.jpg)

#### 2. Opišite kako (i navedite gde u kodu) ste koristili transformacije boja, gradijente ili druge metode za kreiranje binarne slike dobijene pragovanjem. Priložite primer dobijene binarne slike.

Binarnu sliku pravi funkcija `binarize` ([src/pipeline.py:109-120](src/pipeline.py#L109-L120)), a njeni parametri
su u [src/pipeline.py:36-39](src/pipeline.py#L36-L39).

**Zašto prvo pogled odozgo.** U pogledu odozgo (tačka 3) linija trake je svuda iste širine, 10-15 cm, odnosno
17-26 px, jer jedan piksel poprečno na put odgovara 5,8 mm. Veličinu filtera zato mogu da zadam u centimetrima i ona
važi podjednako kod vozila i 30 m ispred njega. Uz to, sve što je iznad puta (nebo, drveće, druga vozila) ispada iz
slike.

Koraci:

1. **Gausov filter 5x5** uklanja šum (predavanje 02).
2. **Prelazak iz BGR u LAB.** L je svetlina, a b plavo-žuta osa, na kojoj se žuta boja izdvaja i na suncu i u senci.
   Prostori boja i filtriranje po boji obrađeni su u predavanjima 00 i 06, gde je za izdvajanje boje korišćen HSV.
   Ja sam izabrao LAB, jer kanal b direktno meri koliko je piksel žut, pa je za žutu boju dovoljan jedan prag, nezavisno
   od svetline.
3. **Morfološki top-hat**: `tophat = I - opening(I)`. Morfološko filtriranje se u predavanju 06 koristi za
   uklanjanje sitnih izolovanih piksela, a top-hat je operacija izvedena iz istog otvaranja. Otvaranje (opening)
   horizontalnim kernelom 1x61 (35 cm) briše svaku svetlu strukturu užu od 35 cm, pa razlika zadržava upravo njih, a to
   je boja na kolovozu. Široke svetle površine (svetao beton, belo vozilo) i tamne strukture (spojevi od katrana,
   senke, ivica između dve vrste asfalta) ne daju odziv. Pošto se odziv meri u odnosu na okolinu, isti prag radi i na
   tamnom asfaltu i na svetlom betonu.
4. **Pragovanje**: piksel pripada liniji ako je top-hat kanala L veći od 30 (bela i žuta boja) **ili** ako je top-hat
   kanala b veći od 8 (žuta boja, i u senci, gde joj je svetlina mala).

Pragove sam podesio na `test1-6.jpg`, `straight_lines1-2.jpg` i kadrovima iz svih šest snimaka. Na asfaltu boja u
top-hat-u kanala L dostiže 100-160, dok je na test slikama 95 % piksela pogleda odozgo ispod 21. Na svetlom betonu
kontrast je mnogo manji, pa tamo žutu liniju uglavnom nalazi sloj b.

Redovi na slici su `test5.jpg` (senke drveća na betonu), `test4.jpg` (prelaz sa betona na asfalt) i kadar iz
`challenge02.mp4` (spojevi od katrana pored linija). Kolone redom prikazuju pogled odozgo, oba top-hat odziva i
konačnu binarnu sliku:

![Binarna slika](docs/binary.jpg)

#### 3. Opišite kako (i navedite gde u kodu) ste izvršili perspektivnu transformaciju i priložite primer transformisane slike.

Transformaciju radi funkcija `perspective` ([src/pipeline.py:99-106](src/pipeline.py#L99-L106)), opis kamere je u
[src/pipeline.py:18-34](src/pipeline.py#L18-L34), a primenjuje se u
[src/pipeline.py:300-305](src/pipeline.py#L300-L305).

Trapez na putu se preslikava na pravougaonik platna 1280x720 koje predstavlja pogled odozgo
(`cv2.getPerspectiveTransform` i `cv2.warpPerspective`, predavanja 03 i 10). Na pravom putu stranice trapeza su
same linije trake, a one se sastaju u **nedoglednoj tački** (vanishing point). Zato umesto četiri ručno izabrane
tačke kameru opisujem nedoglednom tačkom i mestima na kojima linije trake seku donji red slike. Stranice trapeza idu od
tih donjih tačaka ka nedoglednoj tački, a gornja ivica je na 13,5 % rastojanja od nedogledne tačke do dna slike
(red 460).

Merenje: na `straight_lines1.jpg` i `straight_lines2.jpg` posle korekcije distorzije provukao sam pravu kroz piksele
svake linije. Dobio sam `x = -1,44 y + 1245` za levu i `x = 1,55 y - 9` za desnu liniju. One se seku u nedoglednoj
tački **(641, 419)**, a donji red slike seku na x = 207 i x = 1107. Odatle sledi:

| Izvor (slika) | Odredište (platno) |
|---|---|
| (582, 460) | (320, 0) |
| (704, 460) | (960, 0) |
| (1107, 720) | (960, 720) |
| (207, 720) | (320, 720) |

Na `straight_lines1.jpg` obe linije na platnu leže tačno na stranicama crvenog pravougaonika, vertikalne i
paralelne, što potvrđuje da je trapez dobro izabran. Pravougaonik važi samo za prav put, pa na `test2.jpg` linije
skreću i pomerene su udesno, jer je vozilo 0,35 m levo od centra trake. Međusobno su i dalje paralelne: širina trake
je oko 3,6 m celom dužinom platna. Gornji deo platna je mutniji jer je daleki put u originalnoj slici sitan pa se pri
preslikavanju razvlači, a crni uglovi na dnu su delovi platna koji padaju van kadra kamere.

![Perspektivna transformacija](docs/perspective.jpg)

Kamera 960x540 (`project_video01-02.mp4` i slike `solid*`) ima sopstveni opis, izmeren na isti način na
`solidWhiteRight.jpg`: nedogledna tačka (478, 307) i donje tačke 150 i 850.

U videu se trapez dodatno prilagođava putu: red nedogledne tačke prati nagib kamere, a u oštrim krivinama gornja
ivica se spušta, pa platno pokriva manje puta i linije ne izlaze sa strane. Oba prilagođavanja su opisana u delu o
videu.

#### 4. Opišite kako (i navedite gde u kodu) ste identifikovali piksele linija trake i fitovali njihove pozicije polinomom.

Za ovaj deo zadužene su funkcije `lane_starts` ([src/pipeline.py:123-137](src/pipeline.py#L123-L137)),
`sliding_windows` ([src/pipeline.py:140-162](src/pipeline.py#L140-L162)), `around_fit`
([src/pipeline.py:165-181](src/pipeline.py#L165-L181)) i `fit_line`
([src/pipeline.py:184-206](src/pipeline.py#L184-L206)). Pozivaju se u
[src/pipeline.py:307-311](src/pipeline.py#L307-L311), a parametri su u
[src/pipeline.py:41-49](src/pipeline.py#L41-L49).

1. **Histogram** (histogram, predavanje 02; detekcija trake histogramom i kliznim prozorima, predavanje 10): kolone
   donje polovine binarne slike se sabiraju i zaglađuju. Početke dve linije tražim kao par kolona koji zajedno ima
   najviše piksela, između kojih je vozilo i koje su razmaknute za širinu trake (2,5-4,3 m, s prednošću parova blizu
   3,7 m). Prosto uzimanje najvišeg vrha sa svake strane ne radi kada je desna linija isprekidana, a pored nje na
   betonu postoji pukotina ili mrlja. Na `test1.jpg` obe imaju približno isti broj piksela i tek uslov o širini trake
   bira pravu liniju.
2. **Klizni prozori**: svaku liniju odozdo naviše prati 9 prozora, visine 80 px i širine ±100 px. Ako u prozoru ima
   više od 50 piksela, sledeći prozor se centrira na njihov srednji x. U prekidu isprekidane linije prozor nastavlja u
   pravcu poslednjeg pomaka ([src/pipeline.py:157-160](src/pipeline.py#L157-L160)), pa ne gubi liniju u krivini.
3. **Fit metodom RANSAC** (predavanje 04): model je polinom drugog reda `x = Ay² + By + C`. x je funkcija od y jer su
   linije skoro vertikalne, pa kao funkcija od x ne bi imale jednu vrednost. U svakoj od 250 iteracija (broj iz
   predavanja 04) bira se po jedan piksel iz svake trećine linije, sortirane po y, i kroz te tri tačke provlači se
   parabola. Pikseli bliži od 30 px su inlieri. Pobeđuje parabola sa najviše inliera, a konačni fit se računa metodom
   najmanjih kvadrata (`np.polyfit`) samo na njenim inlierima. Svih 250 parabola računa se odjednom pomoću numpy-ja, pa
   je ovo približno brzo kao jedan običan fit.
4. **Da li je to uopšte linija?** Linija trake je tanka, pa skoro svi pikseli oko nje leže na njoj: na
   `project_video03.mp4`, `challenge01.mp4` i `challenge02.mp4` inlieri kod 99 % linija čine bar 94 % piksela, a
   nikad manje od 89 %.
   Sunčeve mrlje i lišće, s druge strane, popune ceo prozor. Ako je inliera manje od 60 %, smatram da u tom kadru
   linije nema (kod tako odbačenih „linija“ na `challenge03.mp4` medijana udela inliera je 44 %). Liniji treba
   i najmanje 300 piksela.
5. **Sledeći kadar videa** (`around_fit`): prozori širine ±60 px idu odozdo naviše duž polinoma iz prethodnog kadra.
   Svaki prozor se pomera u stranu za onoliko koliko su se pikseli u prozoru ispod njega udaljili od prethodnog
   polinoma, pa se prati i linija koja počne da se savija više nego u prethodnom kadru. Sa fiksnim pojasom od ±60 px
   takve linije su se gubile na početku krivine (`challenge03.mp4`, kadrovi 210-240): u pojasu bi ostao samo donji
   deo linije, a gornji deo fita bi nastavio pravo kroz šum. Posle odbačenog kadra pretraga ponovo kreće od kliznih
   prozora.

Levo su klizni prozori (zeleno) na `test3.jpg`: pikseli leve linije su crveni, desne plavi, a polinomi žuti. Desno je
pojas pretrage oko prethodnog fita:

![Pikseli linija i fit polinomom](docs/fit.jpg)

Zašto RANSAC, a ne samo najmanji kvadrati: na ovom kadru iz `challenge03.mp4` desni prozor je pokupio i deo šuma pored
linije. Najmanji kvadrati vuku parabolu ka svakom pikselu, dok RANSAC drži krivu na pikselima koji zaista leže duž
jedne parabole:

![Najmanji kvadrati i RANSAC](docs/ransac.jpg)

#### 5. Opišite kako (i navedite gde u kodu) ste izračunali poluprečnik zakrivljenosti trake i poziciju vozila u odnosu na centar.

Računanje je u funkcijama `curvature` ([src/pipeline.py:237-245](src/pipeline.py#L237-L245)) i
`curvature_and_offset` ([src/pipeline.py:248-253](src/pipeline.py#L248-L253)). Razmera je zadata u
[src/pipeline.py:28-29](src/pipeline.py#L28-L29) i u funkciji `ym_per_px`
([src/pipeline.py:94-96](src/pipeline.py#L94-L96)), a položaj vozila se računa u
[src/pipeline.py:307](src/pipeline.py#L307).

**Iz piksela u metre.**

- Poprečno na put: traka je široka 3,7 m (američki standard, 12 stopa), a na platnu zauzima 640 px, pa je
  1 px = 5,8 mm.
- Duž puta razmera sledi iz kalibracije (pinhole model, predavanje 09). Tačka na putu u redu slike y udaljena je
  `Z = h·fy / (y - y_vp)`, gde je h visina kamere, a `y_vp = 419` red nedogledne tačke. U donjem redu traka je široka
  900 px, pa iz `900 = 3,7·fx / Z` dobijam `Z = 4,75 m` i h = 1,24 m. Gornja ivica trapeza je na 13,5 % rastojanja od
  nedogledne tačke do dna, dakle na `4,75 / 0,135 = 35,2 m`. Platno zato pokriva **30,4 m** puta, i 1 px = 4,2 cm.
  Pošto je trapez na putu zapravo pravougaonik, platno je umanjen pogled odozgo i ova razmera važi svuda na njemu.
  Kada se platno u oštroj krivini skrati, `ym_per_px` na isti način računa razmeru za novu gornju ivicu.
- Nezavisna provera: isprekidana linija se na platnu ponavlja na svakih 338-365 px, odnosno 14,1-15,2 m. Na
  autoputevima u Kaliforniji crta je duga 12 stopa, a razmak 36 stopa, što ukupno daje 14,6 m.

**Poluprečnik krivine.** Polinom prevodim u metre sa `A_m = A·xm/ym²` i `B_m = B·xm/ym`. Njegova krivina u donjem
redu, kod vozila, je `κ = 2·A_m / (1 + (2·A_m·y + B_m)²)^1.5`, a poluprečnik je `R = 1/|κ|`. Računam ga za središnju
liniju trake (srednju vrednost levog i desnog polinoma), jer tako dobijam jednu vrednost sa manje šuma nego za bilo
koju liniju posebno.

**Položaj vozila.** Kamera je na sredini vozila, pa je vozilo na sredini donjeg reda slike. Tu tačku preslikavam
istom matricom na platno i dobijam x = 628, a ne 640, jer trapez nije savršeno simetričan. Pomeraj je
`(car_x - centar trake na dnu) · xm`, pozitivan kada je vozilo desno od centra.

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

Kroz ceo `project_video03.mp4` poluprečnik u krivinama je uglavnom 740-1350 m. U prvoj krivini medijana je 1000 m, a
Udacity materijal iz kog ovaj snimak potiče za nju navodi otprilike 1 km. Na pravom delu, otprilike od 12. do 25.
sekunde, poluprečnik prelazi 5 km. Vozilo se kreće najviše 0,55 m levo od centra trake:

![Poluprečnik krivine i pomeraj vozila kroz project_video03.mp4](docs/measurements.png)

#### 6. Priložite primer slike sa rezultatom iscrtanim nazad na put, tako da je oblast trake jasno označena.

Iscrtavanje radi funkcija `draw_lane` ([src/pipeline.py:256-273](src/pipeline.py#L256-L273)). Na praznom platnu
oblast između dva polinoma boji se zeleno, a obe linije se crtaju duž polinoma kao debele crvene krive. Platno se
zatim inverznom matricom `Minv` vraća u perspektivu kamere i meša sa kadrom pomoću `cv2.addWeighted`. Poluprečnik i
pomeraj ispisuju se u gornjem levom uglu.

![Rezultati na test slikama](docs/result.jpg)

### Pipeline (video)

#### 1. Priložite link ka svom finalnom izlaznom videu. Vaš pipeline treba da radi prihvatljivo dobro na celom projektnom videu (blago treperenje linija je u redu, ali bez katastrofalnih grešaka koje bi dovele do toga da automobil sleti sa puta!).

**Glavni video: [docs/project_video03.mp4](docs/project_video03.mp4)**

Obradio sam svih šest snimaka (`python src/make_docs.py`, ili `python main.py <video>` za pojedinačan snimak):

| Video | Kamera | Kadrova | Kadrova sa trakom | Napomena |
|---|---|---|---|---|
| [project_video01.mp4](docs/project_video01.mp4) | 960x540 | 221 | 221 | nijedan odbačen kadar |
| [project_video02.mp4](docs/project_video02.mp4) | 960x540 | 681 | 681 | nijedan odbačen kadar |
| [project_video03.mp4](docs/project_video03.mp4) | 1280x720 | 1260 | 1260 | nijedan odbačen kadar |
| [challenge01.mp4](docs/challenge01.mp4) | 1280x720 | 251 | 251 | nijedan odbačen kadar |
| [challenge02.mp4](docs/challenge02.mp4) | 1280x720 | 484 | 484 | 2 odbačena kadra, zadržana je prethodna traka |
| [challenge03.mp4](docs/challenge03.mp4) | 1280x720 | 1199 | 1096 (91 %) | bez trake u gustoj izmaglici (kadrovi 876-892, 0,7 s) i u drugoj ukosnici (kadrovi 1023-1108, 3,4 s), videti diskusiju |

Na procesoru laptopa glavni video se obrađuje brzinom od oko 34 kadra u sekundi, što je brže od realnog vremena
(25 kadrova u sekundi).

![Kadrovi iz project_video03.mp4](docs/video_project.jpg)

U odnosu na obradu pojedinačne slike, video koristi i informaciju iz prethodnih kadrova. To je u funkciji `update`
([src/pipeline.py:318-348](src/pipeline.py#L318-L348)), sa proverama u `plausible`
([src/pipeline.py:350-360](src/pipeline.py#L350-L360)), i u prilagođavanju platna u
[src/pipeline.py:298-304](src/pipeline.py#L298-L304). Parametri su u [src/pipeline.py:51-61](src/pipeline.py#L51-L61).

1. **Praćenje**: pikseli linija traže se oko polinoma iz prethodnog kadra (tačka 5 u delu o pikselima linija).
2. **Provera ispravnosti**: novi par linija prihvata se samo ako liči na traku:
   - traka je kod vozila široka 2,5-4,3 m (na pet snimaka koji rade bez greške izmerena širina nikad ne prelazi
     4,12 m),
   - širina, merena poprečno na traku, ne menja se duž platna za više od 2,5 m,
   - širina kod vozila se u odnosu na prethodni kadar ne menja za više od 0,5 m,
   - vozilo je u traci (pomeraj manji od 1,2 m),
   - obe linije se savijaju slično: njihove krivine `κ` (formula u tački 5 iznad) razlikuju se za manje od 0,01 1/m.
     Ovde je bitno uzeti celu formulu. Poređenje samo koeficijenta `A` ne valja u oštrim krivinama, gde linije idu
     dijagonalno preko platna: tamo dve paralelne linije imaju različito `A`, pa bi i dobri parovi bili odbijeni.

   Ako kadar ne prođe proveru, zadržava se prethodna traka, a u sledećem kadru pretraga kreće od kliznih prozora.
   Posle 10 odbačenih kadrova zaredom traka se više ne prikazuje.
3. **Jedna dobra linija** ([src/pipeline.py:324-329](src/pipeline.py#L324-L329)): ako par ne prođe proveru ili jedna
   linija nedostaje (prekid isprekidane linije, izbledela boja, vozilo preko linije), zadržava se linija sa više
   piksela, a druga se crta paralelno sa njom, na poslednjoj poznatoj širini trake. Paralelnost se meri duž normale na
   krivu (`parallel`, [src/pipeline.py:217-222](src/pipeline.py#L217-L222)), a ne prostim pomeranjem u stranu, što je
   bitno u oštrim krivinama.
4. **Usrednjavanje**: koeficijenti polinoma se usrednjavaju eksponencijalnim pokretnim prosekom, sa težinom 0,25 za
   novi kadar. To uklanja treperenje između kadrova i predstavlja jednostavniju varijantu Kalmanovog filtera iz
   predavanja 07.
5. **Nagib kamere** ([src/pipeline.py:340-343](src/pipeline.py#L340-L343)): u ispravnom pogledu odozgo linije trake
   su paralelne. Ako se ka vrhu skupljaju, nedogledna tačka je niže nego što je pretpostavljeno, pa se u svakom kadru
   pomera naniže za 0,5 px po metru razlike u širini, a ako se šire, pomera se naviše. To radim samo na blagim
   krivinama (poluprečnik veći od 500 m), gde parabola dobro opisuje linije, a nedogledna tačka ne sme da se udalji
   više od ±30 px od izmerene. Na `project_video03.mp4` ostaje u redovima 415-424 (izmereno je 419). Na
   `challenge02.mp4` se za oko 7 s pomeri sa 419 na 435-443, što odgovara nedoglednoj tački koja se vidi na njegovim
   kadrovima (oko 445). Posle toga se širina trake duž platna menja za samo 0,15 m (medijana). Bez ovog koraka linije
   se tamo skupljaju (medijana promene 1,35 m), platno nije pravi pogled odozgo, a poluprečnik ispada potcenjen
   (medijana 647 m umesto 1068 m).
6. **Domet pogleda prema krivini** ([src/pipeline.py:298-304](src/pipeline.py#L298-L304), `look_ahead`
   [src/pipeline.py:89-91](src/pipeline.py#L89-L91)): u ukosnici linije izlaze iz platna od 30 m kroz njegove
   stranice. Zato gornja ivica trapeza zavisi od poluprečnika iz prethodnog kadra: platno pokriva 30 m puta za
   poluprečnike iznad 300 m, a sve manje kako se krivina oštri, do oko 11 m pri poluprečniku od 30 m. Domet se menja
   polako (najviše 0,005 po kadru), a prethodni polinomi se na novo platno prenose homografijom `M_novo · Minv_staro`
   (`remap`, [src/pipeline.py:209-214](src/pipeline.py#L209-L214)), pa se praćenje nastavlja bez skoka. Na prvih pet
   snimaka platno sve vreme ostaje na 30,4 m, pa tamo ovo ništa ne menja. Na `challenge03.mp4` platno je kraće na 900
   od 1199 kadrova, a najkraće je 11,1 m.

Kadrovi iz ostalih snimaka. Poslednji kadar pokazuje grešku na `challenge03.mp4` u drugoj ukosnici:

![Kadrovi iz ostalih snimaka](docs/video_other.jpg)

### Diskusija

#### 1. Ukratko prodiskutujte probleme / poteškoće sa kojima ste se suočili tokom implementacije ovog projekta. Gde će vaš pipeline verovatno otkazati? Šta biste mogli da uradite da ga učinite robusnijim?

**Problemi na koje sam naišao i kako sam ih rešio**

1. **Gradijenti su hvatali previše.** Prva verzija je kombinovala Sobel x, pravac gradijenta i pragove u HLS prostoru.
   Na projektnom videu je radila, ali je na `challenge02.mp4` Sobel hvatao i spojeve od katrana, ivicu između dve vrste
   asfalta i senku ograde, jer su to sve jake vertikalne ivice. Linija trake, međutim, nije samo ivica nego uska svetla
   traka, a upravo to izdvaja morfološki top-hat:

   ![Sobel x u poređenju sa top-hat-om](docs/sobel_vs_tophat.jpg)

2. **Ručno biran trapez i pretpostavljena razmera.** Umesto da pogađam četiri tačke, izmerio sam nedoglednu tačku, a
   razmeru duž puta sam izveo iz kalibracije umesto da je pretpostavim. Isprekidana linija potvrđuje dobijeni rezultat.
3. **Nagib kamere nije stalan.** Sa fiksnim trapezom linije na `challenge02.mp4` su se na platnu skupljale ka vrhu, pa
   je moja prva provera, koja je tražila paralelne linije, odbacivala 391 od 484 kadra. Problem je rešila procena
   nedogledne tačke tokom praćenja (deo o videu, tačka 5).
4. **Planinski put** (`challenge03.mp4`). Prva verzija je crtala traku na samo 79 % kadrova, i to ne uvek tačno. Za
   svaki kadar sam beležio koja provera pada i zašto, pa sam izmene uvodio jednu po jednu i posle svake proveravao svih
   šest snimaka, da se ostali ne bi pokvarili. Tako su nastali RANSAC sa udelom inliera, traženje početaka linija u
   paru, domet pogleda koji prati krivinu, dodatne provere ispravnosti i paralelna linija merena duž normale. Na kraju
   sam pregledao svaki deseti kadar sva tri challenge snimka i našao još tri greške:
   - na početku krivine (kadrovi 210-240 i 280-290) desna linija je bila iscrtana na travi pored puta, jer je fiksni
     pojas pretrage gubio liniju koja počinje da se savija. Rešenje su prozori duž prethodnog fita (tačka 5 u delu o
     pikselima linija);
   - u gustoj izmaglici (kadrovi 880-905) ivica ograde je uzimana za desnu liniju, pa je traka klizila sa puta. Sa
     novim praćenjem toga više nema: ti kadrovi ostaju bez trake umesto da dobiju pogrešnu;
   - u ukosnicama su dobri parovi bili odbijani, jer je provera poredila samo koeficijent `A` umesto prave krivine
     (deo o videu, tačka 2).

   Sada se traka crta na 91 % kadrova. Kao meru pogrešnih traka brojao sam kadrove van druge ukosnice u kojima bi
   vozilo bilo više od 0,8 m od centra trake. Takvih je ranije bilo 11, a sada ih nema. Bez RANSAC-a (sa običnim
   najmanjim kvadratima) bilo bi ih 17. Sa fiksnim platnom od 30 m ih takođe ne bi bilo, ali bi traka bila iscrtana na
   manje kadrova (1058 umesto 1096). U samoj ukosnici ovakav pomeraj je stvaran, jer vozač seče krivinu uz središnju
   liniju.
5. **Dve različite kamere.** Za snimke 960x540 nema slika šahovske table, pa se na njima ne radi korekcija distorzije,
   a imaju i svoj trapez. Metri su kod njih samo približni, jer visina i žižna daljina te kamere nisu poznate, pa sam
   pretpostavio istu razmeru.
6. **Ponovljivost rezultata.** RANSAC bira slučajne uzorke, pa svaki detektor ima svoj generator slučajnih brojeva sa
   fiksnim početnim stanjem (seed). Zato ista slika ili isti video uvek daju potpuno isti rezultat.

**Gde pipeline otkazuje**

- **Druga ukosnica na `challenge03.mp4`** (kadrovi 1023-1108). Put skreće za skoro 180°, pa je traka ispred vozila
  van slike, a kamera vidi uglavnom suprotnu traku i ogradu. Jako sunce i zamućena slika brišu belu liniju. Tamo gde
  se obe linije ipak nađu, one izlaze iz platna kroz bočnu stranu: parabola `x = f(y)` ne može da prati put koji
  skreće u stranu, pa se dve krive van vidljivog dela razilaze. Provere ove kadrove odbacuju, pa se umesto pogrešne
  trake ne crta ništa.
- **Gusta izmaglica** (kadrovi 876-892 na `challenge03.mp4`): žuta linija gotovo nestaje, pa nema dovoljno piksela
  linije, a jedina svetla traka desno je ivica ograde.
- **Promena trake**: praćenje se drži starih linija sve dok ih provera ispravnosti ne odbaci.
- **Noć, kiša, sneg i izbledela boja**, kao i svetli uski objekti tik uz liniju.
- **Usponi i padovi**: pogled odozgo pretpostavlja ravan put, a procena nagiba to nadoknađuje samo delimično.

**Kako bi se mogao poboljšati**

- **Kalmanov filter** umesto pokretnog proseka (predavanje 07). On modeluje koliko brzo se traka menja i daje meru
  pouzdanosti procene, pa bi provere mogle da zavise od nje.
- **Bogatiji model trake**: parabola ne može da opiše S-krivinu ili ukosnicu. Splajn, klotoida ili 3D model puta bi
  mogli da prate i takve puteve.
- **Automatsko određivanje nedogledne tačke** za nepoznatu kameru, pomoću Hafove transformacije linija trake na
  prvim kadrovima (predavanje 04).
- **Korišćenje ostalih linija** (suprotne trake, ivice puta): kada jedna linija moje trake nije vidljiva, njihovo
  rastojanje bi i dalje pokazivalo gde se nalazi.
- **Upozorenje o napuštanju trake** na osnovu izmerenog pomeraja (predavanje 10).
