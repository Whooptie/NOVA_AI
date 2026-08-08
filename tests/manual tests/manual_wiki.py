import urllib.request, urllib.parse, json

for woord in ['Appel', 'Appel_(vrucht)']:
    url = 'https://nl.wikipedia.org/api/rest_v1/page/summary/' + urllib.parse.quote(woord)
    req = urllib.request.Request(url, headers={'User-Agent': 'Nova-AI/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode('utf-8'))
            print('WOORD:', woord)
            print('TYPE:', data.get('type'))
            print('EXTRACT:', data.get('extract', '')[:300])
            print()
    except Exception as e:
        print('FOUT:', woord, e)