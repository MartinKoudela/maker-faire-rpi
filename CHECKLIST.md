# Raspi Vision – provozní checklist

Maker Faire Olomouc · neděle 15. 11. 2026

Projekt běží na Raspberry Pi 5 jako služba `maker-vision` (port `5000`). Po připojení napájení se spustí sám, při výpadku kamery nebo detekce ho watchdog do ~15 s restartuje.

| Adresa | Účel |
|---|---|
| `http://<ip-pi>:5000/` | monitor pro návštěvníky (fullscreen) |
| `http://<ip-pi>:5000/controls` | ovládání pro obsluhu |
| `http://<ip-pi>:5000/stream` | samotný video stream |

---

## 1. Den předem

- [ ] `git pull` na Pi a restart služby, ověřit, že běží poslední verze
- [ ] `.env` na Pi obsahuje `CAMERA_ROTATE_180=true`, `PROJECT_URL`, `PROJECT_LABEL`, `PIR_PIN=17`, případně `OPENAI_API_KEY`
- [ ] Monitor ukazuje kartu *Klasický senzor vs. umělá inteligence* (PIR je připojený a funkční)
- [ ] QR kód na monitoru jde načíst mobilem a otevře portfolio
- [ ] Cloud AI otestovaná jedním dotazem *Co vidíš?* (pokud bude použita)
- [ ] Mac a telefon nabité, hotspot telefonu má známé jméno a heslo
- [ ] Pi je připojené k hotspotu (je uložený v síťovém nastavení Pi)

### Co zabalit

- [ ] Raspberry Pi 5 v krabičce s kamerou a chladičem
- [ ] Oficiální napájecí zdroj 27 W (slabší zdroj = podpětí a škrcení výkonu)
- [ ] PIR čidlo připojené na GPIO17 (VCC → 5 V, GND → GND, OUT → pin 11)
- [ ] Kabel micro-HDMI → HDMI (monitor přímo k Pi)
- [ ] Mac + nabíječka, HDMI kabel jako záloha
- [ ] Telefon pro hotspot + nabíječka
- [ ] Prodlužovačka s více zásuvkami
- [ ] Izolepa / stahovací pásky na uchycení kamery a kabelů
- [ ] Informační cedulka: *Kamera snímá prostor u stánku, záznamy se neukládají.*

---

## 2. Instalace na místě

1. Zapnout hotspot na telefonu.
2. Umístit kameru tak, aby viděla prostor před stánkem, ideálně šikmo shora. Kamera je v krabičce vzhůru nohama, obraz se otáčí softwarově.
3. PIR čidlo namířit do stejného prostoru jako kameru.
4. Připojit monitor k Pi kabelem micro-HDMI (port HDMI0, blíž k napájení).
5. Zapojit napájení Pi. Do cca 60 s se na monitoru sám otevře přehled přes celou obrazovku (služba `kiosk`).
6. Připojit Mac nebo mobil k hotspotu a otevřít `http://<ip-pi>:5000/controls`.
   IP adresu Pi zjistíš v seznamu připojených zařízení na hotspotu, nebo na Pi příkazem `hostname -I`.

Záložní varianta bez kabelu micro-HDMI: monitor připojit k Macu, otevřít `http://<ip-pi>:5000/` přes celou obrazovku (`⌃⌘F`), spustit `caffeinate -d` a zapnout režim *Nerušit*. Video pak jde přes hotspot.

---

## 3. Nastavení před otevřením

V `/controls`:

- [ ] **Hlavička:** Video ~30 fps, Detekce > 5 fps, CPU pod 75 °C, žádné varování o škrcení
- [ ] **Počítání lidí → Nastavit čáru:** kliknout dva body přes průchod před stánkem. Projít čarou a ověřit, že se přičte. Případně *Otočit A/B*.
- [ ] **Heatmapa → Vymazat** a **Počítání lidí → Vynulovat**, aby se nepočítaly testovací průchody
- [ ] **Lokální AI:** zapnout požadované funkce (kostra, heatmapa, rozmazání obličejů)
- [ ] **Cloud AI:** zvolit režim
  - *Vypnuto* – vše lokálně, žádné náklady
  - *Tlačítko* – popis jen na vyžádání (doporučeno)
  - *Auto* – popis při příchodu nového člověka, max. jednou za 30 s
