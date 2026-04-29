# Market Scout Bot

En lokal trading-bot/scanner som analyserer en markedsliste, rangerer mulige kjøpskandidater og lager en enkel posisjonsplan med stop-loss, target og antall aksjer etter valgt risikoprofil.

Viktig: Dette er ikke finansiell rådgivning, og boten garanterer ikke avkastning. Høyere risiko betyr større svingninger og større mulig tap. Før ekte ordre kobles på bør strategien backtestes, paper-trades og vurderes opp mot skatt, gebyrer og din egen risikotoleranse.

## Kom i gang

Kjør offline-demoen først:

```bash
python3 -m market_scout scan --source demo --risk medium --account 100000 --top 10
```

Se risikoprofilene:

```bash
python3 -m market_scout profiles
```

Scan en egen liste:

```bash
python3 -m market_scout scan --source stooq --universe data/universe_sample.txt --risk high --account 100000 --top 20
```

Stooq-kilden henter daglige historiske priser for amerikanske aksjer/ETF-er. For "hele markedet" bør `data/universe_sample.txt` erstattes med en full symbol-liste fra broker, børs, Nasdaq/NYSE-export eller en betalt dataleverandør.

## Web-dashboard

Start dashboardet:

```bash
python3 -m market_scout.web
```

Åpne deretter:

```text
http://127.0.0.1:8765
```

Dashboardet lar deg velge datakilde, risikoprofil, konto-størrelse, antall treff, historikk og markedsliste uten å sitte i terminaltabellen.
Det viser også et Bull/Bear-regime basert på SPY, QQQ og IWM, og har en Auto-bryter for periodisk refresh.

## Legg ut på nett

Prosjektet er klargjort for Docker-deploy med [Dockerfile](./Dockerfile) og Render Blueprint med [render.yaml](./render.yaml). Se [DEPLOY.md](./DEPLOY.md) for Render, Railway og Fly.io.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fux-skappel%2FBottrad)

Kortversjon for lokal Docker-test:

```bash
docker build -t market-scout .
docker run --rm -p 8765:10000 market-scout
```

Åpne:

```text
http://127.0.0.1:8765
```

Merk: Dashboardet har ikke innlogging ennå. Ikke legg det offentlig med ekte broker-nøkler før tilgangskontroll er på plass.

## Risikoprofiler

- `low` / `lav` / `forsiktig`: strengere filter, lavere posisjonsstørrelse.
- `medium` / `middels` / `balansert`: normal trend/momentum-scanning.
- `high` / `hoy` / `aggressiv`: lavere scorekrav og større posisjoner.
- `very_high` / `spekulativ`: mest aggressiv. Brukes helst kun til paper trading eller små testbeløp.

## Hvordan signalene scores

Scanneren kombinerer:

- trend: pris over 20/50/200 dagers glidende snitt
- momentum: RSI og 20/60 dagers prisendring
- breakout: nærhet til 20/55 dagers høy
- volum: volumøkning og likviditet
- volatilitet: ATR som prosent av pris, filtrert etter risikoprofil

Resultatet er `BUY`, `WATCH`, `WAIT` eller `SKIP`. `BUY` betyr at signalet passer reglene akkurat nå. `WATCH` betyr at caset er interessant, men ikke helt sterkt nok.

## Neste naturlige steg

1. Legg inn en full markedsliste i `data/universe_sample.txt`.
2. Backtest reglene på historiske data.
3. Kjør paper trading i minst noen uker.
4. Koble på broker-API først når du har ordre-regler, logging, feilhåndtering og maks daglig tap på plass.
