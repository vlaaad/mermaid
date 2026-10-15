"""Local game preview plus a same-origin endpoint for actual browser frame evidence."""
import argparse
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path!='/__capture':
            self.send_error(404);return
        origin=urlparse(self.headers.get('Origin',''))
        if origin.hostname not in ('127.0.0.1','localhost') or origin.port!=self.server.server_port:
            self.send_error(403);return
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<16*1024*1024:raise ValueError('Invalid capture size')
            data=json.loads(self.rfile.read(length))
            png=base64.b64decode(data.pop('png'),validate=True)
            if not png.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Expected PNG')
            image=Image.open(io.BytesIO(png));image.verify()
            out=ROOT/'artifacts/scene';out.mkdir(parents=True,exist_ok=True)
            temporary=out/'browser.pending.png';temporary.write_bytes(png);temporary.replace(out/'browser.png')
            (out/'browser-metrics.json').write_text(json.dumps(data,indent=2)+'\n')
            reply=json.dumps({'saved':'artifacts/scene/browser.png'}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(reply)
        except (ValueError,KeyError,OSError) as exc:
            self.send_error(400,str(exc))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--directory',type=Path,help='Built HTML5 game folder (defaults to Bob bundle, then editor preview)')
    args=p.parse_args()
    bundle=ROOT/'artifacts/browser/mermaid'
    directory=args.directory or (bundle if (bundle/'index.html').exists() else ROOT/'build/default_html5/__htmlLaunchDir/mermaid')
    if not (directory/'index.html').exists():p.error(f'No HTML5 game at {directory}; bundle first')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(directory)))
    print(f'Game: http://127.0.0.1:{args.port}/ | capture/debug: /?capture=1&debug=1',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
