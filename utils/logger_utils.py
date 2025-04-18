import colorlog


class SafeColorHandler(colorlog.StreamHandler):
    def emit(self, record):
        try:
            super().emit(record)
        finally:
            self.stream.write('\033[0m')  # Исправляем красную консоль Windows 10
            self.flush()
