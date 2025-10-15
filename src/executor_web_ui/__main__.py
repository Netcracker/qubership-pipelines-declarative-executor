import os
import sys
import json
import aiofiles
import logging

from base64 import b64decode
from functools import wraps
from aiohttp import web

PORT = 8000
REPORT_FILE = os.path.join(os.path.dirname(__file__), 'report', 'report_data.json')


def require_basic_auth(handler):
    @wraps(handler)
    async def wrapped(request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Basic '):
            return web.Response(text='Authentication required', status=401)
        encoded_credentials = auth_header.split(' ')[1]
        try:
            decoded = b64decode(encoded_credentials).decode('utf-8')
            username, password = decoded.split(':', 1)
            if username != 'user' or password != 'password':
                return web.Response(text='Invalid credentials', status=403)
        except (ValueError, UnicodeDecodeError):
            return web.Response(text='Invalid authentication header', status=401)
        return await handler(request)
    return wrapped


def require_bearer_auth(handler):
    @wraps(handler)
    async def wrapped(request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return web.Response(text='Authentication required', status=401)
        bearer_token = auth_header.split(' ')[1]
        if bearer_token != 'my_cool_token':
            return web.Response(text='Invalid credentials', status=403)
        return await handler(request)
    return wrapped


@require_bearer_auth
async def send_report(request):
    try:
        data = await request.json()
        async with aiofiles.open(REPORT_FILE, 'w') as f:
            await f.write(json.dumps(data))
        return web.json_response({'status': 'success'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def get_report(request):
    try:
        if not os.path.exists(REPORT_FILE):
            return web.json_response({'error': 'No report found'}, status=404)
        async with aiofiles.open(REPORT_FILE, 'r') as f:
            content = await f.read()
            data = json.loads(content)
        return web.json_response(data)
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def serve_index(request):
    return web.FileResponse('./static/index.html')


def create_app():
    app = web.Application()

    app.router.add_get('/', serve_index)
    app.router.add_post('/send_report', send_report)
    app.router.add_get('/get_report', get_report)
    app.router.add_static('/', path='static/', name='static')

    async def add_cors(request, response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

    app.on_response_prepare.append(add_cors)
    return app


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format=u'[%(asctime)s] [%(levelname)-s] [%(filename)s]: %(message)s')
    os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=8000)
