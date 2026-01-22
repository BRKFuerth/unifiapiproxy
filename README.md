# UniFi API Proxy

Eine sichere Flask-basierte Proxy-Anwendung für die UniFi Network API mit IP-Whitelist und API-Key-Authentifizierung.

## Features

- **IP-Whitelist**: Nur definierte IP-Adressen dürfen zugreifen
- **API-Key-Authentifizierung**: Zwei-Schicht-Authentifizierung (extern + UniFi)
- **Path-Whitelist**: Nur explizit erlaubte API-Endpunkte werden weitergeleitet
- **Logging**: Unbekannte Zugriffe werden protokolliert

## Konfiguration

Passe die `config.yaml` an deine Umgebung an:

```yaml
server:
  trust_proxy_headers: true
  real_ip_header: "x-forwarded-for"

auth:
  external_api_key: "dein-sicherer-api-key"

firewall:
  allowed_source_ips:
    - "127.0.0.1"
    - "192.168.1.100"

unifi:
  base_url: "https://dein-unifi-controller"
  api_key: "dein-unifi-api-key"
  verify_tls: false
  timeout_seconds: 15
```

## Installation

### Docker (empfohlen)

```bash
docker build -t unifi-api-proxy .
docker run -d \
  -p 8080:8080 \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  --name unifi-proxy \
  unifi-api-proxy
```

### Lokale Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python unifi_api_firewall_flask.py
```

## Verwendung

### API-Anfragen

Alle Anfragen müssen einen API-Key im Header enthalten:

```bash
curl -H "X-API-Key: dein-external-api-key" \
  http://localhost:8080/proxy/network/integration/v1/sites
```

### Health-Check

```bash
curl http://localhost:8080/health
```

## Deployment

### Tag erstellen und pushen

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

Dies triggert automatisch den GitHub Actions Workflow, der das Docker Image baut und in die GitHub Container Registry pusht.

## Erlaubte Endpunkte

- `GET /proxy/network/integration/v1/sites`
- `GET /proxy/network/integration/v1/sites/{site}/devices`
- `GET /proxy/network/integration/v1/sites/{site}/clients/{client}`
- `POST /proxy/network/integration/v1/sites/{site}/clients/{client}/actions`

## Lizenz

MIT