- [ ] **Denní limit** volání nastavit podle rozpočtu
- [ ] Zkontrolovat monitor: video, boxy, čísla, QR kód

---

## 4. Během dne

- Občas zkontrolovat `/controls`: teplotu, fps, stáří snímku, čerpání cloud limitu.
- Počítadla se o půlnoci nulují sama, ručně je nulovat není potřeba.
- Při výpadku internetu běží vše kromě Cloud AI dál. Cloud AI v takovém případě přepnout na *Vypnuto*.

---

## 5. Řešení problémů

| Problém | Příčina | Řešení |
|---|---|---|
| Monitor je černý | Kiosk neběží / monitor připojen až po startu | `sudo systemctl restart kiosk`, `journalctl -u kiosk -e` |
| Stránka se nenačte | Pi neběží / jiná síť / jiná IP | Ověřit, že Mac i Pi jsou na hotspotu; zjistit IP; `sudo systemctl status maker-vision` |
| Video stojí, *Snímek* roste | Kamera nebo detekce zamrzla | Watchdog restartuje službu sám do ~15 s. Jinak `sudo systemctl restart maker-vision` |
| Video se seká | Slabá Wi-Fi, mnoho otevřených streamů | Zavřít nepotřebné záložky. V `.env` nastavit `STREAM_JPEG_QUALITY=60` a restartovat |
| Nízké fps detekce | Kostra / rozmazání obličejů zatěžuje CPU | Vypnout kostru nebo rozmazání. Případně `YOLO_INPUT_SIZE=480` |
| Varování *podpětí* | Slabý napájecí zdroj | Použít oficiální 27W zdroj |
| CPU nad 80 °C | Přehřívání | Zkontrolovat chladič, umístit Pi mimo přímé slunce a teplo monitoru |
| Obraz je vzhůru nohama | Chybí nastavení otočení | `CAMERA_ROTATE_180=true` v `.env`, restart |
| Cloud AI hlásí chybu | Chybí klíč, vyčerpaný limit, bez internetu | Hláška u tlačítka řekne příčinu. Případně přepnout na *Vypnuto* |
| PIR ukazuje `–` | Čidlo nepřipojené nebo chybí knihovna | Zkontrolovat zapojení na GPIO17. `sudo apt install python3-gpiozero python3-lgpio`, restart |
| Boxy se nečekaně vypnou | Detekce starší než 1 s | Krátkodobé, opraví se samo. Pokud trvá, restart služby |

### Užitečné příkazy (na Pi)

```bash
sudo systemctl status maker-vision
sudo systemctl restart maker-vision
sudo systemctl restart kiosk
journalctl -u maker-vision -f
journalctl -u maker-vision | grep health | tail
vcgencmd measure_temp
```

---

## 6. Po akci

- [ ] Poznamenat si čísla z monitoru (Dnes u stánku, Dnes prošlo, špička)
- [ ] Bezpečně vypnout Pi: `sudo shutdown -h now`, odpojit napájení až po zhasnutí zelené LED

---

## Co říct návštěvníkům

- **Co to dělá:** kamera sleduje prostor před stánkem, neuronová síť v reálném čase pozná lidi, sleduje je a počítá.
- **Kde to běží:** vše lokálně na Raspberry Pi 5 za pár tisíc korun, bez internetu a bez cloudu.
- **Senzor vs. AI:** PIR čidlo za pár korun pozná jen pohyb. Kamera s AI ví, kolik lidí tu je, kde stojí a kudy chodí.
- **Soukromí:** žádný záznam se neukládá, obličeje lze rozmazat. Do cloudu jde snímek jen na vyžádání.
- **Technologie:** YOLO11 (detekce a kostra těla), ByteTrack (sledování), OpenCV, Python, Flask, volitelně OpenAI pro popis scény.
