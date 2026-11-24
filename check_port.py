"""Windows launcher guard: don't silently keep using an old server on port 8787."""
import socket,json,urllib.request,sys
with socket.socket() as s:
    s.settimeout(.7)
    busy=(s.connect_ex(('127.0.0.1',8787))==0)
if busy:
    print('')
    print('[BIG BANG] 127.0.0.1:8787 is already occupied.')
    try:
        with urllib.request.urlopen('http://127.0.0.1:8787/api/health',timeout=3) as r:
            payload=json.loads(r.read().decode('utf-8'))
            print('Detected running BIG BANG version:',payload.get('version','unknown'))
    except Exception:
        print('The process on port 8787 is not responding as a compatible BIG BANG server.')
    print('Close the OLD BIG BANG server command window first, then run this launcher again.')
    sys.exit(2)
print('[BIG BANG] Port 8787 is available.')
