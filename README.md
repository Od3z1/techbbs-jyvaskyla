# TechBBS: Jyväskylän kauppavahti

GitHub Actions tarkistaa uudet ilmoitukset noin 5 minuutin välein. Pushit tulevat ntfy-sovellukseen. Ohjelma lukee Myydään ja ostetaan -osion sekä erilliset Vaihdetaan- ja Lahjoitetaan-osiot uusimmasta aloitusajasta alkaen. Uudet aktiiviset ilmoitukset avataan paikkakunnan tarkistamiseksi.

## Käyttöönotto

1. Asenna puhelimeen **ntfy** ja salli ilmoitukset. Palvelin: `https://ntfy.sh`.
2. Luo pitkä satunnainen kanavanimi, esimerkiksi `techbbs-` ja vähintään 24 satunnaista kirjainta/numeroa. Tilaa tämä kanava ntfy-sovelluksessa. Älä käytä esimerkkikanavaa tai julkaise omaa kanavanimeäsi repossa. Julkisen ntfy-palvelimen kanava on ilman käyttöoikeusrajausta luettavissa sen nimen tietävälle; suojattua kanavaa käytettäessä tarvitset myös palvelun käyttöoikeudet ja tokenin.
3. Luo GitHub-repositorio, esimerkiksi `techbbs-jyvaskyla`. Lisää tämän kansion sisältö repon juureen, myös `.github/workflows/watch.yml`. Älä lataa pelkkää ZIP-tiedostoa GitHubiin.
4. Avaa repossa **Settings → Secrets and variables → Actions → New repository secret**. Lisää `NTFY_TOPIC`, jonka arvoksi tulee kanavanimi. Jos käytät todennusta, lisää `NTFY_TOKEN` erikseen. Älä laita tunnuksia ohjelmakoodiin.
5. Salli **Settings → Actions → General → Workflow permissions → Read and write permissions**. Ohjelma tallentaa käsiteltyjen ketjujen tunnisteet osiokohtaisiin `state*.json`-tiedostoihin. Oletushaaran on sallittava Actionsin tekemät tilatallennukset.
6. Avaa **Actions → TechBBS Jyväskylä → Run workflow**. Voit ensin valita testiviestin. Suorita sen jälkeen normaali ajo ilman testivalintaa.
7. Ensimmäinen normaali ajo lähettää käynnistysilmoituksen kustakin kolmesta osiosta ja alustaa seurannan. Se ei lähetä kaikkia vanhoja myynti-ilmoituksia. Tämän jälkeen tarkista, että ajo näkyy vihreänä ja kolmen osion `state*.json`-tiedostot syntyivät.

## Rajaukset

- Tunnistaa `jkl`, `JKL`, `JkL`, `Jyväskylä`, `jyväskylä`, `JYVÄSKYLÄ` ja ääkkösettömän `Jyvaskyla`-muodon. Kirjainkoolla ei ole merkitystä.
- Ensisijaisesti tarkistetaan aloitusviestin **Paikkakunta** tai **Sijainti**. Jos kenttää ei ole, käytetään otsikkoa. Pelkkä toimitusmahdollisuus Jyväskylään tai vastauksessa oleva maininta ei riitä.
- Mukana Myydään, Ostetaan, Vaihdetaan ja Lahjoitetaan (myös Annetaan). Myyty, Ostettu, Vaihdettu ja Lahjoitettu jätetään pois. Pushin otsikko kertoo ilmoitustyypin. Ketjun nosto ei lähetä uutta ilmoitusta. Ilmoituksen myöhempää paikkakunnan muutosta tai hinnan laskua ei seurata.
- Hinta ja linkki sisältyvät pushiin. Samassa ketjussa olevat tuotteet saapuvat yhtenä ilmoituksena.

## Toimintarajat ja kustannukset

- GitHubin ajastus voi viivästyä tai ajo voi jäädä väliin. Viisi minuuttia ei ole täsmällinen ilmoitustakuu. Seuraava ajo hakee käsittelemättömät ilmoitukset myös katkoksen jälkeen (enintään 30 sivua).
- Yksityisen repon Actions-käyttö kuluttaa tilisi minuuttikiintiötä. 5 minuutin välein tulee noin 8 640 ajoa / 30 päivää. Tarkista tilisi ajantasainen kiintiö ja hinnoittelu ennen käyttöönottoa. Julkisen repon koodi ja state*.json ovat muiden luettavissa, mutta Secrets-arvot eivät kuulu niihin.
- GitHub voi poistaa julkisen repon ajastuksen käytöstä 60 päivän toimettomuuden jälkeen. Tarkista ajojen tila säännöllisesti.
- Jos sivusto estää lukemisen tai muuttaa rakennetta, ajo epäonnistuu näkyvästi. Ohjelma ei kierrä estoja. Sivupyyntöjen väli on vähintään sekunti.
- Jos push onnistuu mutta tila ei tallennu GitHubiin, sama ilmoitus voi tulla uudelleen. Verkon yli täysin täsmälleen kerran tapahtuvaa toimitusta ei luvata.
- Ensimmäinen sivuluku tässä ympäristössä ja parseritestit on tarkistettu. GitHub-ajo ja puhelimen push täytyy vielä testata omilla asetuksillasi.
- Aiempi ChatGPT:n tuntivahti on erillinen. Se kannattaa poistaa käytöstä, kun tämä vahti on testattu toimivaksi.

## Paikallinen testaus

```sh
pip install -r requirements.txt
python -m unittest -v
python watch.py --dry-run
```

`--dry-run` ei lähetä pusheja eikä muuta tilatiedostoa. Ilman tilatiedostoa se testaa vain listan lukemisen ja kertoo alustuksen. `--test-push` lähettää yhden testin ja vaatii NTFY_TOPIC-ympäristömuuttujan.

Lähteet: [GitHub-ajastukset](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [ntfy-viestien lähetys](https://docs.ntfy.sh/publish/).
