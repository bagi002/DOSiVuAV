**Projekat detekcije saobraćajnih traka**

Ciljevi / koraci ovog projekta su sledeći:

* Izračunati matricu kalibracije kamere i koeficijente distorzije na osnovu skupa slika šahovske table.
* Primeniti korekciju distorzije na sirove slike.
* Koristiti transformacije boja, gradijente itd. za kreiranje binarne slike dobijene pragovanjem (thresholding).
* Primeniti perspektivnu transformaciju kako bi se binarna slika ispravila (pogled iz ptičje perspektive, "birds-eye view").
* Detektovati piksele traka i izvršiti fitovanje kako bi se pronašle granice trake.
* Odrediti zakrivljenost trake i poziciju vozila u odnosu na centar.
* Vratiti (warp) detektovane granice trake nazad na originalnu sliku.
* Prikazati vizuelno granice trake i numeričku procenu zakrivljenosti trake i pozicije vozila.

[//]: # (Reference na slike)

[image1]: ./docs/calibration.jpg "Ispravljena distorzija"
[image2]: ./docs/undistort.jpg "Slika puta bez distorzije"
[image3]: ./docs/binary.jpg "Binarna slika"
[image4]: ./docs/perspective.jpg "Perspektivna transformacija"
[image5]: ./docs/fit.jpg "Pikseli linija i fit"
[image5b]: ./docs/ransac.jpg "Najmanji kvadrati i RANSAC"
[image6]: ./docs/measurements.png "Krivina i pomeraj kroz video"
[image7]: ./docs/result.jpg "Rezultat"
[image8]: ./docs/video_project.jpg "Kadrovi iz projektnog videa"
[image9]: ./docs/video_other.jpg "Kadrovi iz ostalih snimaka"
[image10]: ./docs/sobel_vs_tophat.jpg "Sobel i top-hat"
[video1]: ./docs/project_video03.mp4 "Video"

---

### Izveštaj / README

Slike u ovom izveštaju i obrađeni video snimci nalaze se u folderu `docs/`. Ceo pipeline je u `src/pipeline.py`, gde
klasa `LaneDetector` redom poziva sve korake nad jednim kadrom. `main.py` prima sliku, folder sa slikama ili video i
čuva rezultat u `output_images/` ili `output_videos/`, a `src/make_docs.py` ponovo pravi sve slike i snimke iz `docs/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main.py sources/test_images/test1.jpg           # jedna slika
python main.py sources/test_images/                    # ceo folder
python main.py sources/test_videos/project_video03.mp4 # video
python src/make_docs.py                                # slike i snimci za ovaj izveštaj
```

Redosled koraka se u jednom detalju razlikuje od šablona: perspektivna transformacija se radi pre pragovanja. Razlog
je objašnjen u tački 2.

### Kalibracija kamere

#### 1. Matrica kamere i koeficijenti distorzije

Kalibracija je u funkciji `calibrate()`. Na svakoj slici šahovske table `cv2.findChessboardCorners()` traži 9x6
unutrašnjih uglova, a `cv2.cornerSubPix()` ih zatim precizira na nivo ispod piksela. Svaka uspešna detekcija daje dve
stvari:

* koordinate uglova na slici (tačke slike);
* istu mrežu tačaka objekta `(0,0,0), (1,0,0), ..., (8,5,0)`. Tabla leži u ravni z = 0, pa je ova mreža ista za
  svaku sliku.

`cv2.calibrateCamera()` iz svih parova tačaka računa matricu kamere (žižne daljine i glavnu tačku) i koeficijente
radijalne i tangencijalne distorzije. Srednja greška reprojekcije je 1,00 px. Rezultat se čuva u
`sources/camera_cal/calib.npz`, pa se kalibracija računa samo pri prvom pokretanju.

Korekcija pomoću `cv2.undistort()` ispravlja jaku bačvastu distorziju. Na ispravljenoj slici ivice table, koje su na
originalu savijene, postaju prave:

![Ispravljena distorzija][image1]

### Pipeline (pojedinačne slike)

#### 1. Korekcija distorzije

Korekcija distorzije je prvi korak za svaki kadar. Na slici puta efekat je slabo vidljiv i najviše se primećuje na
ivicama, gde se hauba na dnu i belo vozilo desno pomeraju ka spolja:

![Slika puta bez distorzije][image2]

Kalibracija važi samo za kameru kojom su snimljene slike table (1280x720). Deo snimaka je rezolucije 960x540 i potiče
sa druge kamere, za koju nema slika table, pa se ti kadrovi obrađuju bez korekcije.

#### 2. Binarna slika

Binarna slika se pravi u funkciji `binarize()`, i to na pogledu odozgo, a ne na originalnoj slici. U pogledu odozgo
linija trake ima istu širinu na celoj slici, 10-15 cm, odnosno oko 20 px, pa se veličina filtera može zadati u
centimetrima i važi jednako blizu vozila i 30 m ispred njega. Pored toga, nebo, drveće i druga vozila više nisu na
slici.

Umesto fiksnih pragova na boju, binarna slika se pravi od onoga što linija fizički jeste, a to je uska traka koja je
svetlija ili žuća od asfalta sa obe strane.

* Slika se zamuti Gausovim filterom 5x5 i prebaci u LAB prostor boja. Kanal L meri svetlinu (bela i žuta boja), a
  kanal b plavo-žutu osu, na kojoj se žuta boja izdvaja i u senci, gde nije svetlija od okoline.
* Na oba kanala primenjuje se morfološki top-hat: `tophat = I - opening(I)`. Otvaranje horizontalnim kernelom
  širine 35 cm briše sve svetle strukture uže od kernela, pa razlika zadržava upravo njih. Široke svetle površine
  (svetao beton, belo vozilo) i tamne strukture (spojevi od katrana, senke, ivica između dve vrste asfalta) ne daju
  odziv.
* Piksel pripada liniji ako je top-hat kanala L veći od 30 ili top-hat kanala b veći od 8. Pošto se odziv meri u
  odnosu na lokalnu okolinu, isti pragovi rade i na tamnom asfaltu i na svetlom betonu.

Gradijenti (Sobel) su probani u prvoj verziji, ali su hvatali svaku jaku vertikalnu ivicu na putu, pa nisu korišćeni
(detaljnije u diskusiji).

Na slici su redom senke drveća na betonu, prelaz sa betona na asfalt i kadar sa spojevima od katrana pored linija.
Kolone prikazuju pogled odozgo, odziv top-hat filtera na kanalima L i b i konačnu binarnu sliku:

![Binarna slika][image3]

#### 3. Perspektivna transformacija

Matrice prave funkcija `perspective()`: `M` iz pogleda kamere u pogled odozgo i inverznu `Minv` za vraćanje
rezultata nazad (tačka 6), obe pomoću `cv2.getPerspectiveTransform()`. Sama slika se preslikava sa
`cv2.warpPerspective()`.

Trapez na putu se preslikava na pravougaonik platna 1280x720. Na ravnom putu linije trake se sastaju u nedoglednoj
tački, pa trapez nije biran ručno, tačku po tačku, nego je izveden iz geometrije kamere. Na slikama pravog puta kroz
piksele svake linije provučena je prava. Te prave se seku u nedoglednoj tački (641, 419), a donju ivicu slike seku na
x = 207 i x = 1107. Stranice trapeza idu od tih tačaka ka nedoglednoj tački, a gornja ivica je na 13,5 % rastojanja od
nedogledne tačke do dna slike. Druga kamera (960x540) je izmerena na isti način.

| Izvor | Odredište |
|:-:|:-:|
| 582, 460 | 320, 0 |
| 704, 460 | 960, 0 |
| 1107, 720 | 960, 720 |
| 207, 720 | 320, 720 |

Na pravom putu linije u pogledu odozgo izlaze vertikalne i paralelne i leže na stranicama crvenog pravougaonika. Na
putu u krivini savijaju se zajedno, a pomerene su udesno jer vozilo ne vozi tačno po sredini trake. Gornji deo platna
je mutniji, jer je daleki deo puta u originalu sitan pa se razvlači, a crni uglovi na dnu su delovi platna van kadra
kamere:

![Perspektivna transformacija][image4]

Transformacija pretpostavlja ravan put i stalan nagib kamere. Kako se u videu to menja, nedogledna tačka se procenjuje
tokom vožnje, a u oštrim krivinama platno se skraćuje (opisano u delu o videu).

#### 4. Pikseli linija i fit polinomom

Ulaz je binarna slika pogleda odozgo iz tačke 2.

Početak linija traži `lane_starts()` pomoću histograma: pikseli donje polovine slike, gde su linije najbliže vozilu i
najvertikalnije, sabiraju se po kolonama. Ne uzima se najviši vrh na svakoj strani, nego par vrhova koji zajedno imaju
najviše piksela, između kojih je vozilo i koji su razmaknuti za širinu trake. Tako pukotina ili mrlja pored
isprekidane linije ne može da zameni pravu liniju, jer nije na pravom rastojanju od druge.

Od tih tačaka `sliding_windows()` prati linije kliznim prozorima. Prozor dodeljuje liniji piksele unutar sebe i zatim
se pomera naviše, u 9 koraka do vrha slike. Kada sadrži dovoljno piksela, centrira se na njihov srednji x, pa prozori
prate liniju kroz krivinu. U prekidu isprekidane linije prozor nastavlja u pravcu poslednjeg pomaka.

Kroz piksele svake linije `fit_line()` provlači polinom `x = A*y^2 + B*y + C`. x je funkcija od y jer su linije u
slici skoro vertikalne. Umesto običnih najmanjih kvadrata koristi se RANSAC: u svakoj od 250 iteracija bira se po
jedan piksel iz svake trećine linije, kroz te tri tačke provlači se parabola i broji se koliko piksela leži na manje
od 30 px od nje. Parabola sa najviše takvih piksela (inliera) pobeđuje, a konačni fit se radi najmanjim kvadratima
samo na njenim inlierima. Svih 250 parabola računa se odjednom, pa je fit gotovo jednako brz kao običan.

RANSAC usput pokazuje i da li je to uopšte linija. Linija trake je tanka, pa skoro svi pikseli oko nje leže na njoj,
dok sunčeve mrlje i lišće popune ceo prozor. Ako je inliera manje od 60 %, u tom kadru linija se smatra nepronađenom.

Pikseli leve linije su crveni, desne plavi, prozori zeleni, a fitovi žuti:

![Pikseli linija i fit][image5]

Razlika između običnih najmanjih kvadrata i RANSAC-a vidi se kada prozor pokupi i šum pored linije. Najmanji kvadrati
vuku parabolu ka svakom pikselu, a RANSAC je drži na pikselima koji zaista leže duž jedne parabole:

![Najmanji kvadrati i RANSAC][image5b]

U videu se linije između dva kadra malo pomeraju, pa sledeći kadar ne kreće od kliznih prozora. `around_fit()` uzima
piksele u pojasu od ±60 px oko fita iz prethodnog kadra (desni deo slike sa prozorima). Pojas nije fiksan: ide odozdo
naviše u prozorima, a svaki prozor se pomera u stranu onoliko koliko su se pikseli ispod njega udaljili od prethodnog
fita. Tako se ne gubi linija koja na početku krivine počne da se savija više nego u prethodnom kadru.

#### 5. Poluprečnik krivine i pozicija vozila

Računanje je u funkcijama `curvature()` i `curvature_and_offset()`.

Za prelazak iz piksela u metre potrebna je razmera u oba pravca. Poprečno na put traka od 3,7 m zauzima 640 px
platna, što daje 5,8 mm po pikselu. Razmera duž puta izvedena je iz modela kamere, a ne pretpostavljena. Za ravan put
tačka u redu slike y udaljena je `Z = h*fy / (y - y_vp)`, gde je h visina kamere, a `y_vp` red nedogledne tačke. Iz
širine trake u donjem redu slike (900 px) i žižne daljine iz kalibracije dobija se da je kamera na 1,24 m, a donji red
slike 4,75 m ispred nje. Gornja ivica trapeza je onda na 35,2 m, pa platno pokriva 30,4 m puta, odnosno 4,2 cm po
redu. Rezultat se slaže sa isprekidanom linijom: crta i razmak (12 + 36 stopa, ukupno 14,6 m) na platnu se ponavljaju
na svakih 14,1-15,2 m.

Poluprečnik se računa iz koeficijenata polinoma prevedenih u metre (`A*xm/ym^2`, `B*xm/ym`), pa novi fit nije
potreban. Krivina se računa u donjem redu, najbližem vozilu:

κ = 2A / (1 + (2Ay + B)^2)^(3/2),  R = 1 / |κ|

Računa se za središnju liniju trake, odnosno srednju vrednost levog i desnog polinoma, što daje jednu vrednost sa manje
šuma nego bilo koja linija posebno. Prav put daje veoma veliki poluprečnik, pa se iznad 5 km ispisuje samo "> 5 km".

Za poziciju vozila pretpostavlja se da je kamera na sredini vozila, pa je vozilo na sredini donjeg reda slike. Ta
tačka se preslikava na platno istom matricom, jer trapez nije savršeno simetričan oko sredine slike. Pomeraj je
rastojanje između nje i sredine trake na dnu, u metrima, pozitivno kada je vozilo desno od centra.

Na test slikama:

| Slika | Poluprečnik krivine | Pomeraj vozila |
|---|---|---|
| test1.jpg | 853 m | 0,26 m levo |
| test2.jpg | 557 m | 0,35 m levo |
| test3.jpg | 1030 m | 0,19 m levo |
| test4.jpg | 939 m | 0,38 m levo |
| test5.jpg | 787 m | 0,06 m levo |
| test6.jpg | 959 m | 0,34 m levo |
| straight_lines1.jpg | > 5 km (pravo) | 0,07 m levo |
| straight_lines2.jpg | > 5 km (pravo) | 0,09 m levo |

Kroz projektni video poluprečnik u krivinama je uglavnom 740-1350 m, a na pravom delu prelazi 5 km. Za prvu krivinu
Udacity materijal, iz kog snimak potiče, navodi otprilike 1 km, a ovde je medijana 1000 m:

![Krivina i pomeraj kroz video][image6]

#### 6. Traka iscrtana nazad na put

Iscrtavanje radi `draw_lane()`. Traka se crta u pogledu odozgo, gde su fitovi i definisani: oblast između dva polinoma
boji se zeleno, a obe linije se crtaju duž polinoma kao debele crvene krive. `cv2.warpPerspective()` sa inverznom
matricom `Minv` vraća crtež u pogled kamere, a `cv2.addWeighted()` ga meša sa slikom. Na kraju se u gornji levi ugao
upisuju poluprečnik krivine i pomeraj vozila. Rezultat na test slikama:

![Rezultat][image7]

### Pipeline (video)

#### 1. Izlazni video

Izlazni video projektnog snimka nalazi se [ovde](./docs/project_video03.mp4). U `docs/` su i obrađeni ostali snimci:

| Video | Kamera | Kadrova | Kadrova sa trakom |
|---|---|---|---|
| [project_video01.mp4](./docs/project_video01.mp4) | 960x540 | 221 | 221 |
| [project_video02.mp4](./docs/project_video02.mp4) | 960x540 | 681 | 681 |
| [project_video03.mp4](./docs/project_video03.mp4) | 1280x720 | 1260 | 1260 |
| [challenge01.mp4](./docs/challenge01.mp4) | 1280x720 | 251 | 251 |
| [challenge02.mp4](./docs/challenge02.mp4) | 1280x720 | 484 | 484 |
| [challenge03.mp4](./docs/challenge03.mp4) | 1280x720 | 1199 | 1096 |

Obrada je brža od realnog vremena, oko 34 kadra u sekundi na procesoru laptopa. Nekoliko kadrova iz projektnog videa:

![Kadrovi iz projektnog videa][image8]

Za video `LaneDetector` pamti traku između kadrova. To je u metodama `update()` i `plausible()`:

* Ako je prethodni kadar imao traku, linije se traže oko nje (`around_fit()`, tačka 4), a posle neuspešnog kadra
  pretraga ponovo kreće od kliznih prozora.
* Novi par linija se prihvata samo ako liči na traku: širina kod vozila je između 2,5 i 4,3 m, duž platna se ne menja
  mnogo, ne skače u odnosu na prethodni kadar, vozilo je unutar trake i obe linije se savijaju slično. Kod poređenja
  savijanja bitno je uzeti pravu krivinu κ, a ne samo koeficijent A, jer u oštroj krivini linije idu dijagonalno preko
  platna i dve paralelne linije imaju različito A.
* Ako par ne prođe proveru ili jedna linija nedostaje (prekid isprekidane linije, izbledela boja, vozilo preko
  linije), zadržava se linija sa više piksela, a druga se crta paralelno sa njom na poslednjoj poznatoj širini trake.
  Paralelnost se meri duž normale na krivu, a ne prostim pomeranjem u stranu.
* Koeficijenti polinoma se usrednjavaju eksponencijalnim pokretnim prosekom, sa težinom 0,25 za novi kadar, što
  uklanja treperenje.
* Ako nijedan par ne prođe proveru, prikazuje se poslednja dobra traka. Posle 10 neuspešnih kadrova zaredom traka se
  briše, da se ne bi prikazivala zastarela.
* Nedogledna tačka se procenjuje tokom vožnje. U ispravnom pogledu odozgo linije su paralelne, pa ako se ka vrhu
  skupljaju, nedogledna tačka je niže nego što je pretpostavljeno i pomera se naniže, a ako se šire, pomera se naviše.
  Procena se radi samo na blagim krivinama, gde parabola dobro opisuje linije. Na snimku `challenge02` kamera je
  drugačije nagnuta: nedogledna tačka se za oko 7 sekundi pomeri sa reda 419 na oko 440, što odgovara onome što se
  vidi na snimku, i linije u pogledu odozgo postaju paralelne.
* Domet pogleda zavisi od krivine. U ukosnici linije izlaze iz platna od 30 m kroz njegove stranice, pa gornja ivica
  trapeza zavisi od poluprečnika iz prethodnog kadra: za blage krivine platno pokriva 30 m puta, a u najoštrijim
  krivinama oko 11 m. Domet se menja postepeno, a prethodni fit se na novo platno prenosi homografijom, pa se praćenje
  nastavlja bez skoka. Na autoputu domet ostaje stalan.

Kadrovi iz ostalih snimaka. Poslednji kadar je iz druge ukosnice na `challenge03`, gde traka nije pronađena:

![Kadrovi iz ostalih snimaka][image9]

### Diskusija

#### 1. Problemi i moguća poboljšanja

Najviše posla bilo je sa binarnom slikom. Prva verzija je koristila Sobel gradijent i pragove u HLS prostoru. Na
projektnom videu je radila, ali je na `challenge02` gradijent hvatao spoj dve vrste asfalta, spojeve od katrana i oštru
senku betonske ograde, jer su to sve jake vertikalne ivice. Linija trake nije samo ivica nego uska svetla traka, pa je
gradijent zamenjen top-hat filterom, koji izdvaja upravo takve trake:

![Sobel i top-hat][image10]

Drugi problem je bio nagib kamere. I sa čistom binarnom slikom, linije na `challenge02` su se u pogledu odozgo
skupljale ka vrhu, pa je skoro svaki kadar padao na proveri paralelnosti. Kamera je na tom snimku drugačije nagnuta.
Procena nedogledne tačke tokom vožnje to rešava, a delimično pomaže i na usponima i padovima.

Najteži snimak je `challenge03`: oštre krivine, ukosnice, dupla žuta linija, sunčeve mrlje i duboke senke. Tu su
najviše pomogli RANSAC i provera udela inliera, koji odbacuju šum umesto da ga fituju, zatim traženje početka linija
u paru, platno koje se skraćuje u krivini i pretraga koja prati liniju kada počne da se savija. Traka je sada
pronađena na 91 % kadrova, a van druge ukosnice nema kadrova sa pogrešno postavljenom trakom.

U drugoj ukosnici na `challenge03` pipeline i dalje ne radi. Put skreće za skoro 180°, traka ispred vozila je van
slike, a jako sunce briše belu liniju. Parabola `x = f(y)` ne može da opiše put koji skreće u stranu, pa provere
odbacuju te kadrove i traka se ne crta. Isto se kratko dešava u gustoj izmaglici, gde žuta linija gotovo nestaje.
Pipeline bi verovatno imao problema i pri promeni trake, jer se praćenje drži starih linija dok ih provera ne odbaci,
zatim noću, po kiši ili snegu, na izbledeloj boji i na izraženim usponima, jer pogled odozgo pretpostavlja ravan put.

Snimci 960x540 su sa kamere za koju nema slika table, pa se ne ispravljaju, a razmera u metrima je kod njih samo
približna. Provere uz to pretpostavljaju paralelne linije, što ne važi tamo gde se trake spajaju ili razdvajaju.

Kalmanov filter umesto pokretnog proseka dao bi i meru pouzdanosti procene, pa bi provere mogle da zavise od nje.
Model trake koji može da prati S-krivinu ili ukosnicu, na primer splajn ili klotoida, rešio bi najveći preostali
problem. Nedogledna tačka za nepoznatu kameru mogla bi se odrediti automatski, Hafovom transformacijom linija na prvim
kadrovima. Kada jedna linija trake nije vidljiva, njen položaj bi mogao da se proceni i iz susednih linija i ivice
puta.
