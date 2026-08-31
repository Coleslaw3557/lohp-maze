import socket
import sys

class ProgressBar:
    def __init__(self, header, stream=None):
        print(header, file=sys.stderr)
        self.pct = -1
    def update(self, progress):
        pct = int(progress * 10)
        if pct != self.pct:
            self.pct = pct
            print(f"  {int(progress*100)}%", file=sys.stderr)
    def done(self):
        print("  done", file=sys.stderr)

def resolve_ip_address(host, port, address_cache=None):
    hosts = host if isinstance(host, list) else [host]
    out = []
    for h in hosts:
        out += socket.getaddrinfo(h, port, type=socket.SOCK_STREAM)
    return out
