import logging

import colorlog


class SafeColorHandler(colorlog.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        finally:
            self.stream.write('\033[0m')  # Исправляем красную консоль Windows 10
            self.flush()


class CustomLogMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        def custom_start_response(status, headers, *args, **kwargs):
            ip = environ.get('REMOTE_ADDR', '0.0.0.0')
            method = environ.get('REQUEST_METHOD', '')
            path = environ.get('PATH_INFO', '')
            protocol = environ.get('SERVER_PROTOCOL', '')
            status_code = status.split()[0]

            logging.getLogger('werkzeug_request').info(f'{ip} "{method} {path} {protocol}" {status_code}')
            return start_response(status, headers, *args, **kwargs)

        return self.app(environ, custom_start_response)
