# Frendy Webmercs MCP

Paikallinen MCP-palvelin Webmercs Admin API:n lukemiseen. Ensimmäinen versio tarjoaa
11 työkalua tilausten, sarjanumeroiden, toimittajatilausten, tuotteiden, asiakkaiden
ja käyttäjien tutkimiseen.

Kaikki API-kutsut ovat GET-hakuja ja käyttävät kiinteästi projektia **3 / PINUS-FRENDY / Frendy**
(`X-Project-ID: 3`). Projektia tai palvelimen osoitetta ei voi vaihtaa työkalukutsussa.
Palvelin ei sisällä tilausten, vientistatusten tai muiden tietojen muuttamista.

## Asennus

Tarvitset Python 3.11:n tai uudemman sekä Webmercsin Admin API -tunnukset.

```bash
cd "/Users/pelkonen/github/Webmercs MCP"
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Täytä `.env`-tiedostoon `WEBMERCS_API_USERNAME` ja `WEBMERCS_API_PASSWORD`.
API-kuvaus määrittelee HTTP Basic Authin: kenttiin annetaan tunnuspari sellaisenaan,
ei valmista Base64-merkkijonoa eikä `Basic `-otsaketta. Jos saamasi API-avaimet ovat
eri muodossa, varmista Webmercsiltä niiden käyttö Basic Authin tunnusparina.

`.env` ja muut paikalliset ympäristötiedostot ovat `.gitignore`-tiedostossa.
`.env.example` sisältää vain tyhjät tunnuskentät. Ympäristömuuttujat menevät
`.env`-tiedoston arvojen edelle. Tunnuksia tai API:n virhevastausten sisältöä ei
kirjoiteta lokiin tai työkalujen virheilmoituksiin.

## Käynnistys ja MCP-asiakkaaseen liittäminen

```bash
.venv/bin/webmercs-mcp --env-file "/Users/pelkonen/github/Webmercs MCP/.env"
```

Palvelin käyttää **stdio**-yhteyttä: MCP-asiakas käynnistää prosessin ja kommunikoi
sen vakiosyötteen ja vakio­tulosteen kautta. Pelkkä käynnistys terminaalissa jää
odottamaan asiakkaan viestejä, eikä avaa HTTP-porttia. Virheilmoitukset menevät stderr-kanavaan.

MCP-asiakkaan asetusesimerkki (asiakkaan asetustiedoston muoto voi vaihdella):

```json
{
  "mcpServers": {
    "frendy-webmercs": {
      "command": "/Users/pelkonen/github/Webmercs MCP/.venv/bin/webmercs-mcp",
      "args": [
        "--env-file",
        "/Users/pelkonen/github/Webmercs MCP/.env"
      ]
    }
  }
}
```

Käytä absoluuttisia polkuja, jotta käynnistys ei riipu asiakkaan työhakemistosta.
Tunnuksia ei tarvitse kopioida MCP-asiakkaan asetuksiin. Käynnistä MCP-yhteys
uudelleen, kun muutat `.env`-asetuksia.

## Työkalut

| Työkalu | Tarkoitus / tärkeimmät parametrit |
| --- | --- |
| `list_orders` | `customer_id`, `user_id`, `status`, `created_at_days`, `pending_export_any` |
| `get_order` | Yksittäinen tilaus: `order_id` |
| `find_orders_by_serial_number` | `serial_number`, `created_at_days` |
| `list_vendor_orders` | `vendor_id`, `status`, `created_at_days` |
| `get_vendor_order` | Toimittajatilaus: `vendor_order_id` |
| `search_products` | `search`, `brand_sku`, `brand_id`, `category_id`, `status` |
| `get_product` | Tuote: `product_id` |
| `list_customers` | `customer_number`, `enabled` |
| `get_customer` | Asiakas: `customer_id` |
| `list_users` | `email`, `customer_id`, `enabled` |
| `get_user` | Käyttäjä: `user_id` |

Kaikissa listahauissa on `offset` (oletus 0) ja `limit` (oletus 20, sallittu 1–100).
Palvelin palauttaa yhden sivun alkuperäisessä API-rakenteessa, mukaan lukien
`items`, `total`, `count`, `offset` ja `limit`, kun API palauttaa ne.
Seuraava sivu haetaan kasvattamalla `offset`-arvoa palautettujen rivien määrällä.
Palvelin ei automaattisesti lataa kaikkia sivuja.

Tilaus- ja toimittajatilaushakujen aikarajaus on oletuksena **90 päivää**.
Myös sarjanumerohaku käyttää tätä rajausta. Vanhempia tilauksia etsiessä kasvata
`created_at_days`-arvoa; tyhjä tulos ei todista, ettei sarjanumeroa löydy vanhemmista tilauksista.
Yksittäisen tietueen ID-haku ei käytä tätä aikarajausta.

Esimerkkejä työkalujen parametreista:

```json
{"serial_number": "ESIMERKKI-SARJANUMERO", "created_at_days": 1825, "limit": 20}
```

```json
{"status": "Ordered", "pending_export_any": true, "created_at_days": 90}
```

```json
{"brand_sku": "VALMISTAJAN-TUOTEKOODI", "limit": 10}
```

Tilausrivien hinnat palautetaan API:n alkuperäisinä arvoina. Dokumentoidut
tilaushinnat ovat valuutan pienimmässä yksikössä: esimerkiksi `1025` tarkoittaa
`10,25 EUR`, jos tilauksen valuutta on EUR. Muiden kenttien yksiköt tarkistetaan
niiden omasta API-kuvauksesta. Tuotteiden projektikohtaiset hinta- ja varastotiedot
voivat sijaita `projects`-kentässä.

## Virheet ja rajaukset

- HTTP 401: tarkista API-tunnukset.
- HTTP 403: tarkista tunnusten oikeudet Frendyn projektiin.
- HTTP 404: tietuetta tai resurssia ei löydy.
- HTTP 429: odota ennen seuraavaa hakua.
- Yhteysvirhe ja aikakatkaisu palautetaan ymmärrettävinä työkalujen virheinä.

Kutsuja ei uusita automaattisesti. Oletusaikakatkaisu on 30 sekuntia ja sen voi
muuttaa `.env`-tiedostossa. API-vastaukset voivat sisältää asiakas-, käyttäjä- ja
osoitetietoja, joita MCP-asiakas käsittelee työkalun vastauksena.

Tämä versio on paikalliseen käyttöön. Jaettu HTTP-palvelu, sen käyttäjätunnistus,
kirjoitustyökalut ja taustasynkronointi eivät sisälly runkoon.

## Kehitys ja tarkistus

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

Testit käyttävät simuloituja HTTP-vastauksia. Ne tarkistavat muun muassa
Basic Authin, Frendyn projektirajauksen, GET-haut, hakuehtojen välityksen,
virheiden käsittelyn sekä työkalujen toiminnan MCP-yhteyden kautta.
Testit eivät tarvitse oikeita API-tunnuksia eivätkä tee Webmercs-kutsuja.

Oikeiden tunnusten toimivuus ja API-vastausten sisältö täytyy vielä varmistaa
MCP-asiakkaasta tehdyllä lukuhakukokeilulla. Aloita rajatulla haulla,
esimerkiksi `list_customers` parametrilla `limit: 1`.

Riippuvuudet rajataan yhteensopiviin pääversioihin; MCP SDK käyttää tässä v1:n
FastMCP-rajapintaa. Tässä luonnoksessa ei ole tarkkojen riippuvuusversioiden lukitustiedostoa.

## API-lähteet

- [Webmercs Swagger](https://api.webmercs.com/admin/v1/swagger/index.html)
- [Webmercs OpenAPI JSON](https://api.webmercs.com/admin/v1/swagger/admin-openapi.json)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

`docs/admin-openapi.json` on 13.10.2026 haettu dokumentaatiokopio.
Se ei sisällä API-tunnuksia tai oikeiden tilausten vastauksia.
