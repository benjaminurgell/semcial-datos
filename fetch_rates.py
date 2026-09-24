"""Tipos de cambio diarios para las herramientas de semcial.com.

Consulta las APIs públicas y gratuitas de cada banco central y guarda rates.json con
cuántas unidades de cada moneda vale 1 USD. Si una fuente falla, usa la API abierta de
ExchangeRate-API como respaldo y, si también falla, conserva el valor anterior.

Solo usa la biblioteca estándar de Python: no hace falta instalar nada.
"""
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

OUT = 'rates.json'
UA = {'User-Agent': 'semcial-datos/1.0 (+https://semcial.com)'}
TODAY = date.today()
SINCE = (TODAY - timedelta(days=10)).isoformat()


def get(url, data=None, headers=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def ars():
    """BCRA, API de estadísticas cambiarias: tipo de cambio mayorista (Com. A 3500)."""
    url = f'https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde={SINCE}&fechahasta={TODAY}'
    # A veces responde una lista vacía por un momento: se reintenta antes de pasar al respaldo
    for _ in range(3):
        res = json.loads(get(url))['results']
        if res:
            break
        time.sleep(5)
    last = max(res, key=lambda r: r['fecha'])
    return last['detalle'][0]['tipoCotizacion'], last['fecha']


def uyu():
    """Banco Central del Uruguay, servicio web de cotizaciones: dólar billete (moneda 2225)."""
    body = f'''<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:cot="Cotiza"><soapenv:Body>
<cot:wsbcucotizaciones.Execute><cot:Entrada><cot:Moneda><cot:item>2225</cot:item></cot:Moneda>
<cot:FechaDesde>{SINCE}</cot:FechaDesde><cot:FechaHasta>{TODAY}</cot:FechaHasta><cot:Grupo>0</cot:Grupo>
</cot:Entrada></cot:wsbcucotizaciones.Execute></soapenv:Body></soapenv:Envelope>'''
    xml = get('https://cotizaciones.bcu.gub.uy/wscotizaciones/servlet/awsbcucotizaciones',
              data=body.encode(), headers={'Content-Type': 'text/xml; charset=utf-8'})
    rows = []
    for el in ET.fromstring(xml).iter():
        if el.tag.endswith('datoscotizaciones.dato'):
            vals = {c.tag.split('}')[-1]: c.text for c in el}
            rows.append((vals['Fecha'], float(vals['TCV'])))
    fecha, valor = max(rows)
    return valor, fecha


def clp():
    """Banco Central de Chile, dólar observado, a través de la API abierta mindicador.cl."""
    serie = json.loads(get('https://mindicador.cl/api/dolar'))['serie']
    return serie[0]['valor'], serie[0]['fecha'][:10]


def boc(series):
    """Banco de Canadá, API Valet: último valor disponible de cada serie contra el CAD."""
    url = f'https://www.bankofcanada.ca/valet/observations/{",".join(series)}/json?start_date={SINCE}'
    obs = json.loads(get(url))['observations']
    last = [o for o in obs if all(s in o for s in series)][-1]
    return {s: float(last[s]['v']) for s in series}, last['d']


def mxn():
    """Peso mexicano por USD, cruzando USD/CAD y MXN/CAD del Banco de Canadá."""
    v, d = boc(['FXUSDCAD', 'FXMXNCAD'])
    return round(v['FXUSDCAD'] / v['FXMXNCAD'], 4), d


def eur():
    """Banco Central Europeo, tipo de referencia USD por EUR (se invierte a EUR por USD)."""
    csv = get(f'https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod={SINCE}&format=csvdata').decode()
    rows = [line.split(',') for line in csv.strip().splitlines()[1:]]
    head = csv.splitlines()[0].split(',')
    i_date, i_val = head.index('TIME_PERIOD'), head.index('OBS_VALUE')
    last = max(rows, key=lambda r: r[i_date])
    return round(1 / float(last[i_val]), 4), last[i_date]


SOURCES = {
    'ARS': (ars, {'es': 'BCRA, tipo de cambio mayorista (Com. A 3500)', 'en': 'Central Bank of Argentina, wholesale rate (Com. A 3500)'}),
    'UYU': (uyu, {'es': 'Banco Central del Uruguay, dólar billete', 'en': 'Central Bank of Uruguay, US dollar rate'}),
    'CLP': (clp, {'es': 'Banco Central de Chile, dólar observado', 'en': 'Central Bank of Chile, observed dollar rate'}),
    'MXN': (mxn, {'es': 'Banco de Canadá, cruce USD/CAD y MXN/CAD', 'en': 'Bank of Canada, USD/CAD and MXN/CAD cross rate'}),
    'EUR': (eur, {'es': 'Banco Central Europeo, tipo de referencia', 'en': 'European Central Bank, reference rate'}),
}
FALLBACK = {'es': 'ExchangeRate-API (respaldo)', 'en': 'ExchangeRate-API (fallback)'}


def fallback():
    data = json.loads(get('https://open.er-api.com/v6/latest/USD'))
    day = datetime.fromtimestamp(data['time_last_update_unix'], tz=timezone.utc).date().isoformat()
    return data['rates'], day


def main():
    try:
        previous = json.load(open(OUT, encoding='utf-8'))['rates']
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        previous = {}

    rates = {'USD': {'rate': 1, 'date': TODAY.isoformat(), 'source': {'es': 'Referencia', 'en': 'Reference'}}}
    backup = None
    for code, (fetch, source) in SOURCES.items():
        entry = None
        try:
            value, day = fetch()
            entry = {'rate': value, 'date': day, 'source': source}
        except Exception as err:  # noqa: BLE001 — cualquier falla de la fuente pasa al respaldo
            print(f'{code}: falló la fuente oficial ({err}); uso el respaldo')
            try:
                backup = backup or fallback()
                entry = {'rate': round(backup[0][code], 4), 'date': backup[1], 'source': FALLBACK}
            except Exception as err2:  # noqa: BLE001
                print(f'{code}: falló también el respaldo ({err2})')

        prev = previous.get(code)
        # Control: un salto de más de 30% en un día casi seguro es un error de la fuente
        if entry and prev and abs(entry['rate'] / prev['rate'] - 1) > 0.30:
            print(f'{code}: {entry["rate"]} difiere más de 30% de {prev["rate"]}; conservo el anterior')
            entry = None
        rates[code] = entry or prev
        print(code, rates[code]['rate'] if rates[code] else 'sin dato', rates[code]['date'] if rates[code] else '')

    missing = [c for c, v in rates.items() if v is None]
    if missing:
        raise SystemExit(f'Sin dato para {missing}: no se actualiza el archivo')

    json.dump({'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'base': 'USD', 'rates': rates},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
