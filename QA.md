# Raspi Vision – otázky a odpovědi

Podklady pro vysvětlování u stánku. Každá odpověď má krátkou verzi na řeč a případně detail pro zvídavé.

---

## Projekt v jedné větě

> Kamera na Raspberry Pi v reálném čase pozná lidi před stánkem, sleduje je, počítá a ukazuje, kudy chodí. Všechno běží lokálně na malém počítači za pár tisíc, bez internetu.

### Pro děti

> Počítač se naučil z tisíců fotek, jak vypadá člověk. Teď kouká kamerou a kolem každého, koho vidí, nakreslí rámeček a dá mu číslo.

---

## Hardware

**Na čem to běží?**
Raspberry Pi 5 se 16 GB RAM: čtyřjádrový ARM procesor Cortex-A76 na 2,4 GHz. Žádná grafická karta ani AI akcelerátor, všechno počítá samotný procesor.

**Jaká je to kamera?**
Raspberry Pi Camera Module 3 NoIR, 12 MPx čip Sony IMX708. *NoIR* znamená bez infračerveného filtru: vidí i infračervené světlo, takže by fungovala i s IR přísvitem ve tmě. Za denního světla proto mívá trochu zvláštní barvy.

**Proč je kamera vzhůru nohama?**
Kvůli tvaru vytištěné krabičky. Obraz se otáčí softwarově.

**Co je to za malé čidlo vedle?**
PIR čidlo pohybu, stejné jako v automatických světlech na chodbě. Reaguje na změnu tepelného (infračerveného) záření, třeba když projde člověk. Pozná jen *ano/ne*, nic víc. Je tu schválně pro srovnání s AI.

**Kolik to žere?**
Raspberry Pi 5 má při plné zátěži řádově jednotky až kolem 10 W. To je méně než běžná žárovka.

**Kolik to stojí?**
Raspberry Pi 5 a kamera dohromady vyjdou na pár tisíc korun. PIR čidlo stojí desítky korun.

---

## Umělá inteligence

**Jak to pozná člověka?**
Neuronová síť **YOLO11** („You Only Look Once“). Snímek projde sítí jednou a ta vrátí obdélníky kolem všech lidí, které najde, a k nim jistotu, že jde o člověka.

Detail: nejmenší varianta YOLO11n má asi 2,6 milionu parametrů a soubor má kolem 10 MB. Je natrénovaná na datové sadě COCO, kde je přes 100 000 fotek s označenými objekty v 80 kategoriích. Z nich používám jen kategorii *člověk*.

**Učil jsi ji sám?**
Ne, používám předtrénovaný model. Moje práce je dostat ho efektivně na Raspberry Pi, napojit na kameru a postavit kolem toho celý systém: sledování, počítání, heatmapu, kostru těla, web a ovládání.

**Jak je to rychlé?**
Video běží na 30 snímků za sekundu. Detekce stihne zhruba 8–12 snímků za sekundu, podle toho, co je zapnuté. Obojí běží souběžně ve dvou vláknech, takže video se nezpomaluje kvůli AI.

**Jak to běží tak rychle na tak malém počítači?**
Model je převedený do formátu **NCNN**. To je knihovna od Tencentu optimalizovaná pro ARM procesory v mobilech, takže využívá všechna čtyři jádra a speciální instrukce procesoru.

