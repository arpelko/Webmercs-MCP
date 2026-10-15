# Webmercs MCP

[English](README.md) | Suomi

Paikallinen MCP-palvelin Webmercs Admin API:n käyttöön. Palvelimessa on 11 lukutyökalua,
26 kirjoitustyökalua sekä työkalupakettien tietoja näyttävä `list_tool_packages`.
Oletuksena vain lukutoiminnot ovat käytettävissä.

Kaikki API-kutsut käyttävät asetuksessa `WEBMERCS_PROJECT_ID` määritettyä projektia
(`X-Project-ID`-otsake). Projektia tai palvelimen osoitetta ei voi vaihtaa työkalukutsussa.
Toteutus ei sisällä yrityskohtaisia tunnisteita tai sääntöjä.

## Asennus

Tarvitset Python 3.11:n tai uudemman sekä Webmercsin Admin API -tunnukset.

```bash
cd "/absolute/path/to/webmercs-mcp"
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Täytä `.env`-tiedostoon `WEBMERCS_API_USERNAME`, `WEBMERCS_API_PASSWORD` ja
`WEBMERCS_PROJECT_ID`. Projektitunniste on oman Webmercs-projektisi positiivinen
kokonaisluku. Esimerkkitiedoston tunnuskentät ja projektitunniste on jätetty tyhjiksi;
projektilla ei ole oletusarvoa. Vaihda ohjeen esimerkkipolku oman projektihakemistosi poluksi.
API-kuvaus määrittelee HTTP Basic Authin: kenttiin annetaan tunnuspari sellaisenaan,
ei valmista Base64-merkkijonoa eikä `Basic `-otsaketta. Jos saamasi API-avaimet ovat
eri muodossa, varmista Webmercsiltä niiden käyttö Basic Authin tunnusparina.

`.env` ja muut paikalliset ympäristötiedostot ovat `.gitignore`-tiedostossa.
`.env.example` sisältää vain tyhjät tunnuskentät. Ympäristömuuttujat menevät
`.env`-tiedoston arvojen edelle. Tunnuksia tai API:n virhevastausten sisältöä ei
kirjoiteta lokiin tai työkalujen virheilmoituksiin.

## Käynnistys ja MCP-asiakkaaseen liittäminen

```bash
.venv/bin/webmercs-mcp --env-file "/absolute/path/to/webmercs-mcp/.env"
```

Palvelin käyttää **stdio**-yhteyttä: MCP-asiakas käynnistää prosessin ja kommunikoi
sen vakiosyötteen ja vakio­tulosteen kautta. Pelkkä käynnistys terminaalissa jää
odottamaan asiakkaan viestejä, eikä avaa HTTP-porttia. Virheilmoitukset menevät stderr-kanavaan.

MCP-asiakkaan asetusesimerkki (asiakkaan asetustiedoston muoto voi vaihdella):

```json
{
  "mcpServers": {
    "webmercs": {
      "command": "/absolute/path/to/webmercs-mcp/.venv/bin/webmercs-mcp",
      "args": [
        "--env-file",
        "/absolute/path/to/webmercs-mcp/.env"
      ]
    }
  }
}
```

Käytä absoluuttisia polkuja, jotta käynnistys ei riipu asiakkaan työhakemistosta.
Tunnuksia ei tarvitse kopioida MCP-asiakkaan asetuksiin. Käynnistä MCP-yhteys
uudelleen, kun muutat `.env`-asetuksia.

## Lukutyökalut

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

## Työkalujen hallinta

Asetukset luetaan palvelimen käynnistyessä. Muuta `.env`-tiedostoa ja käynnistä
MCP-yhteys uudelleen. Työkalu ei voi vaihtaa pakettiaan tai sallia itselleen kirjoituksia.

| `MCP_TOOL_PACKAGE` | Käytössä |
| --- | --- |
| `readonly` (oletus) | Kaikki 11 lukutyökalua |
| `orders` | Kaikki lukutyökalut ja 16 tilaus-/lähetyskirjoitusta |
| `catalog` | Tuotehaut ja tuotteen luonti |
| `customers` | Asiakas- ja käyttäjähaut sekä 9 asiakas-/käyttäjäkirjoitusta |
| `full` | Kaikki luku- ja kirjoitustyökalut |
| `none` | Ei yhtään työkalua |

`list_tool_packages` näyttää aktiivisen paketin, käytössä olevat työkalut, poissulut
ja kirjoitusten sallimisen tilan. Se sisältyy kaikkiin paketteihin paitsi `none`.
Tuntematon paketti tai virheellinen asetus estää palvelimen käynnistymisen.

Esimerkiksi tilaustyökalut esikatseluun:

```dotenv
MCP_TOOL_PACKAGE=orders
WEBMERCS_ALLOW_WRITES=false
MCP_DISABLED_TOOLS=send_order_email,delete_order_line,delete_vendor_order_shipment
```

`MCP_DISABLED_TOOLS` on pilkuilla erotettu lista poistettavista työkaluista.
Poissulku ohittaa paketin: työkalu ei näy eikä sitä voi kutsua suoraan nimellä.
Rajaus on työkalukohtainen; useampi sallittu työkalu voi muokata samaa kenttää.
Työkalupaketit eivät korvaa Webmercsin omia käyttöoikeuksia.

## Kirjoittaminen ja esikatselu

Jokaisen kirjoitustyökalun oletus on `dry_run: true`. Esikatselu tarkistaa pyynnön
paikallisesti ja palauttaa metodin, polun, projektin ja sisällön **tekemättä API-kutsua**.
Se ei tarkista tietueen olemassaoloa, oikeuksia tai Webmercsin liiketoimintasääntöjä.

Varsinainen kirjoitus edellyttää kaikkia seuraavia:

1. Työkalu kuuluu valittuun pakettiin eikä ole poissuljettu.
2. Palvelimen asetuksissa on `WEBMERCS_ALLOW_WRITES=true`.
3. Työkalukutsussa annetaan nimenomaisesti `dry_run: false`.

Esimerkki `set_order_status_order_action`-työkalun esikatselusta kuvitteelliselle tilaukselle:

```json
{
  "order_id": 123,
  "payload": {"orderStatus": "Ordered"},
  "dry_run": true
}
```

Toteutus käyttää API-kuvauksen omia payload-kenttiä ja validoi niiden tyypit,
pakolliset arvot, enum-arvot ja ylimääräiset kentät. Työkalun MCP-skeema sisältää
payloadin rakenteen. Tunnisteparametrit ovat snake_case-muodossa, esimerkiksi
`order_id`, `order_line_id`, `user_id`, `vendor_order_id` ja `shipment_id`.
Payload-kentät ovat Webmercsin alkuperäisessä muodossa, esimerkiksi `orderStatus`.
Jos payloadissa annetaan `projectId`, sen pitää vastata palvelimen projektia.
Pois jätetyt kentät ja nimenomaiset `null`-arvot säilytetään erillisinä; esimerkiksi
`update_order_partial`-työkalussa `null` voi tyhjentää kentän.

Onnistunut kirjoitus palauttaa `executed: true`, `http_status` ja `data`.
Tyhjä onnistumisvastaus palauttaa `data: null`. Verkkovirhe tai palvelinvirhe ei
takaa, ettei muutosta tapahtunut. Tarkista tietue lukutyökalulla ennen uutta yritystä.
Palvelin ei toista kirjoituksia automaattisesti.

Tilauksen luonti, tuonti ja sähköpostityökalu voivat aiheuttaa Webmercsin omia
sivuvaikutuksia, kuten tilausvahvistusten lähettämistä. `generate_password_reset_link`
palauttaa arkaluonteisen linkin, jota asiakas käsittelee työkalun vastauksena.

| Kirjoitustyökalu | Webmercs-toiminto |
| --- | --- |
| `update_customer` | Update customer (partial update). |
| `create_customer` | Create customer |
| `set_customer_number` | Set customer number |
| `update_order` | Update order |
| `update_order_partial` | Update order (partial update). |
| `place_order` | Place an order |
| `set_admin_comment_order_action` | Set order admin comment |
| `set_order_status_order_action` | Set order status. |
| `set_export_status_order_action` | Set export status. |
| `send_order_email` | Send an order email of the specified type to the default recipients or to the specified ones |
| `update_order_billing_address` | Update order billing address (partial update). |
| `update_order_shipping_address` | Update order shipping address (partial update). |
| `add_order_line` | Add a new order line |
| `update_order_line` | Update an order line |
| `delete_order_line` | Delete an order line |
| `import_order_file` | Import order from file |
| `import_order_text` | Import order from text |
| `create_product` | Create product |
| `create_user` | Create user |
| `change_customer` | Change customer for user |
| `create_billing_profile` | Create billing profile |
| `set_customer_number_for_billing_profile` | Set customer number for billing profile |
| `create_shipping_profile` | Create shipping profile |
| `generate_password_reset_link` | Generate password reset link for user |
| `add_vendor_order_shipment` | Add a shipment (tracking number) to a vendor order |
| `delete_vendor_order_shipment` | Delete a shipment from a vendor order |

`update_order` tukee API-kuvauksessa dokumentoitua `setAdminComment`-toimintoa.
Yksittäisiin muutoksiin kannattaa käyttää niiden omia työkaluja.
`import_order_text` ottaa `text`-sisällön. `import_order_file` ottaa pelkän
`filename`-nimen ja `content_base64`-sisällön (enintään 5 MiB); se ei lue paikallisia
tiedostopolkuja. Tuontitiedoston esikatselu palauttaa nimen, koon ja SHA-256-tiivisteen.
Tuontisisällön sisäisen formaatin ja liiketoimintasääntöjen tarkistus jää Webmercsille.

## Virheet ja rajaukset

- HTTP 401: tarkista API-tunnukset.
- HTTP 403: tarkista tunnusten oikeudet asetuksissa määritettyyn projektiin.
- HTTP 404: tietuetta tai resurssia ei löydy.
- HTTP 429: odota ennen seuraavaa hakua.
- Yhteysvirhe ja aikakatkaisu palautetaan ymmärrettävinä työkalujen virheinä.

Kutsuja ei uusita automaattisesti. Oletusaikakatkaisu on 30 sekuntia ja sen voi
muuttaa `.env`-tiedostossa. API-vastaukset voivat sisältää asiakas-, käyttäjä- ja
osoitetietoja, joita MCP-asiakas käsittelee työkalun vastauksena.

Tämä versio on paikalliseen käyttöön. Jaettu HTTP-palvelu, sen käyttäjätunnistus
ja taustasynkronointi eivät sisälly toteutukseen.

## Kehitys ja tarkistus

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

Testit käyttävät simuloituja HTTP-vastauksia. Ne tarkistavat muun muassa
Basic Authin, asetuksissa määritetyn projektirajauksen, hakuehtojen välityksen,
työkalupakettien estot, esikatselut sekä kaikkien 26 kirjoitustyökalun HTTP-metodit,
polut ja sisällöt MCP-yhteyden kautta. PATCH-pyyntöjen null-arvot säilytetään.
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
