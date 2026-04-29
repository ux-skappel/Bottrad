# Publisering på nett

Appen er nå klar for deploy med Docker. Den leser `PORT` fra hosting-miljøet og lytter på `0.0.0.0`, som trengs for at offentlige web-tjenester skal nå serveren.

## Viktig sikkerhet

Dette dashboardet har ingen innlogging ennå. Ikke legg det offentlig med ekte konto-/broker-nøkler før vi har lagt til passord, login eller annen tilgangskontroll.

## Lokal Docker-test

```bash
docker build -t market-scout .
docker run --rm -p 8765:10000 market-scout
```

Åpne:

```text
http://127.0.0.1:8765
```

## Render

1. Legg prosjektet i et GitHub-repo.
2. Gå til Render og opprett en ny Web Service.
3. Velg repoet.
4. Velg Docker som runtime/build type.
5. Deploy.

Render forventer at web services binder til `0.0.0.0` og en port, normalt `PORT`/`10000`. Dette er allerede satt opp i `Dockerfile` og `market_scout/web.py`.

## Railway

1. Legg prosjektet i GitHub, eller bruk Railway CLI.
2. Opprett et nytt Railway-prosjekt.
3. Koble repoet eller kjør:

```bash
railway up
```

Railway finner `Dockerfile` i prosjektroten og bygger fra den.

## Fly.io

Fra prosjektmappen:

```bash
fly launch
fly deploy
```

Fly kan deploye direkte fra `Dockerfile`. Hvis Fly spør om intern port, bruk `10000`.

## Neste steg før ekte bruk

1. Legg til innlogging/passord.
2. Sett en bedre markedsdatakilde enn Stooq hvis du vil ha hyppig oppdatering.
3. Kjør den offentlig som analyse/paper-trading først.
4. Ikke legg broker-nøkler i frontend eller i repoet.