**Co jsou ta čísla u lidí (#12)?**
Sledování (tracking) algoritmem **ByteTrack**. Detekce na každém snímku je samostatná a teprve tracking pozná, že rámeček na tomhle snímku je stejný člověk jako na předchozím. Odhaduje, kam se člověk posune (Kalmanův filtr), a páruje rámečky podle překryvu.

**Pozná mě to příště? Ví, kdo jsem?**
**Ne.** Číslo je jen dočasné označení, dokud jsi v záběru. Když odejdeš a vrátíš se, dostaneš nové. Systém nerozpoznává obličeje ani identitu a nic si o lidech nepamatuje.

**Jak funguje ta kostra?**
Druhý model, **YOLO11n-pose**, k rámečku najde i 17 bodů těla: nos, oči, uši, ramena, lokty, zápěstí, boky, kolena a kotníky. Spojením bodů vznikne kostra. Je o něco pomalejší, proto jde vypnout.

**Co je ta barevná mapa?**
Heatmapa pohybu. Ukazuje, kde se lidé nejčastěji zdržují. Starší data postupně blednou (po 15 minutách na polovinu), takže mapa ukazuje poslední dění.

**Jak to počítá lidi?**
- *Právě teď*: kolik lidí je na aktuálním snímku.
- *Dnes u stánku*: kolik různých lidí systém sledoval. Člověk se započítá, až je vidět aspoň 5 snímků po sobě, aby se nepočítaly chybné detekce.
- *Dnes prošlo*: kolikrát někdo překročil virtuální čáru v obraze, ve kterémkoli směru.

**Jak je to přesné?**
Na běžnou scénu velmi dobře. Chybuje, když se lidé hodně překrývají v davu, jsou daleko nebo jen napůl v záběru, nebo při špatném světle. Počty berte jako dobrý odhad, ne přesné sčítání. Když se člověk na chvíli schová za jiného, může dostat nové číslo.

**Proč nepoužiješ ESP32 / Arduino?**
Na mikrokontroléru se dá pustit jen hodně malý model s nízkým rozlišením, třeba pár snímků za sekundu na detekci „je tu člověk / není“. Sledování, kostra a plynulé video potřebují výkon procesoru jako v mobilu.

**Šlo by to rychleji?**
Ano. S AI akcelerátorem (například Raspberry Pi AI HAT s čipem Hailo) by detekce běžela na plných 30 fps a víc. Tady jsem chtěl ukázat, co zvládne samotný procesor.

---

## Cloud AI (popis scény)

**Kdo píše ten popis v češtině?**
Jazykový model od OpenAI (GPT). Na vyžádání se mu pošle jeden snímek a on popíše scénu: kolik lidí, co dělají, jaké vidí předměty. Odpověď trvá několik sekund.

**Proč to neběží pořád?**
Každý dotaz stojí peníze a celý den v kuse by to vyšlo draho. Proto se dá v ovládání vypnout, spouštět jen tlačítkem, nebo automaticky nejvýš jednou za 30 sekund s denním limitem.

**Proč to neběží taky lokálně?**
Jazykové modely, které umí popsat obrázek, jsou o řády větší než YOLO. Na Raspberry Pi by jedna odpověď trvala minuty. Lokální AI tu dělá rychlé věci v reálném čase, cloudová AI to pomalé „chytré“.

**Je model instruovaný nějak speciálně?**
Ano. Musí odpovídat česky a stručně, a nesmí odhadovat pohlaví, věk, etnicitu ani hodnotit vzhled.

---

## Soukromí

**Nahráváš nás?**
**Ne.** Video se nikam neukládá, zpracovává se snímek po snímku v paměti a hned se zahodí. Ukládají se jen souhrnná čísla: kolik lidí bylo za hodinu.

**Jde něco na internet?**
Lokální část vůbec, všechno běží na Raspberry Pi. Do cloudu jde jen jeden snímek, když se spustí popis scény. Ten jde přes API OpenAI, které podle jejich podmínek data z API standardně nepoužívá k trénování.

**Co je to rozmazání obličejů?**
Další malá neuronová síť (YuNet z OpenCV) najde obličeje a obraz je na těch místech rozpixeluje. Je to ukázka anonymizace, kterou se dá zapnout.

---

## Software

**V čem je to napsané?**
Python. Hlavní knihovny:
- OpenCV na zpracování obrazu,
- NCNN na běh neuronových sítí,
- supervision pro ByteTrack,
- Flask jako webový server,
- obyčejné HTML, CSS a JavaScript pro web.

**Jak se dostane obraz na monitor?**
Raspberry Pi samo hostuje webovou stránku a video posílá jako MJPEG stream, tedy rychlý sled JPEG obrázků. Monitor je připojený přímo k Pi, na kterém běží prohlížeč v režimu kiosku. Stejnou stránku jde otevřít z mobilu na stejné síti.

**Co když to spadne?**
Hlídač (watchdog) kontroluje, jestli chodí nové snímky. Když se něco zasekne, aplikace se sama restartuje a stránka na monitoru se sama obnoví.

**Jak dlouho jsi to dělal?**
Tahle verze vznikla spojením dvou mých dřívějších projektů: bezpečnostní kamery s PIR čidlem a systému vidění pro humanoidního robota. Řešení jsem postavil znovu a vylepšil.

**Je to open source?**
Odkaz na moje projekty je v QR kódu na monitoru.

---

## Na co si dát pozor

- **Neříkat, že systém rozpoznává obličeje nebo konkrétní lidi.** Nerozpoznává.
- **Neslibovat přesné počty.** Jde o odhad, který v davu chybuje.
- Když se někdo nechce nechat snímat, stačí, aby šel mimo záběr. Nic se neukládá.
