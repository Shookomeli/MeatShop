import sys
import os

def main():
    args = sys.argv[1:]
    host = '0.0.0.0'
    port = '3000'
    other_args = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--host' and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif arg.startswith('--host='):
            host = arg.split('=', 1)[1]
            i += 1
        elif arg == '--port' and i + 1 < len(args):
            port = args[i + 1]
            i += 2
        elif arg.startswith('--port='):
            port = arg.split('=', 1)[1]
            i += 1
        else:
            other_args.append(arg)
            i += 1

    addrport = f"{host}:{port}"
    cmd = [sys.executable, 'manage.py', 'runserver', addrport] + other_args
    os.execv(sys.executable, cmd)

if __name__ == '__main__':
    main()
